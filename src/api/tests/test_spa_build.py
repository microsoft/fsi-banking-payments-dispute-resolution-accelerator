"""
test_spa_build.py

Checks that the React / TypeScript SPA builds without type errors.

The build script in src/web/package.json is:
    "build": "tsc --noEmit && vite build"

This test runs `npm run build` in src/web and asserts it exits 0.

If Node/npm is unavailable in this environment, the test is skipped with
a clear explanation (not marked xfail — a skip is more informative).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

import pytest

# ── Path resolution ───────────────────────────────────────────────────────────
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_API_DIR = os.path.dirname(_TESTS_DIR)
_SRC_DIR = os.path.dirname(_API_DIR)
_WEB_DIR = os.path.join(_SRC_DIR, "web")

# ── Skip guard ────────────────────────────────────────────────────────────────
_npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
_npm_available = shutil.which(_npm_cmd) is not None
_web_dir_exists = os.path.isdir(_WEB_DIR)

skip_no_npm = pytest.mark.skipif(
    not _npm_available,
    reason="npm not found on PATH — install Node.js to run SPA build checks",
)
skip_no_web = pytest.mark.skipif(
    not _web_dir_exists,
    reason=f"src/web directory not found at {_WEB_DIR}",
)


# ── Tests ─────────────────────────────────────────────────────────────────────

@skip_no_npm
@skip_no_web
class TestSpaBuild:
    def test_npm_run_build_exits_zero(self):
        """
        `npm run build` in src/web must exit 0.
        The build script runs `tsc --noEmit && vite build`, so any TypeScript
        type error or Vite build failure will cause a non-zero exit.
        """
        result = subprocess.run(
            [_npm_cmd, "run", "build"],
            cwd=_WEB_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"npm run build failed (exit {result.returncode}).\n"
            f"stdout:\n{result.stdout[-2000:] if result.stdout else '(empty)'}\n"
            f"stderr:\n{result.stderr[-2000:] if result.stderr else '(empty)'}"
        )

    def test_dist_directory_created(self):
        """Vite build must create a dist/ directory with at least one file."""
        dist_dir = os.path.join(_WEB_DIR, "dist")
        assert os.path.isdir(dist_dir), (
            f"Expected dist/ at {dist_dir} after build — run test_npm_run_build_exits_zero first"
        )
        dist_files = list(os.listdir(dist_dir))
        assert len(dist_files) > 0, "dist/ directory is empty after build"

    def test_dist_contains_index_html(self):
        """SPA build must produce an index.html entry point."""
        index_html = os.path.join(_WEB_DIR, "dist", "index.html")
        assert os.path.isfile(index_html), "dist/index.html not found after build"
