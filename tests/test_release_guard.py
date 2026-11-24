"""Exercise the static artifact boundary using synthetic fixtures and reviewed public icons."""
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import shutil
import struct
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("check_release", ROOT / "scripts" / "check_release.py")
release = module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def build(tmp_path):
    shutil.copytree(release.PUBLIC, tmp_path, dirs_exist_ok=True)
    assets = tmp_path / "assets"
    assets.mkdir()
    for name in ("index-12345678.css", "index-87654321.js"):
        (assets / name).write_text("/* test */", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<script src="/r/assets/index-87654321.js"></script><link href="/r/assets/index-12345678.css">',
        encoding="utf-8",
    )
    for name, content in {
        "sw.js": 'importScripts("workbox-aabbccdd.js")',
        "workbox-aabbccdd.js": "// test", "registerSW.js": "// test",
        "manifest.webmanifest": '{"scope":"./"}',
    }.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return tmp_path


def test_only_expected_artifacts_are_accepted(build):
    assert release.check_release(build) == (12, [])


@pytest.mark.parametrize("name", [".env", ".git", "tasks.sqlite3", "tasks.json", "assets/index-12345678.js.map"])
def test_unexpected_file_blocks_publication(build, name):
    (build / name).write_text("private", encoding="utf-8")
    assert release.check_release(build)[1]


@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_linked_file_is_not_read(build, link):
    outside = build.parent / (build.name + "-outside")
    outside.write_text("private", encoding="utf-8")
    file = build / "registerSW.js"
    file.unlink()
    if link == "symlink":
        file.symlink_to(outside)
    else:
        os.link(outside, file)
    assert release.check_release(build)[1]


@pytest.mark.parametrize("unsafe", [
    'const data = {"raw_input":' + '"一项用来测试的任务"}',
    "sk-" + "a" * 32, "/Users/" + "example/private", "//#" + " sourceMappingURL=a.map",
    'DEEPSEEK_API_KEY="' + ("s" * 18) + '"',
])
def test_sensitive_content_is_rejected_with_redacted_output(build, unsafe):
    with (build / "assets" / "index-87654321.js").open("a", encoding="utf-8") as handle:
        handle.write("\n" + unsafe)
    errors = release.check_release(build)[1]
    assert errors and all(unsafe not in message for message in errors)


def test_image_metadata_is_rejected_even_if_in_reviewed_asset(build, monkeypatch):
    path = build / "icon-192.png"
    original = path.read_bytes()
    text = b"Author\0test"
    chunk = struct.pack(">I", len(text)) + b"tEXt" + text + struct.pack(">I", zlib.crc32(b"tEXt" + text))
    path.write_bytes(original[:-12] + chunk + original[-12:])
    monkeypatch.setattr(release, "PUBLIC", build)
    assert any("metadata" in error for error in release.check_release(build)[1])
