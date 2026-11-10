"""Validate the SQL-first resource-library specification.

The checker is intentionally read-only with respect to application data. It
loads the target DDL into an in-memory SQLite database, verifies the seeded
registries, and checks that stable IDs and the current-data audit agree.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "docs" / "resource-library"
SCHEMA_PATH = SPEC_DIR / "schema.sql"
DESIGN_PATH = SPEC_DIR / "design.md"
AUDIT_PATH = SPEC_DIR / "data-reorganization-2026-11-02.md"
DIAGRAM_PATH = SPEC_DIR / "diagrams-zh.md"
SNAPSHOT_HASH = "74f3238a8e91a2d965be89add4810d2f6a2d51a756a44e7a6eadcb434bb733f6"
SNAPSHOT_ALEMBIC = "0008_domain_integrity_guards"

ID_RE = re.compile(r"\bRL-(ENT|FLD|REL|STS|INV|CMD|DEC|DAT)-(\d{3})\b")

EXPECTED_RANGES = {
    "ENT": range(1, 30),
    "FLD": range(1, 51),
    "REL": range(1, 20),
    "STS": range(1, 6),
    "INV": range(1, 22),
    "CMD": range(1, 10),
    "DEC": range(1, 14),
}

EXPECTED_TABLES = {
    "users",
    "workspaces",
    "fact_categories",
    "fact_schema_versions",
    "fact_field_definitions",
    "fact_records",
    "fact_basics_details",
    "fact_education_details",
    "fact_experience_details",
    "skill_groups",
    "fact_skill_details",
    "fact_achievement_details",
    "fact_extension_values",
    "tags",
    "tag_aliases",
    "fact_tags",
    "evidence",
    "fact_evidence",
    "profile_photos",
    "fact_audit_events",
    "evidence_audit_events",
    "experience_skill_links",
    "resumes",
    "resume_versions",
    "resume_fact_uses",
    "resume_version_fact_snapshots",
    "resume_evidence_uses",
    "resume_version_evidence_snapshots",
}


def ids_in(text: str) -> set[str]:
    return {match.group(0) for match in ID_RE.finditer(text)}


def load_schema() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def check_schema(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing = sorted(EXPECTED_TABLES - tables)
    extra = sorted(tables - EXPECTED_TABLES)
    if missing:
        errors.append(f"missing tables: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected tables: {', '.join(extra)}")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        errors.append("foreign_keys is not enabled")
    expected_categories = {"basics", "education", "experience", "skill", "achievement"}
    categories = {
        row[0] for row in connection.execute("SELECT code FROM fact_categories")
    }
    if categories != expected_categories:
        errors.append(f"category registry mismatch: {sorted(categories)}")
    schema_count = connection.execute("SELECT count(*) FROM fact_schema_versions").fetchone()[0]
    if schema_count != 5:
        errors.append(f"expected 5 schema versions, got {schema_count}")
    field_count = connection.execute("SELECT count(*) FROM fact_field_definitions").fetchone()[0]
    if field_count != 46:
        errors.append(f"expected 46 field definitions, got {field_count}")
    extension_count = connection.execute(
        "SELECT count(*) FROM fact_field_definitions WHERE is_extension = 1"
    ).fetchone()[0]
    if extension_count:
        errors.append("version 1 should not invent extension fields")
    bad_details = connection.execute(
        """
        SELECT f.id
          FROM fact_records f
          LEFT JOIN fact_basics_details b ON b.fact_id = f.id
          LEFT JOIN fact_education_details e ON e.fact_id = f.id
          LEFT JOIN fact_experience_details x ON x.fact_id = f.id
          LEFT JOIN fact_skill_details s ON s.fact_id = f.id
          LEFT JOIN fact_achievement_details a ON a.fact_id = f.id
         WHERE (
                 f.status <> 'purged'
                 AND ((b.fact_id IS NOT NULL) + (e.fact_id IS NOT NULL)
                      + (x.fact_id IS NOT NULL) + (s.fact_id IS NOT NULL)
                      + (a.fact_id IS NOT NULL)) <> 1
               )
            OR (
                 f.status = 'purged'
                 AND ((b.fact_id IS NOT NULL) + (e.fact_id IS NOT NULL)
                      + (x.fact_id IS NOT NULL) + (s.fact_id IS NOT NULL)
                      + (a.fact_id IS NOT NULL)) <> 0
               )
        """
    ).fetchall()
    if bad_details:
        errors.append(f"facts with invalid typed-detail coverage: {[row[0] for row in bad_details]}")
    return errors


def check_ids() -> list[str]:
    errors: list[str] = []
    schema_ids = ids_in(SCHEMA_PATH.read_text(encoding="utf-8"))
    design_text = DESIGN_PATH.read_text(encoding="utf-8")
    design_ids = ids_in(design_text)
    audit_text = AUDIT_PATH.read_text(encoding="utf-8")
    audit_ids = ids_in(audit_text)

    orphan_schema_ids = sorted(schema_ids - design_ids)
    if orphan_schema_ids:
        errors.append(f"SQL IDs missing from design.md: {', '.join(orphan_schema_ids)}")

    for prefix, numbers in EXPECTED_RANGES.items():
        expected = {f"RL-{prefix}-{number:03d}" for number in numbers}
        missing = sorted(expected - design_ids)
        if missing:
            errors.append(f"design.md missing {prefix} IDs: {', '.join(missing)}")

    expected_data = {f"RL-DAT-{number:03d}" for number in range(1, 27)}
    if not expected_data <= audit_ids:
        missing = sorted(expected_data - audit_ids)
        errors.append(f"data audit missing IDs: {', '.join(missing)}")
    extra_data = sorted(
        value for value in audit_ids if value.startswith("RL-DAT-") and value not in expected_data
    )
    if extra_data:
        errors.append(f"data audit has unexpected IDs: {', '.join(extra_data)}")
    return errors


def check_audit_privacy() -> list[str]:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    phone_like = re.findall(r"(?<!\d)1[3-9]\d{9}(?!\d)", text)
    email_like = re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
    if phone_like:
        errors.append(f"data audit contains {len(phone_like)} phone-like value(s)")
    if email_like:
        errors.append(f"data audit contains {len(email_like)} email-like value(s)")
    return errors


def check_chinese_diagrams() -> list[str]:
    text = DIAGRAM_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    if "erDiagram" in text or "||--" in text or "}o--" in text:
        errors.append("Chinese diagram guide must not contain crow's-foot ER syntax")
    if text.count("```mermaid") < 3:
        errors.append("Chinese diagram guide must contain relation, boundary, and UML diagrams")
    if "左侧实体数量 : 右侧实体数量" not in text:
        errors.append("Chinese diagram guide must explain its cardinality reading")
    required_sections = (
        "公共身份与字典",
        "五类分类明细",
        "标签、证据和审计",
        "关联与简历边界",
    )
    missing = [heading for heading in required_sections if heading not in text]
    if missing:
        errors.append(f"Chinese diagram guide is missing field sections: {', '.join(missing)}")
    return errors


def check_source_snapshot() -> list[str]:
    """Check the frozen audit text, not the evolving local database.

    The reorganization audit is a dated safety snapshot. Once the application
    accepts user edits, comparing it to the live database would make a valid
    historical audit permanently fail for reasons unrelated to the design.
    """
    errors: list[str] = []
    text = AUDIT_PATH.read_text(encoding="utf-8")
    if SNAPSHOT_HASH not in text:
        errors.append(
            "dated reorganization audit does not contain its declared source hash"
        )
    if SNAPSHOT_ALEMBIC not in text:
        errors.append("dated reorganization audit does not record its source revision")
    return errors


def validate() -> list[str]:
    missing_files = [
        str(path.relative_to(ROOT))
        for path in (SCHEMA_PATH, DESIGN_PATH, AUDIT_PATH, DIAGRAM_PATH)
        if not path.exists()
    ]
    if missing_files:
        return [f"missing files: {', '.join(missing_files)}"]
    connection = load_schema()
    try:
        return (
            check_schema(connection)
            + check_ids()
            + check_audit_privacy()
            + check_chinese_diagrams()
            + check_source_snapshot()
        )
    finally:
        connection.close()


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    connection = load_schema()
    try:
        table_count = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        trigger_count = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'trigger'"
        ).fetchone()[0]
        field_count = connection.execute(
            "SELECT count(*) FROM fact_field_definitions"
        ).fetchone()[0]
    finally:
        connection.close()
    print(
        "Resource-library spec OK: "
        f"{table_count} tables, {trigger_count} triggers, {field_count} fields, "
        "26 audited facts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
