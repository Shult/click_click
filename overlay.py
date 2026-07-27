import logging
import queue
import time
import tkinter as tk
from typing import Callable

from pynput.keyboard import Key

import sessions
import settings
import winapi
from sessions import SessionError, load_session, save_session
from state import state
from version import __version__

log = logging.getLogger(__name__)

MAX_LISTED_SESSIONS = 10


class OverlayApp:
    BG = "#1e1e1e"
    BG2 = "#161616"
    HDR = "#111111"

    def __init__(self, on_key_press: Callable):
        self._on_kp = on_key_press
        state.app = self

        self.root = tk.Tk()
        self.root.title("Mouse Recorder")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.93)
        self.root.configure(bg=self.BG)

        # Le processus est DPI-aware : Tk ne met plus les tailles à l'échelle
        # tout seul, il faut lui donner le ratio du poste.
        self.scale = winapi.system_dpi() / winapi.DEFAULT_DPI
        self.root.tk.call("tk", "scaling", winapi.system_dpi() / 72)

        self._drag_x = self._drag_y = 0
        self._click_through = False
        # Dernier compte fini connu : sortir du mode infini doit rendre une
        # valeur utilisable, pas repartir de 1.
        self._finite_times = state.play_times or 1

        self._build_ui()
        self.root.update()
        self._hwnd = self.root.winfo_id()
        self._restore_position()
        self._update()

    def px(self, n: int) -> int:
        return int(round(n * self.scale))

    # ── Placement ────────────────────────────────────────────────────────────

    def _restore_position(self):
        """Replace la fenêtre où l'utilisateur l'avait laissée.

        La position est contrainte au bureau courant : un écran débranché
        depuis la dernière session ne doit pas rendre l'overlay inatteignable.
        """
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if state.window_pos:
            x, y = state.window_pos
        else:
            x = self.root.winfo_screenwidth() - self.px(250)
            y = self.px(20)
        x, y = winapi.clamp_rect(x, y, w, h, winapi.virtual_screen())
        self.root.geometry(f"+{x}+{y}")

    def _place_beside(self, win, w: int, h: int):
        """Accole une fenêtre à l'overlay, du côté où il y a la place.

        Le cadre de référence est l'**écran** qui porte l'overlay, pas le
        bureau virtuel : l'overlay étant ancré près du bord droit, une fenêtre
        posée à sa droite tenait dans le bureau mais débordait de l'écran
        (142 px mesurés en 1920 de large) et s'affichait à cheval sur l'écran
        voisin.
        """
        self.root.update_idletasks()
        ox, oy = self.root.winfo_x(), self.root.winfo_y()
        ow = self.root.winfo_width()
        gap = self.px(8)
        mon = winapi.monitor_rect(self._hwnd)

        x = ox + ow + gap
        if mon["w"] > 0 and x + w > mon["x"] + mon["w"]:
            x = ox - w - gap  # bascule à gauche de l'overlay
        x, y = winapi.clamp_rect(x, oy, w, h, mon)
        win.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=self.HDR, cursor="fleur")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Mouse Recorder", bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(side="left", padx=(7, 0), pady=3)
        # Affiché en clair : sans repère visible, impossible de savoir quelle
        # version tourne quand deux binaires coexistent sur la machine.
        tk.Label(hdr, text=f"v{__version__}", bg=self.HDR, fg="#3a3a3a",
                 font=("Segoe UI", 7)).pack(side="left", padx=(4, 0), pady=3)
        tk.Button(hdr, text="×", bg=self.HDR, fg="#555555",
                  font=("Segoe UI", 11, "bold"), bd=0,
                  activebackground="#aa2222", activeforeground="white",
                  cursor="hand2", command=self._quit).pack(side="right", padx=5)
        hdr.bind("<Button-1>", self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)
        hdr.bind("<ButtonRelease-1>", self._drag_end)

        self.status_var = tk.StringVar(value="⏸  EN ATTENTE")
        self.status_lbl = tk.Label(self.root, textvariable=self.status_var,
                                   bg=self.BG, fg="#555555",
                                   font=("Segoe UI", 13, "bold"))
        self.status_lbl.pack(pady=(7, 0))

        self.session_var = tk.StringVar(value="—")
        self.session_lbl = tk.Label(self.root, textvariable=self.session_var,
                                    bg=self.BG, fg="#3a3a3a",
                                    font=("Segoe UI", 8))
        self.session_lbl.pack()

        row1 = tk.Frame(self.root, bg=self.BG)
        row1.pack(padx=8, pady=6, fill="x")
        self._btn(row1, "⏺  F8", "#7a1a1a", lambda: self._on_kp(Key.f8)).pack(side="left", expand=True, fill="x", padx=2)
        self._btn(row1, "⏹  F9", "#333333", lambda: self._on_kp(Key.f9)).pack(side="left", expand=True, fill="x", padx=2)
        self._btn(row1, "▶  F10", "#1a4a1a", lambda: self._on_kp(Key.f10)).pack(side="left", expand=True, fill="x", padx=2)

        row2 = tk.Frame(self.root, bg=self.BG)
        row2.pack(padx=8, pady=(0, 7), fill="x")
        self._small_btn(row2, "📂 Sessions", self._toggle_sessions).pack(side="left", expand=True, fill="x", padx=2)
        self._small_btn(row2, "⚙ Réglages", self._toggle_settings).pack(side="left", expand=True, fill="x", padx=2)

        self.panel_frame = tk.Frame(self.root, bg=self.BG2)
        self._active_panel = None  # "sessions" | "settings" | None

    def _btn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="white",
                         font=("Segoe UI", 9, "bold"), bd=0, relief="flat",
                         activebackground=color, activeforeground="white",
                         cursor="hand2", pady=5, command=cmd)

    def _small_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, bg="#242424", fg="#777777",
                         font=("Segoe UI", 8), bd=0, relief="flat",
                         activebackground="#303030", activeforeground="white",
                         cursor="hand2", pady=3, command=cmd)

    # ── Panel helpers ────────────────────────────────────────────────────────

    def _open_panel(self, name: str, builder):
        if self._active_panel == name:
            self._close_panel()
            return
        self._active_panel = name
        for w in self.panel_frame.winfo_children():
            w.destroy()
        builder(self.panel_frame)
        self.panel_frame.pack(fill="x")
        self.root.update()

    def _close_panel(self):
        self._active_panel = None
        self.panel_frame.pack_forget()
        for w in self.panel_frame.winfo_children():
            w.destroy()
        self.root.update()

    # ── Settings panel ───────────────────────────────────────────────────────

    def _build_settings(self, f):
        tk.Frame(f, bg="#2a2a2a", height=1).pack(fill="x")

        def row(label, widget_fn):
            r = tk.Frame(f, bg=self.BG2)
            r.pack(fill="x", padx=8, pady=3)
            tk.Label(r, text=label, bg=self.BG2, fg="#666666",
                     font=("Segoe UI", 8), width=12, anchor="w").pack(side="left")
            widget_fn(r).pack(side="right")

        self.times_var = tk.StringVar(value=settings.format_times(state.play_times))

        def times_w(p):
            f2 = tk.Frame(p, bg=self.BG2)
            tk.Button(f2, text=" − ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("times", -1)).pack(side="left")
            # Conteneur : le nombre y est tantôt un libellé, tantôt un champ de
            # saisie. Régler 200 répétitions au bouton « + » demandait 199 clics.
            self.times_box = tk.Frame(f2, bg=self.BG2)
            self.times_box.pack(side="left")
            self._show_times_label()
            tk.Button(f2, text=" + ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("times", 1)).pack(side="left")
            self.inf_btn = tk.Button(
                f2, text=" ∞ ", fg="white", bd=0, font=("Segoe UI", 9),
                cursor="hand2", command=self._toggle_infinite,
            )
            self.inf_btn.pack(side="left", padx=(4, 0))
            self._paint_infinite_btn()
            return f2
        row("Répétitions", times_w)

        self.delay_var = tk.StringVar(value=f"{state.play_delay:.1f}s")

        def delay_w(p):
            f2 = tk.Frame(p, bg=self.BG2)
            tk.Button(f2, text=" − ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("delay", -0.5)).pack(side="left")
            tk.Label(f2, textvariable=self.delay_var, bg=self.BG2, fg="white",
                     font=("Segoe UI", 9), width=4, anchor="center").pack(side="left")
            tk.Button(f2, text=" + ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("delay", 0.5)).pack(side="left")
            return f2
        row("Délai (s)", delay_w)

        self.skip_var = tk.BooleanVar(value=state.play_skip_moves)

        def skip_w(p):
            return tk.Checkbutton(p, variable=self.skip_var, bg=self.BG2,
                                  selectcolor="#2a2a2a", activebackground=self.BG2,
                                  command=self._toggle_skip)
        row("Skip moves", skip_w)

    # ── Sessions panel ───────────────────────────────────────────────────────

    def _build_sessions(self, f):
        tk.Frame(f, bg="#2a2a2a", height=1).pack(fill="x")

        names = sessions.list_sessions(by_date=state.sort_by_date)

        sort_lbl = "date" if state.sort_by_date else "A-Z"
        tk.Button(f, text=f"Tri : {sort_lbl}", bg=self.BG2, fg="#555555",
                  font=("Segoe UI", 7), bd=0, cursor="hand2",
                  activebackground=self.BG2, activeforeground="#888888",
                  command=self._toggle_sort).pack(anchor="w", padx=8, pady=(3, 1))

        if not names:
            tk.Label(f, text="Aucune session", bg=self.BG2, fg="#444444",
                     font=("Segoe UI", 8)).pack(pady=6)
            return

        for name in names[:MAX_LISTED_SESSIONS]:
            color = "#55cc55" if name == state.active_session else "#888888"
            tk.Button(f, text=name, bg=self.BG2, fg=color,
                      font=("Segoe UI", 8), bd=0, anchor="w",
                      activebackground="#252525", activeforeground="white",
                      cursor="hand2",
                      command=lambda n=name: self._load_session(n),
                      ).pack(fill="x", padx=12, pady=1)

        if len(names) > MAX_LISTED_SESSIONS:
            tk.Label(f, text=f"+ {len(names) - MAX_LISTED_SESSIONS} autres",
                     bg=self.BG2, fg="#444444",
                     font=("Segoe UI", 7)).pack(pady=(2, 4))

    # ── Panel toggles ────────────────────────────────────────────────────────

    def _toggle_sessions(self):
        self._open_panel("sessions", self._build_sessions)

    def _toggle_settings(self):
        self._open_panel("settings", self._build_settings)

    def _toggle_sort(self):
        state.sort_by_date = not state.sort_by_date
        settings.save()
        self._open_panel("sessions", self._build_sessions)

    def _load_session(self, name: str):
        load_session(name)
        self._close_panel()

    # ── Settings actions ─────────────────────────────────────────────────────

    def _show_times_label(self):
        """Affiche le nombre de répétitions, cliquable pour le saisir."""
        for w in self.times_box.winfo_children():
            w.destroy()
        lbl = tk.Label(self.times_box, textvariable=self.times_var, bg=self.BG2,
                       fg="white", font=("Segoe UI", 9), width=4,
                       anchor="center", cursor="hand2")
        lbl.pack()
        lbl.bind("<Button-1>", lambda _e: self._edit_times())

    def _edit_times(self):
        """Remplace le nombre par un champ de saisie, le temps d'une valeur."""
        if state.playing:
            return  # l'overlay est click-through, mais le clavier reste actif
        for w in self.times_box.winfo_children():
            w.destroy()

        var = tk.StringVar(value="" if state.play_times == settings.INFINITE
                          else str(state.play_times))
        entry = tk.Entry(self.times_box, textvariable=var, width=4,
                         bg=self.BG, fg="white", insertbackground="white",
                         relief="flat", justify="center", font=("Segoe UI", 9),
                         highlightthickness=1, highlightcolor="#444444",
                         highlightbackground="#333333")
        entry.pack()
        # La fenêtre est `overrideredirect` : Windows ne lui donne pas le focus
        # clavier de lui-même, il faut le réclamer.
        self.root.focus_force()
        entry.focus_set()
        entry.select_range(0, "end")

        # `_show_times_label` détruit le champ, ce qui déclenche à son tour le
        # <FocusOut> : sans ce verrou, la fermeture se rappelle elle-même.
        closing = False

        def close(validate: bool):
            nonlocal closing
            if closing:
                return
            closing = True
            if validate:
                value = settings.parse_times(var.get())
                # Saisie refusée : rien ne change. Le champ redevient un
                # libellé affichant l'ancienne valeur, la correction est lisible.
                if value is not None:
                    self._set_times(value)
            self._show_times_label()

        entry.bind("<Return>", lambda _e: close(True))
        entry.bind("<KP_Enter>", lambda _e: close(True))
        entry.bind("<Escape>", lambda _e: close(False))
        entry.bind("<FocusOut>", lambda _e: close(False))

    def _set_times(self, value: int):
        state.play_times = value
        self.times_var.set(settings.format_times(value))
        if value != settings.INFINITE:
            self._finite_times = value
        self._paint_infinite_btn()
        settings.save()

    def _paint_infinite_btn(self):
        on = state.play_times == settings.INFINITE
        self.inf_btn.config(bg="#1a4a1a" if on else "#2a2a2a",
                            activebackground="#245a24" if on else "#3a3a3a")

    def _toggle_infinite(self):
        if state.play_times == settings.INFINITE:
            self._set_times(self._finite_times)
        else:
            self._set_times(settings.INFINITE)

    def _adj(self, what: str, delta):
        if what == "times":
            # Depuis le mode infini, « − » et « + » repartent du dernier compte
            # fini : incrémenter zéro n'aurait aucun sens pour l'utilisateur.
            base = (self._finite_times if state.play_times == settings.INFINITE
                    else state.play_times)
            self._set_times(max(1, min(settings.MAX_TIMES, base + int(delta))))
            return
        if what == "delay":
            state.play_delay = round(
                max(0.0, min(settings.MAX_DELAY, state.play_delay + delta)), 1
            )
            self.delay_var.set(f"{state.play_delay:.1f}s")
        settings.save()

    def _toggle_skip(self):
        state.play_skip_moves = self.skip_var.get()
        settings.save()

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, _e=None):
        # Au relâchement seulement : pendant le glissement, chaque pixel
        # parcouru déclencherait une écriture disque.
        state.window_pos = (self.root.winfo_x(), self.root.winfo_y())
        settings.save()

    # ── Click-through ────────────────────────────────────────────────────────

    def _set_click_through(self, enable: bool):
        if self._click_through == enable:
            return
        self._click_through = enable
        self.root.wm_attributes("-alpha", 0.22 if enable else 0.93)
        winapi.set_click_through(self._hwnd, enable)

    # ── Save dialog (thread Tk uniquement) ───────────────────────────────────

    def show_save_dialog(self, duration: float):
        dialog = tk.Toplevel(self.root)
        dialog.title("")
        dialog.overrideredirect(True)
        dialog.wm_attributes("-topmost", True)
        dialog.configure(bg=self.HDR)

        self._place_beside(dialog, self.px(220), self.px(150))

        hdr = tk.Frame(dialog, bg=self.HDR, cursor="fleur")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Sauvegarder la session", bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(side="left", padx=7, pady=4)

        drag = {"x": 0, "y": 0}

        def drag_start(e):
            drag["x"], drag["y"] = e.x, e.y

        def drag_move(e):
            dialog.geometry(
                f"+{dialog.winfo_x() + e.x - drag['x']}"
                f"+{dialog.winfo_y() + e.y - drag['y']}"
            )
        hdr.bind("<Button-1>", drag_start)
        hdr.bind("<B1-Motion>", drag_move)

        tk.Label(dialog, text=f"{len(state.events)} évts  •  {duration:.2f}s",
                 bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(pady=(10, 4))

        entry_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=entry_var,
                         bg=self.BG, fg="white", insertbackground="white",
                         relief="flat", font=("Segoe UI", 10),
                         highlightthickness=1, highlightcolor="#444444",
                         highlightbackground="#333333")
        entry.pack(padx=16, fill="x")
        entry.focus_set()

        error_var = tk.StringVar()
        tk.Label(dialog, textvariable=error_var, bg=self.HDR, fg="#cc5555",
                 font=("Segoe UI", 7), wraplength=self.px(190)).pack(pady=(3, 0))

        def confirm(e=None):
            raw = entry_var.get().strip() or f"session_{int(time.time())}"
            try:
                name = sessions.sanitize_name(raw)
                save_session(name)
            except SessionError as exc:
                error_var.set(str(exc))
                return
            state.active_session = name
            state.session_screen = winapi.virtual_screen()
            state.screen_mismatch = False
            dialog.destroy()

        def cancel(e=None):
            dialog.destroy()

        tk.Button(dialog, text="Enregistrer", bg="#1a4a1a", fg="white",
                  font=("Segoe UI", 9, "bold"), bd=0, relief="flat",
                  activebackground="#1a4a1a", activeforeground="white",
                  cursor="hand2", pady=5, command=confirm).pack(
                      padx=16, pady=10, fill="x")

        entry.bind("<Return>", confirm)
        entry.bind("<Escape>", cancel)
        dialog.bind("<Escape>", cancel)

        # Neutralise les raccourcis globaux : sans ça, taper un nom contenant
        # F8/F10 déclencherait un enregistrement ou une lecture.
        state.modal_open = True
        dialog.grab_set()
        try:
            self.root.wait_window(dialog)
        finally:
            state.modal_open = False

    # ── Polling ──────────────────────────────────────────────────────────────

    def _drain_ui_queue(self):
        """Exécute dans le thread Tk ce que les écouteurs y ont déposé."""
        while True:
            try:
                action = state.ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                action(self)
            except Exception:
                log.exception("action d'interface en échec")

    def _update(self):
        if state.quit.is_set():
            self.root.destroy()
            return

        if state.playing:
            self.status_var.set(
                f"▶  PLAYING  ({state.play_current}"
                f"/{settings.format_times(state.play_times)})"
            )
            self.status_lbl.config(fg="#44cc44")
            self._set_click_through(True)
        elif state.recording:
            self.status_var.set("⏺  REC")
            self.status_lbl.config(fg="#cc3333")
            self._set_click_through(False)
        else:
            self.status_var.set("⏸  EN ATTENTE")
            self.status_lbl.config(fg="#555555")
            self._set_click_through(False)

        name = state.active_session or "—"
        if state.active_session and state.screen_mismatch:
            self.session_var.set(f"⚠ {name}  (écran différent)")
            self.session_lbl.config(fg="#cc8844")
        else:
            self.session_var.set(name)
            self.session_lbl.config(fg="#3a3a3a")

        self._drain_ui_queue()
        self.root.after(150, self._update)

    def _quit(self):
        state.stop_play.set()
        state.quit.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
