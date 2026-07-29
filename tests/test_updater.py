"""Mise à jour : comparaison de versions, tri de la réponse GitHub, bascule.

Rien ici ne touche au réseau : la réponse de l'API est un dictionnaire posé à
la main, et le téléchargement passe par une URL `file://`. Le remplacement
d'un exécutable en cours d'exécution, lui, ne se teste que sur la machine —
ces tests couvrent le renommage et le retour en arrière sur des fichiers
ordinaires.
"""

import hashlib

import pytest

import updater
from updater import UpdateError


# ── Versions ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tag, expected", [
    ("v1.2.0", (1, 2, 0)),
    ("1.2.0", (1, 2, 0)),
    ("V2.0", (2, 0)),
    ("", None),
    ("v", None),
    ("abc", None),
    ("1.2.beta", None),
    (None, None),
    (120, None),
])
def test_parse_tag(tag, expected):
    assert updater.parse_tag(tag) == expected


@pytest.mark.parametrize("tag, current, newer", [
    ("v1.2.0", "1.1.0", True),
    ("v1.1.1", "1.1.0", True),
    ("v2.0", "1.9.9", True),
    ("v1.1.0", "1.1.0", False),
    ("v1.2", "1.2.0", False),  # longueurs différentes, même version
    ("v1.0.9", "1.1.0", False),
    ("garbage", "1.1.0", False),
    (None, "1.1.0", False),
])
def test_is_newer(tag, current, newer):
    assert updater.is_newer(tag, current) is newer


# ── Lecture de la réponse GitHub ─────────────────────────────────────────────

def _payload(tag="v99.0.0", assets=None):
    if assets is None:
        assets = [{
            "name": updater.ASSET_NAME,
            "browser_download_url": "https://example.invalid/ClickClick.exe",
            "size": 123,
            "digest": "sha256:" + "0" * 64,
        }]
    return {"tag_name": tag, "assets": assets}


def test_extract_info_reads_the_asset():
    info = updater.extract_info(_payload())
    assert info == {
        "version": "99.0.0",
        "url": "https://example.invalid/ClickClick.exe",
        "size": 123,
        "sha256": "0" * 64,
    }


def test_extract_info_ignores_older_or_equal_releases():
    from version import __version__
    assert updater.extract_info(_payload(tag="v0.0.1")) is None
    assert updater.extract_info(_payload(tag=f"v{__version__}")) is None


def test_extract_info_without_the_expected_asset():
    assert updater.extract_info(_payload(assets=[])) is None
    assert updater.extract_info(
        _payload(assets=[{"name": "autre.zip"}])
    ) is None


def test_extract_info_survives_a_strange_payload():
    assert updater.extract_info(None) is None
    assert updater.extract_info({}) is None
    assert updater.extract_info({"tag_name": "v99.0", "assets": None}) is None


def test_extract_info_without_digest_still_works():
    payload = _payload()
    del payload["assets"][0]["digest"]
    info = updater.extract_info(payload)
    assert info["sha256"] is None


# ── Téléchargement ───────────────────────────────────────────────────────────

def _local_info(tmp_path, content: bytes, size=None, sha256=None):
    src = tmp_path / "release.bin"
    src.write_bytes(content)
    return {
        "version": "99.0.0",
        "url": src.as_uri(),
        "size": len(content) if size is None else size,
        "sha256": hashlib.sha256(content).hexdigest() if sha256 is None else sha256,
    }


def test_download_verifies_size_and_hash(tmp_path):
    dest = tmp_path / "new.exe"
    updater.download(_local_info(tmp_path, b"binaire"), dest)
    assert dest.read_bytes() == b"binaire"


def test_download_rejects_a_wrong_size(tmp_path):
    with pytest.raises(UpdateError, match="size"):
        updater.download(_local_info(tmp_path, b"binaire", size=999),
                         tmp_path / "new.exe")


def test_download_rejects_a_wrong_hash(tmp_path):
    with pytest.raises(UpdateError, match="sha256"):
        updater.download(_local_info(tmp_path, b"binaire", sha256="f" * 64),
                         tmp_path / "new.exe")


# ── Bascule ──────────────────────────────────────────────────────────────────

def test_swap_replaces_the_executable(tmp_path):
    exe = tmp_path / "ClickClick.exe"
    new = tmp_path / "ClickClick.new.exe"
    exe.write_bytes(b"ancien")
    new.write_bytes(b"nouveau")

    updater.swap(exe, new)

    assert exe.read_bytes() == b"nouveau"
    assert (tmp_path / "ClickClick.old.exe").read_bytes() == b"ancien"
    assert not new.exists()


def test_swap_overwrites_a_leftover_old(tmp_path):
    exe = tmp_path / "ClickClick.exe"
    new = tmp_path / "ClickClick.new.exe"
    old = tmp_path / "ClickClick.old.exe"
    exe.write_bytes(b"ancien")
    new.write_bytes(b"nouveau")
    old.write_bytes(b"fossile")

    updater.swap(exe, new)

    assert exe.read_bytes() == b"nouveau"
    assert old.read_bytes() == b"ancien"


def test_swap_rolls_back_when_the_new_file_is_missing(tmp_path):
    exe = tmp_path / "ClickClick.exe"
    exe.write_bytes(b"ancien")

    with pytest.raises(OSError):
        updater.swap(exe, tmp_path / "ClickClick.new.exe")

    # L'exécutable d'origine a repris son nom : rien n'est perdu.
    assert exe.read_bytes() == b"ancien"
    assert not (tmp_path / "ClickClick.old.exe").exists()


# ── Garde-fous ───────────────────────────────────────────────────────────────

def test_apply_refuses_to_run_from_source():
    with pytest.raises(UpdateError, match="packaged"):
        updater.apply({"version": "99.0.0", "url": "https://example.invalid"})


def test_exe_path_is_none_in_development():
    assert updater.exe_path() is None
