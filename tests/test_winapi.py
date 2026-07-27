"""Contraintes de placement des fenêtres sur un bureau multi-écrans."""

import pytest

import winapi

# Montage réel du poste : un écran à gauche du principal, donc origine négative.
DESKTOP = {"x": -1080, "y": 0, "w": 4920, "h": 1920, "monitors": 3}


@pytest.mark.parametrize("x,y", [(0, 0), (100, 100), (-1000, 500), (3000, 1000)])
def test_a_window_already_inside_is_left_alone(x, y):
    assert winapi.clamp_rect(x, y, 220, 150, DESKTOP) == (x, y)


def test_overflow_on_the_right_is_pulled_back():
    """Le cas vécu : le dialogue débordait de 142 px hors de l'écran."""
    x, _ = winapi.clamp_rect(1842, 20, 220, 150, {"x": 0, "y": 0, "w": 1920, "h": 1080})
    assert x == 1700
    assert x + 220 == 1920


def test_overflow_on_the_bottom_is_pulled_back():
    _, y = winapi.clamp_rect(0, 1900, 220, 150, DESKTOP)
    assert y == 1770


def test_negative_origin_is_respected():
    """Le bord gauche du bureau est à -1080, pas à 0."""
    assert winapi.clamp_rect(-5000, 0, 220, 150, DESKTOP) == (-1080, 0)


def test_window_larger_than_desktop_keeps_its_top_left_reachable():
    small = {"x": 0, "y": 0, "w": 200, "h": 100}
    assert winapi.clamp_rect(50, 50, 800, 600, small) == (0, 0)


@pytest.mark.parametrize("vs", [None, {}, {"x": 0, "y": 0, "w": 0, "h": 0}])
def test_unknown_desktop_leaves_the_position_untouched(vs):
    assert winapi.clamp_rect(1842, 20, 220, 150, vs) == (1842, 20)


def test_clamp_to_screen_keeps_the_cursor_on_the_desktop():
    assert winapi.clamp_to_screen(99_999, -99_999, DESKTOP) == (3839, 0)


# ── Écran porteur ────────────────────────────────────────────────────────────

def test_monitor_rect_describes_one_real_screen():
    """hwnd=0 renvoie l'écran principal : plus petit que le bureau entier."""
    mon = winapi.monitor_rect(0)
    vs = winapi.virtual_screen()

    assert mon["w"] > 0 and mon["h"] > 0
    assert mon["x"] >= vs["x"]
    assert mon["x"] + mon["w"] <= vs["x"] + vs["w"]
    assert mon["y"] + mon["h"] <= vs["y"] + vs["h"]


def test_monitor_rect_falls_back_instead_of_raising():
    """Un handle invalide ne doit pas remonter d'exception à l'interface."""
    mon = winapi.monitor_rect(0xDEADBEEF)
    assert mon["w"] > 0 and mon["h"] > 0
