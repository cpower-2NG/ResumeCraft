import io
import sys

sys.path.insert(0, ".")
from app.templates import BUILTIN_TEMPLATES

print("registry size:", len(BUILTIN_TEMPLATES))
s = io.open("scripts/gen_samples.py", encoding="utf-8").read()
for line in s.splitlines():
    if "samples" in line and "=" in line and "def" not in line:
        print("samples:", line.strip())
    if "for slug" in line or "for name" in line:
        print("loop:", line.strip())
