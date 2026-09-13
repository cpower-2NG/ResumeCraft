import os
import subprocess
import sys

GIT = os.path.join(os.environ["LOCALAPPDATA"], r"GitHubDesktop\app-3.5.8\resources\app\git\cmd\git.exe")

def run(*args):
    out = subprocess.run([GIT, *args], capture_output=True, text=True, encoding="utf-8", cwd=".")
    print(out.stdout)
    if out.returncode != 0:
        print("STDERR:", out.stderr)
        sys.exit(out.returncode)

run("add", "-A")
run("commit", "-m",
    "fix: restore sidebar main sections and rebuild pagination model on measured pixel heights\n\n"
    "- sidebar layouts (10 templates) duplicated skills/awards in main column after\n"
    "  the v1.0.7 layout-branch refactor; main stream is back to five sections\n"
    "- replace count-based block weights with pixel-height estimates derived from\n"
    "  the export CSS (content/meta line wrapping, per-section headers, per-entry\n"
    "  chrome for line/timeline) so long field values no longer overflow the A4 page\n"
    "- recalibrate per-layout budgets with headless-Chromium measurement over\n"
    "  26 templates x 3 density samples: zero overflow, first-page fill 77-92%\n"
    "- mirror the model in web/src/lib/resume.ts (streamItems gains layout param)\n"
    "- add calibration toolkit: scripts/gen_samples.py, scripts/summarize_metrics.py,\n"
    "  web/scripts/measure_pages.mjs")
run("log", "--oneline", "-2")
