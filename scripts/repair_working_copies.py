"""Repair legacy-format resume working copies.

Working copies created by earlier builds stored fact blocks without structured
``fields`` and concatenated the ``brief`` summary into ``content``. This script
rebuilds every fact-derived block that is still in the old format from the
authoritative fact record (same logic as ``fact_to_block``), keeping blocks the
user edited afterwards (``origin`` != "fact") and blocks already in the new
format untouched. Versions are immutable and are never modified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.services import dump, fact_to_block, json_value
from app.workbench_database import SessionLocal
from app.workbench_models import FactRecord, ResumeIdentity, ResumeWorkingCopy


def repair() -> dict:
    report = {"resumes": 0, "repaired_blocks": 0, "skipped_user_blocks": 0, "missing_facts": 0, "details": []}
    with SessionLocal() as db:
        identities = db.scalars(select(ResumeIdentity)).all()
        for identity in identities:
            copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == identity.id))
            if not copy:
                continue
            content = json_value(copy.content, {})
            changed = False
            for section in content.get("sections", []):
                for block in section.get("blocks", []):
                    fact_ids = [fid for fid in block.get("source_refs", []) if isinstance(fid, int)]
                    if not fact_ids or block.get("fields"):
                        continue  # new-format or non-fact block
                    if block.get("origin") == "user":
                        report["skipped_user_blocks"] += 1
                        continue
                    fact = db.get(FactRecord, fact_ids[0])
                    if not fact:
                        report["missing_facts"] += 1
                        continue
                    rebuilt = fact_to_block(db, fact, section["id"])
                    block["title"] = rebuilt["title"]
                    block["content"] = rebuilt["content"]
                    block["fields"] = rebuilt["fields"]
                    block["field_labels"] = rebuilt["field_labels"]
                    block["display_fields"] = rebuilt["display_fields"]
                    block["origin"] = "fact"
                    changed = True
                    report["repaired_blocks"] += 1
            if changed:
                copy.content = dump(content)
                report["resumes"] += 1
                report["details"].append({"resume_id": identity.id, "display_name": identity.display_name})
        db.commit()
    return report


if __name__ == "__main__":
    print(json.dumps(repair(), ensure_ascii=False, indent=2))
