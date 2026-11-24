"""Check the static Pages artifact before uploading it. Never print matched content."""
import argparse
from pathlib import Path
import re
import stat
import struct
import sys
import zlib

PUBLIC = Path(__file__).resolve().parents[1] / "frontend" / "public"
PUBLIC_FILES = {"apple-touch-icon.png", "desk-note.webp", "favicon.svg", "icon-192.png", "icon-512.png"}
ROOT_FILES = PUBLIC_FILES | {"index.html", "manifest.webmanifest", "registerSW.js", "sw.js"}
BUNDLES = {
    "application script": re.compile(r"assets/index-[\w-]{8,64}\.js", re.ASCII),
    "stylesheet": re.compile(r"assets/index-[\w-]{8,64}\.css", re.ASCII),
    "workbox": re.compile(r"workbox-[0-9a-f]{8,64}\.js"),
}
SENSITIVE = {
    "provider credential": re.compile(
        r"\b(?:sk-(?:proj-)?[a-zA-Z0-9_-]{16,}|gh[pousr]_[a-zA-Z0-9_]{30,}|"
        r"github_pat_[a-zA-Z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,}|xox[baprs]-[\w-]{20,})"
    ),
    "private key material": re.compile(r"-----BEGIN (?:[\w-]+ )*PRIVATE KEY-----"),
    "embedded credential": re.compile(
        r"""(?ix)\b(?:DEEPSEEK_API_KEY|GITHUB_TOKEN|API_?KEY|ACCESS_?TOKEN|PASSWORD)["']?\s*[:=]\s*["'][^"'\s]{8,}["']"""
    ),
    "local home path": re.compile(r"(?:/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\+Users\\+)", re.I),
    "embedded task input": re.compile(r"""(?:["']raw_input["']|\braw_input)\s*:\s*["'][^"'\s]"""),
    "literal bearer credential": re.compile(r"""(?i)\bBearer\s+[a-z0-9._-]{16,}"""),
    "credential in URL": re.compile(r"https?://[^/\s:@]{1,100}:[^/\s@]{1,100}@"),
    "source map": re.compile(r"(?://|/\*)[#@]\s*sourceMappingURL\s*="),
}


def image_is_public(data: bytes, suffix: str) -> bool:
    """Permit pixel/color chunks only; arbitrary text, EXIF and trailing payloads fail."""
    if suffix == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return False
        position = 8
        while position + 12 <= len(data):
            size, kind = struct.unpack_from(">I4s", data, position)
            end = position + 12 + size
            if end > len(data) or kind not in {
                b"IHDR", b"IDAT", b"IEND", b"PLTE", b"tRNS", b"bKGD", b"cHRM", b"sRGB", b"gAMA", b"pHYs",
            }:
                return False
            crc = int.from_bytes(data[end - 4:end], "big")
            if zlib.crc32(data[position + 4:end - 4]) != crc:
                return False
            if kind == b"IEND":
                return size == 0 and end == len(data)
            position = end
        return False
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP" or int.from_bytes(data[4:8], "little") + 8 != len(data):
        return False
    position = 12
    has_pixels = False
    while position + 8 <= len(data):
        kind, size = struct.unpack_from("<4sI", data, position)
        if kind not in {b"VP8 ", b"VP8L", b"VP8X", b"ALPH"}:
            return False
        has_pixels |= kind in {b"VP8 ", b"VP8L"}
        position += 8 + size + size % 2
    return has_pixels and position == len(data)


def check_release(root: Path) -> tuple[int, list[str]]:
    if root.is_symlink() or not root.is_dir():
        return 0, ["expected a regular build directory"]
    errors: list[str] = []
    files: dict[str, bytes] = {}
    # Traverse only the expected directories. Even nested, hidden and empty extras are rejected.
    for parent in [root, root / "assets"]:
        if parent.is_symlink() or not parent.is_dir():
            errors.append("missing or linked assets directory")
            continue
        for path in parent.iterdir():
            if path == root / "assets":
                continue
            name = path.relative_to(root).as_posix()
            if name not in ROOT_FILES and not any(regex.fullmatch(name) for regex in BUNDLES.values()):
                errors.append(f"unexpected file or directory in {'.' if parent == root else 'assets'}")
                continue
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                errors.append(f"{name}: expected one regular file, without links")
                continue
            data = path.read_bytes()
            files[name] = data
            if name in PUBLIC_FILES and data != (PUBLIC / name).read_bytes():
                errors.append(f"{name}: differs from the reviewed public asset")
            if path.suffix in {".png", ".webp"}:
                if not image_is_public(data, path.suffix):
                    errors.append(f"{name}: disallowed media metadata or invalid image")
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{name}: expected UTF-8 text")
                continue
            if "\x00" in content:
                errors.append(f"{name}: unexpected binary data")
            for category, pattern in SENSITIVE.items():
                if pattern.search(content):
                    errors.append(f"{name}: found {category}")
    for missing in sorted(ROOT_FILES - files.keys()):
        errors.append(f"missing {missing}")
    for label, pattern in BUNDLES.items():
        matches = [name for name in files if pattern.fullmatch(name)]
        if len(matches) != 1:
            errors.append(f"expected exactly one {label}")
            continue
        name = matches[0]
        if label == "workbox":
            if name[:-3].encode() not in files.get("sw.js", b""):
                errors.append("service worker does not reference the supplied workbox script")
        elif name.encode() not in files.get("index.html", b""):
            errors.append(f"index.html does not reference the supplied {label}")
    return len(files), errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=PUBLIC.parent / "dist-local")
    try:
        count, errors = check_release(parser.parse_args().directory)
    except OSError:
        sys.exit("Release blocked: unable to read static build or reference assets.")
    if errors:
        sys.exit("Release blocked:\n" + "\n".join("- " + error for error in errors))
    print(f"Release check passed: {count} expected static files.")
