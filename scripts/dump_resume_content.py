"""Dump the saved content of one resume version so rendering defects can be traced
to the data that produced them (empty sections, inline field labels, etc.).

Usage: python scripts/dump_resume_content.py [identity_id] [version_number]
"""
import json
import sqlite3
import sys

DB = "data/resume_workbench.db"
identity_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

connection = sqlite3.connect(DB)
connection.row_factory = sqlite3.Row
row = connection.execute(
    "select version_number, content from resume_versions where resume_identity_id=? order by version_number desc limit 1",
    (identity_id,),
).fetchone()
content = json.loads(row["content"])
print(f"resume {identity_id} v{row['version_number']}")
for section in content.get("sections", []):
    blocks = section.get("blocks") or []
    print(f"\n[{section['id']}] {section['title']} blocks={len(blocks)}")
    for block in blocks:
        fields = {key: value for key, value in (block.get("fields") or {}).items() if value}
        print(f"  - title={block.get('title')!r} display={block.get('display_fields')}")
        print(f"    fields={json.dumps(fields, ensure_ascii=False)}")
        print(f"    content={block.get('content')!r}")
