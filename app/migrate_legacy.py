"""Import the prototype database without modifying it."""
from __future__ import annotations

import hashlib
import json
import sqlite3

from sqlalchemy import select

from .services import dump, identity_key
from .workbench_database import ROOT, SessionLocal
from .workbench_models import FactAudit, FactRecord, RequirementProfile, ResumeTemplate, TemplateVersion, User, Workspace


LEGACY_PATH = ROOT / "data" / "profile.db"
REPORT_PATH = ROOT / "data" / "migration-report.json"


def legacy_rows(connection: sqlite3.Connection, table: str):
    return connection.execute(f"SELECT * FROM {table}").fetchall()


def collect(row: sqlite3.Row, fields: list[str]) -> dict:
    return {field: row[field] for field in fields if field in row.keys() and row[field] not in (None, "")}


def import_legacy() -> dict:
    if not LEGACY_PATH.exists():
        raise RuntimeError(f"找不到原型数据库：{LEGACY_PATH}")
    source = sqlite3.connect(LEGACY_PATH)
    source.row_factory = sqlite3.Row
    report = {"source": str(LEGACY_PATH), "facts": 0, "profiles": 0, "templates": 0, "skipped": [], "legacy_resumes": "未迁移：缺少完整来源和版本快照"}
    try:
        with SessionLocal() as db:
            if db.scalar(select(Workspace.id).limit(1)):
                report["status"] = "already_imported"
                return report
            user = User(display_name="本地用户")
            db.add(user); db.flush()
            space = Workspace(owner_id=user.id, name="我的简历工作区")
            db.add(space); db.flush()
            tables = {
                "profiles": ("basics", "name", ["name", "phone", "email", "city", "desired_city", "status", "graduation", "availability", "bio"]),
                "educations": ("education", "school", ["school", "major", "degree", "period", "achievement", "courses"]),
                "experiences": ("experience", "title", ["kind", "period", "organization", "role", "context", "work", "tools", "outcome", "challenge", "solution", "public_note"]),
                "skills": ("skills", "name", ["category", "proficiency", "context"]),
                "awards": ("awards", "title", ["period", "issuer", "result", "note"]),
            }
            for table, (category, title_field, fields) in tables.items():
                for row in legacy_rows(source, table):
                    verified = bool(row["is_verified"]) if "is_verified" in row.keys() else True
                    item = FactRecord(
                        workspace_id=space.id, category=category, title=row[title_field] or category,
                        content=dump(collect(row, fields)), tags=row["tags"] if "tags" in row.keys() and row["tags"] else "[]",
                        status="active" if verified else "archived",
                        source_note=row["source_ref"] if "source_ref" in row.keys() and row["source_ref"] else "原型数据库",
                    )
                    db.add(item); db.flush()
                    db.add(FactAudit(workspace_id=space.id, fact_id=item.id, action="imported", summary="从原型数据库导入", after_content=item.content))
                    report["facts"] += 1
            for row in legacy_rows(source, "job_targets"):
                profile = RequirementProfile(
                    workspace_id=space.id, name=row["name"], role_direction=row["name"],
                    core_requirements=row["tags"] or "[]", raw_jd=row["description"] or "",
                    source_note=row["company"] or "原型数据库", identity_key="",
                )
                profile.identity_key = identity_key(profile)
                db.add(profile); report["profiles"] += 1
            for row in legacy_rows(source, "resume_templates"):
                template = ResumeTemplate(workspace_id=space.id, name=row["name"], slug=row["slug"], description=row["description"] or "", active=True)
                db.add(template); db.flush()
                markup = row["content"]
                db.add(TemplateVersion(template_id=template.id, version_number=1, content=markup, checksum=hashlib.sha256(markup.encode("utf-8")).hexdigest()))
                report["templates"] += 1
            db.commit()
            report["status"] = "imported"
            return report
    finally:
        source.close()
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(import_legacy(), ensure_ascii=False, indent=2))
