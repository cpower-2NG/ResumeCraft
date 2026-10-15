"""Repair legacy-format resume working copies.

Working copies created by earlier builds stored fact blocks without structured
``fields`` and concatenated the ``brief`` summary into ``content``. This script
rebuilds every fact-derived block that is still in the old format from the
authoritative fact record (same logic as ``fact_to_block``), keeping blocks the
user edited afterwards (``origin`` != "fact") and blocks already in the new
format untouched. Versions are immutable and are never modified.

``repair_content`` is the in-memory half of that rule: it rebuilds a content
document and returns per-kind counts without touching the database, so other
tooling (e.g. the layout sample generator) can render the repaired view instead
of the flattened snapshot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.services import dump, fact_to_block, json_value
from app.workbench_database import SessionLocal
from app.workbench_models import FactRecord, RequirementProfile, ResumeIdentity, ResumeWorkingCopy


def repair_content(db, identity, content: dict) -> dict:
    """Rebuild legacy fact blocks inside ``content`` in place; return per-kind counts.

    Touches no database rows: callers own the document and decide whether to
    persist it (``repair`` below does; the sample generator does not).
    """
    counts = {"repaired_blocks": 0, "skipped_user_blocks": 0, "missing_facts": 0}
    profile = db.get(RequirementProfile, identity.requirement_profile_id)
    for section in content.get("sections", []):
        for block in section.get("blocks", []):
            if section["id"] == "target" and profile:
                # 求职目标 is always derived from the profile: rebuild it so the
                # block title carries the role direction instead of duplicating
                # the section heading.
                requirements = json_value(profile.core_requirements, [])
                block["title"] = profile.role_direction or profile.name or "求职目标"
                block["content"] = block.get("content") if block.get("origin") == "user" and block.get("content") not in (None, "", "请填写与目标岗位匹配的简历强调方向。") else (profile.resume_strategy or "")
                block["fields"] = {"role_direction": profile.role_direction, "core_requirements": "、".join(requirements)}
                block["field_labels"] = {"role_direction": "岗位方向", "core_requirements": "核心要求"}
                block["display_fields"] = [key for key, value in block["fields"].items() if value]
                counts["repaired_blocks"] += 1
                continue
            fact_ids = [fid for fid in block.get("source_refs", []) if isinstance(fid, int)]
            if not fact_ids or block.get("fields"):
                continue  # new-format or non-fact block
            if block.get("origin") == "user":
                counts["skipped_user_blocks"] += 1
                continue
            fact = db.get(FactRecord, fact_ids[0])
            if not fact:
                counts["missing_facts"] += 1
                continue
            rebuilt = fact_to_block(db, fact, section["id"])
            block["title"] = rebuilt["title"]
            block["content"] = rebuilt["content"]
            block["fields"] = rebuilt["fields"]
            block["field_labels"] = rebuilt["field_labels"]
            block["display_fields"] = rebuilt["display_fields"]
            block["origin"] = "fact"
            counts["repaired_blocks"] += 1
    return counts


def repair() -> dict:
    report = {"resumes": 0, "repaired_blocks": 0, "skipped_user_blocks": 0, "missing_facts": 0, "details": []}
    with SessionLocal() as db:
        identities = db.scalars(select(ResumeIdentity)).all()
        for identity in identities:
            copy = db.scalar(select(ResumeWorkingCopy).where(ResumeWorkingCopy.resume_identity_id == identity.id))
            if not copy:
                continue
            content = json_value(copy.content, {})
            counts = repair_content(db, identity, content)
            if counts["repaired_blocks"]:
                copy.content = dump(content)
                report["resumes"] += 1
                report["details"].append({"resume_id": identity.id, "display_name": identity.display_name})
            report["repaired_blocks"] += counts["repaired_blocks"]
            report["skipped_user_blocks"] += counts["skipped_user_blocks"]
            report["missing_facts"] += counts["missing_facts"]
        db.commit()
    return report


if __name__ == "__main__":
    print(json.dumps(repair(), ensure_ascii=False, indent=2))
