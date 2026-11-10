"""Import the retired prototype database into the target domain model."""

from __future__ import annotations

import json
import sqlite3

from sqlalchemy import select

from .services import (
    business_key_for,
    ensure_fact_catalog,
    fact_audit_snapshot,
    replace_fact_details,
    replace_fact_tags,
    schema_for,
)
from .workbench_database import ROOT, SessionLocal
from .workbench_models import (
    FactAuditEvent,
    FactRecord,
    RequirementProfile,
    Template,
    TemplatePreference,
    User,
    Workspace,
)


LEGACY_PATH = ROOT / "data" / "profile.db"
REPORT_PATH = ROOT / "data" / "migration-report.json"


def legacy_rows(connection: sqlite3.Connection, table: str):
    return connection.execute(f"SELECT * FROM {table}").fetchall()


def collect(row: sqlite3.Row, fields: list[str]) -> dict:
    return {
        field: row[field]
        for field in fields
        if field in row.keys() and row[field] not in (None, "")
    }


def experience_values(values: dict) -> dict:
    result = dict(values)
    raw = str(result.pop("kind", "") or "")
    result["experience_kind"] = {
        "竞赛": "competition",
        "比赛": "competition",
        "科研项目": "research",
        "科研": "research",
        "实习": "work_internship",
        "工作": "work_internship",
        "课程设计": "project",
        "课程项目": "project",
    }.get(raw, "project")
    return result


def row_tags(row: sqlite3.Row) -> list[str]:
    if "tags" not in row.keys() or not row["tags"]:
        return []
    try:
        value = json.loads(row["tags"])
        return [str(item) for item in value] if isinstance(value, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def import_legacy() -> dict:
    if not LEGACY_PATH.exists():
        raise RuntimeError(f"找不到原型数据库：{LEGACY_PATH}")
    source = sqlite3.connect(LEGACY_PATH)
    source.row_factory = sqlite3.Row
    report = {
        "source": str(LEGACY_PATH),
        "facts": 0,
        "profiles": 0,
        "templates": 0,
        "skipped": [],
        "legacy_resumes": "未迁移：原型缺少完整来源与不可变版本快照",
    }
    try:
        with SessionLocal() as db:
            if db.scalar(select(Workspace.id).limit(1)):
                report["status"] = "already_imported"
                return report
            ensure_fact_catalog(db)
            user = User(display_name="本地用户")
            db.add(user)
            db.flush()
            space = Workspace(owner_id=user.id, name="我的简历工作区")
            db.add(space)
            db.flush()
            tables = {
                "profiles": (
                    "basics",
                    "name",
                    [
                        "name",
                        "phone",
                        "email",
                        "city",
                        "desired_city",
                        "identity_status",
                        "graduation_date",
                        "availability",
                        "bio",
                    ],
                ),
                "educations": (
                    "education",
                    "school",
                    ["school", "major", "degree", "period_text", "achievement", "courses"],
                ),
                "experiences": (
                    "experience",
                    "title",
                    [
                        "experience_kind",
                        "period_text",
                        "organization",
                        "role",
                        "context_summary",
                        "work_summary",
                        "tools_summary",
                        "result_summary",
                        "challenge",
                        "solution",
                        "public_note",
                    ],
                ),
                "skills": (
                    "skill",
                    "name",
                    ["proficiency", "usage_context"],
                ),
                "awards": (
                    "achievement",
                    "title",
                    ["achievement_kind", "period_text", "issuer", "result_text", "note"],
                ),
            }
            for table, (category, title_field, fields) in tables.items():
                for row in legacy_rows(source, table):
                    verified = (
                        bool(row["is_verified"])
                        if "is_verified" in row.keys()
                        else True
                    )
                    values = collect(row, fields)
                    if category == "experience":
                        source_values = collect(
                            row,
                            [
                                "kind",
                                "period",
                                "organization",
                                "role",
                                "context",
                                "work",
                                "tools",
                                "outcome",
                                "challenge",
                                "solution",
                                "public_note",
                            ],
                        )
                        values.update(experience_values(source_values))
                    elif category == "education":
                        legacy_period = collect(row, ["period"]).get("period")
                        if legacy_period:
                            values["period_text"] = legacy_period
                    elif category == "skill":
                        values.setdefault("usage_context", "")
                    elif category == "achievement":
                        values.setdefault("achievement_kind", "honor")
                    schema = schema_for(db, category)
                    title = str(row[title_field] or category)
                    item = FactRecord(
                        workspace_id=space.id,
                        category_code=category,
                        schema_version_id=schema.id,
                        title=title,
                        business_key=business_key_for(category, title, values),
                        status="active" if verified else "archived",
                        source_note=(
                            row["source_ref"]
                            if "source_ref" in row.keys() and row["source_ref"]
                            else "原型数据库"
                        ),
                    )
                    db.add(item)
                    db.flush()
                    replace_fact_details(db, item, values)
                    replace_fact_tags(db, space.id, item.id, row_tags(row))
                    db.add(
                        FactAuditEvent(
                            workspace_id=space.id,
                            fact_id=item.id,
                            actor_user_id=user.id,
                            action="created",
                            schema_version_id=schema.id,
                            changed_fields='["import"]',
                            after_values=json.dumps(
                                fact_audit_snapshot(db, item),
                                ensure_ascii=False,
                            ),
                            reason="从原型数据库导入",
                        )
                    )
                    report["facts"] += 1

            for row in legacy_rows(source, "job_targets"):
                db.add(
                    RequirementProfile(
                        workspace_id=space.id,
                        name=row["name"],
                        role_direction=row["name"],
                        core_requirements=row["tags"] or "[]",
                        raw_jd=row["description"] or "",
                        source_note=row["company"] or "原型数据库",
                    )
                )
                report["profiles"] += 1

            first_template: Template | None = None
            for row in legacy_rows(source, "resume_templates"):
                template = Template(
                    template_key=row["slug"],
                    display_name=row["name"],
                    description=row["description"] or "",
                    renderer_key=row["slug"],
                    status="available",
                )
                db.add(template)
                db.flush()
                first_template = first_template or template
                report["templates"] += 1
            if first_template:
                db.add(
                    TemplatePreference(
                        workspace_id=space.id,
                        default_template_id=first_template.id,
                    )
                )
            db.commit()
            report["status"] = "imported"
            return report
    finally:
        source.close()
        REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    print(json.dumps(import_legacy(), ensure_ascii=False, indent=2))
