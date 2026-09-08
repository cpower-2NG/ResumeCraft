from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .workbench_models import FactRecord, RequirementProfile, ResumeFactReference


CORE_SECTIONS = [
    ("basics", "基本信息"), ("target", "求职目标"), ("profile", "个人简介"),
    ("education", "教育经历"), ("experience", "项目与实践"),
    ("skills", "技能"), ("awards", "成果"),
]


def json_value(value: str, default):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=lambda item: item.isoformat() if hasattr(item, "isoformat") else str(item))


def content_hash(content: dict) -> str:
    return hashlib.sha256(dump(content).encode("utf-8")).hexdigest()


def identity_key(profile: RequirementProfile) -> str:
    requirements = json_value(profile.core_requirements, [])
    normalized = sorted({str(item).strip().lower() for item in requirements if str(item).strip()})
    fields = [profile.role_direction, " ".join(normalized), profile.resume_strategy]
    return "|".join(re.sub(r"\s+", " ", (value or "").strip()).lower() for value in fields)


def fact_to_block(fact: FactRecord) -> dict:
    content = json_value(fact.content, {})
    plain = content.get("summary") or content.get("bio") or content.get("work") or content.get("achievement") or content.get("context") or ""
    metadata = [value for key, value in content.items() if key not in {"summary", "bio", "work", "achievement", "context"} and value]
    if metadata:
        plain = "\n".join([plain, " · ".join(str(v) for v in metadata[:3])]).strip()
    return {"id": f"fact-{fact.id}", "type": "fact", "title": fact.title, "content": plain, "source_refs": [fact.id], "origin": "fact"}


def build_resume_content(db: Session, profile: RequirementProfile, selection: dict) -> dict:
    facts = {item.id: item for item in db.query(FactRecord).filter(FactRecord.workspace_id == profile.workspace_id, FactRecord.status == "active").all()}
    sections = []
    for section_id, title in CORE_SECTIONS:
        selected_ids = selection.get(section_id, [])
        blocks = [fact_to_block(facts[fact_id]) for fact_id in selected_ids if fact_id in facts]
        if section_id == "target" and not blocks:
            blocks = [{"id": "target-profile", "type": "paragraph", "title": title, "content": profile.role_direction or profile.name, "source_refs": [], "origin": "user"}]
        sections.append({"id": section_id, "type": section_id, "title": title, "visibility": True, "blocks": blocks})
    return {"sections": sections}


def source_manifest(content: dict) -> list[dict]:
    items = []
    for section in content.get("sections", []):
        for block in section.get("blocks", []):
            for fact_id in block.get("source_refs", []):
                if isinstance(fact_id, int):
                    items.append({"fact_id": fact_id, "section_id": section["id"], "block_id": block["id"]})
    return items


def sync_references(db: Session, identity_id: int, content: dict) -> None:
    db.execute(delete(ResumeFactReference).where(ResumeFactReference.resume_identity_id == identity_id))
    for item in source_manifest(content):
        db.add(ResumeFactReference(resume_identity_id=identity_id, **item))


def serialize_fact(item: FactRecord) -> dict:
    return {"id": item.id, "category": item.category, "title": item.title, "content": json_value(item.content, {}), "tags": json_value(item.tags, []), "status": item.status, "source_note": item.source_note, "created_at": item.created_at, "updated_at": item.updated_at}


def serialize_profile(item: RequirementProfile) -> dict:
    return {"id": item.id, "name": item.name, "role_direction": item.role_direction, "core_requirements": json_value(item.core_requirements, []), "general_requirements": item.general_requirements, "responsibilities": item.responsibilities, "resume_strategy": item.resume_strategy, "raw_jd": item.raw_jd, "source_note": item.source_note, "identity_key": item.identity_key, "updated_at": item.updated_at}


def serialize_version(version) -> dict:
    return {"id": version.id, "version_number": version.version_number, "content": json_value(version.content, {}), "reason": version.reason, "change_summary": version.change_summary, "created_at": version.created_at}
