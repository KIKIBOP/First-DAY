"""Convenience wrapper; requires Node.js and npm install (Playwright). No external network requests."""
import subprocess
from pathlib import Path
raise SystemExit(subprocess.call(['node',str(Path(__file__).with_name('browser.cjs'))]))
