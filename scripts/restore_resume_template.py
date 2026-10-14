"""Put a dev resume back on a template after the canvas tooling switched it.

`web/scripts/inspect_canvas.mjs` and `audit_canvas_contrast.mjs` switch a resume's
template to walk the library, which mutates the local dev database. This restores it
through the public API so the working copy and version rules stay intact.

Usage: python scripts/restore_resume_template.py <resume_id> <template_slug>
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
resume_id, slug = int(sys.argv[1]), sys.argv[2]

templates = json.load(urllib.request.urlopen(f"{BASE}/api/templates"))
match = next((item for item in templates if item["slug"] == slug), None)
if not match:
    raise SystemExit(f"画廊里没有模板 {slug}；现有：{', '.join(item['slug'] for item in templates)}")

request = urllib.request.Request(
    f"{BASE}/api/resumes/{resume_id}/template",
    data=json.dumps({"template_version_id": match["template_version_id"]}).encode(),
    headers={"Content-Type": "application/json"},
    method="PATCH",
)
with urllib.request.urlopen(request) as response:
    print(f"resume {resume_id} → {match['name']}（HTTP {response.status}）")
