import os
import time
import ctypes
import tkinter as tk
from typing import Callable
from pynput.keyboard import Key
from state import state
from sessions import load_session, save_session, SESSIONS_DIR

GWL_EXSTYLE       = -20
WS_EX_TRANSPARENT = 0x00000020


class OverlayApp:
    BG  = "#1e1e1e"
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

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{sw - 250}+20")

        self._drag_x = self._drag_y = 0
        self._click_through = False
        self._sort_by_date  = True

        self._build_ui()
        self.root.update()
        self._hwnd = self.root.winfo_id()
        self._update()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=self.HDR, cursor="fleur")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Mouse Recorder", bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(side="left", padx=7, pady=3)
        tk.Button(hdr, text="×", bg=self.HDR, fg="#555555",
                  font=("Segoe UI", 11, "bold"), bd=0,
                  activebackground="#aa2222", activeforeground="white",
                  cursor="hand2", command=self._quit).pack(side="right", padx=5)
        hdr.bind("<Button-1>",  self._drag_start)
        hdr.bind("<B1-Motion>", self._drag_move)

        self.status_var = tk.StringVar(value="⏸  EN ATTENTE")
        self.status_lbl = tk.Label(self.root, textvariable=self.status_var,
                                    bg=self.BG, fg="#555555",
                                    font=("Segoe UI", 13, "bold"))
        self.status_lbl.pack(pady=(7, 0))

        self.session_var = tk.StringVar(value="—")
        tk.Label(self.root, textvariable=self.session_var,
                 bg=self.BG, fg="#3a3a3a", font=("Segoe UI", 8)).pack()

        row1 = tk.Frame(self.root, bg=self.BG)
        row1.pack(padx=8, pady=6, fill="x")
        self._btn(row1, "⏺  F8",  "#7a1a1a", lambda: self._on_kp(Key.f8) ).pack(side="left", expand=True, fill="x", padx=2)
        self._btn(row1, "⏹  F9",  "#333333", lambda: self._on_kp(Key.f9) ).pack(side="left", expand=True, fill="x", padx=2)
        self._btn(row1, "▶  F10", "#1a4a1a", lambda: self._on_kp(Key.f10)).pack(side="left", expand=True, fill="x", padx=2)

        row2 = tk.Frame(self.root, bg=self.BG)
        row2.pack(padx=8, pady=(0, 7), fill="x")
        self._small_btn(row2, "📂 Sessions", self._toggle_sessions).pack(side="left", expand=True, fill="x", padx=2)
        self._small_btn(row2, "⚙ Réglages",  self._toggle_settings).pack(side="left", expand=True, fill="x", padx=2)

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

        self.times_var = tk.StringVar(value=str(state.play_times))

        def times_w(p):
            f2 = tk.Frame(p, bg=self.BG2)
            tk.Button(f2, text=" − ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("times", -1)).pack(side="left")
            tk.Label(f2, textvariable=self.times_var, bg=self.BG2, fg="white",
                     font=("Segoe UI", 9), width=3, anchor="center").pack(side="left")
            tk.Button(f2, text=" + ", bg="#2a2a2a", fg="white", bd=0,
                      font=("Segoe UI", 9), activebackground="#3a3a3a",
                      command=lambda: self._adj("times", 1)).pack(side="left")
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

        files = [x for x in os.listdir(SESSIONS_DIR) if x.endswith(".json")]
        if self._sort_by_date:
            files.sort(
                key=lambda x: os.path.getmtime(os.path.join(SESSIONS_DIR, x)),
                reverse=True,
            )
        else:
            files.sort()

        sort_lbl = "date" if self._sort_by_date else "A-Z"
        tk.Button(f, text=f"Tri : {sort_lbl}", bg=self.BG2, fg="#555555",
                  font=("Segoe UI", 7), bd=0, cursor="hand2",
                  activebackground=self.BG2, activeforeground="#888888",
                  command=self._toggle_sort).pack(anchor="w", padx=8, pady=(3, 1))

        if not files:
            tk.Label(f, text="Aucune session", bg=self.BG2, fg="#444444",
                     font=("Segoe UI", 8)).pack(pady=6)
            return

        for fname in files[:10]:
            name  = fname[:-5]
            color = "#55cc55" if name == state.active_session else "#888888"
            tk.Button(f, text=name, bg=self.BG2, fg=color,
                      font=("Segoe UI", 8), bd=0, anchor="w",
                      activebackground="#252525", activeforeground="white",
                      cursor="hand2",
                      command=lambda n=name: self._load_session(n),
                      ).pack(fill="x", padx=12, pady=1)

    # ── Panel toggles ────────────────────────────────────────────────────────

    def _toggle_sessions(self):
        self._open_panel("sessions", self._build_sessions)

    def _toggle_settings(self):
        self._open_panel("settings", self._build_settings)

    def _toggle_sort(self):
        self._sort_by_date = not self._sort_by_date
        self._open_panel("sessions", self._build_sessions)

    def _load_session(self, name: str):
        load_session(name)
        self._close_panel()

    # ── Settings actions ─────────────────────────────────────────────────────

    def _adj(self, what: str, delta):
        if what == "times":
            state.play_times = max(1, state.play_times + int(delta))
            self.times_var.set(str(state.play_times))
        elif what == "delay":
            state.play_delay = round(max(0.0, state.play_delay + delta), 1)
            self.delay_var.set(f"{state.play_delay:.1f}s")

    def _toggle_skip(self):
        state.play_skip_moves = self.skip_var.get()

    # ── Drag ─────────────────────────────────────────────────────────────────

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ── Click-through ────────────────────────────────────────────────────────

    def _set_click_through(self, enable: bool):
        if self._click_through == enable:
            return
        self._click_through = enable
        style = ctypes.windll.user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        if enable:
            self.root.wm_attributes("-alpha", 0.22)
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
            self.root.wm_attributes("-alpha", 0.93)
        ctypes.windll.user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, style)

    # ── Save dialog (appelé depuis le thread principal) ───────────────────────

    def _show_save_dialog(self, duration: float):
        dialog = tk.Toplevel(self.root)
        dialog.title("")
        dialog.overrideredirect(True)
        dialog.wm_attributes("-topmost", True)
        dialog.configure(bg=self.HDR)

        # Centrer sur l'overlay
        self.root.update_idletasks()
        ox = self.root.winfo_x()
        oy = self.root.winfo_y()
        ow = self.root.winfo_width()
        dialog.geometry(f"220x130+{ox + ow + 8}+{oy}")

        # Header draggable
        hdr = tk.Frame(dialog, bg=self.HDR, cursor="fleur")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Sauvegarder la session", bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(side="left", padx=7, pady=4)

        drag = {"x": 0, "y": 0}
        def drag_start(e): drag["x"], drag["y"] = e.x, e.y
        def drag_move(e):
            x = dialog.winfo_x() + e.x - drag["x"]
            y = dialog.winfo_y() + e.y - drag["y"]
            dialog.geometry(f"+{x}+{y}")
        hdr.bind("<Button-1>",  drag_start)
        hdr.bind("<B1-Motion>", drag_move)

        # Infos
        tk.Label(dialog, text=f"{len(state.events)} évts  •  {duration:.2f}s",
                 bg=self.HDR, fg="#555555",
                 font=("Segoe UI", 8)).pack(pady=(10, 4))

        # Champ texte
        entry_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=entry_var,
                         bg=self.BG, fg="white", insertbackground="white",
                         relief="flat", font=("Segoe UI", 10),
                         highlightthickness=1, highlightcolor="#444444",
                         highlightbackground="#333333")
        entry.pack(padx=16, fill="x")
        entry.focus_set()

        # Bouton valider
        def confirm(e=None):
            name = entry_var.get().strip() or f"session_{int(time.time())}"
            save_session(name)
            state.active_session = name
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

        dialog.grab_set()
        self.root.wait_window(dialog)

    # ── Polling ──────────────────────────────────────────────────────────────

    def _update(self):
        if state.quit.is_set():
            self.root.destroy()
            return

        if state.playing:
            self.status_var.set(f"▶  PLAYING  ({state.play_current}/{state.play_times})")
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

        self.session_var.set(state.active_session or "—")
        self.root.after(150, self._update)

    def _quit(self):
        state.quit.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
