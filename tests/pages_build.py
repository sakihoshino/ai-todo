"""Serve production artifacts under a repository subpath, without FastAPI."""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
from threading import Thread


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
SUBPATH = "/AI-Todo/"


def build_pages(output, *flags):
    subprocess.run(
        ["npm", "run", "build", "--", "--outDir", str(output), *flags],
        cwd=FRONTEND, env={**os.environ, "PAGES_BASE_PATH": SUBPATH}, check=True,
    )


class StaticFiles(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


@contextmanager
def serve_pages(root):
    handler = partial(StaticFiles, directory=str(root))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as httpd:
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_port}{SUBPATH}"
        finally:
            httpd.shutdown()
            thread.join()
