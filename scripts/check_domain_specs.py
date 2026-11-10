"""Validate living-domain documents and executable SQLite contracts."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOMAIN = DOCS / "domain"

LIVING_DOCS = [
    DOCS / "functional-design.md",
    DOCS / "interaction-design.md",
    DOCS / "technical-design.md",
    DOCS / "resource-library" / "design.md",
    DOMAIN / "job-profile" / "design.md",
    DOMAIN / "resume" / "design.md",
    DOMAIN / "rendering-delivery" / "design.md",
    DOMAIN / "system-map.md",
]

HISTORICAL_DOCS = [
    DOCS / "release-notes.md",
    DOCS / "investigation-log-2026-09-13.md",
    DOCS / "revision-audit.md",
    DOCS / "ui-audit-2026-09-12.md",
    DOCS / "gui-test-report-2026-10-31.md",
    DOCS / "resource-library" / "data-reorganization-2026-11-02.md",
    DOCS / "resource-library" / "data-reorganization-2026-11-09.md",
    DOCS / "resource-library" / "data-correction-2026-11-09.md",
]

MODULE_SPECS = {
    "JP": DOMAIN / "job-profile",
    "RS": DOMAIN / "resume",
    "RD": DOMAIN / "rendering-delivery",
}

SCHEMA_FILES = [
    DOMAIN / "job-profile" / "schema.sql",
    DOMAIN / "resume" / "schema.sql",
    DOMAIN / "rendering-delivery" / "schema.sql",
]

BASE_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL
) STRICT;
CREATE TABLE workspaces (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL
) STRICT;
CREATE TABLE fact_records (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    title TEXT NOT NULL,
    UNIQUE (workspace_id, id)
) STRICT;
CREATE TABLE evidence (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    title TEXT NOT NULL,
    UNIQUE (workspace_id, id)
) STRICT;
"""

ID_RE = re.compile(r"\b(JP|RS|RD|SYS|CAP)-[A-Z]+-\d{3}\b")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HASH = "a" * 64


def load_target_schema() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(BASE_SCHEMA_SQL)
    for path in SCHEMA_FILES:
        connection.executescript(path.read_text(encoding="utf-8"))
    return connection


def seed_workspace(connection: sqlite3.Connection, workspace_id: int = 1) -> None:
    connection.execute(
        "INSERT INTO users(id, display_name) VALUES (?, ?)",
        (workspace_id, f"user-{workspace_id}"),
    )
    connection.execute(
        "INSERT INTO workspaces(id, owner_id, name) VALUES (?, ?, ?)",
        (workspace_id, workspace_id, f"workspace-{workspace_id}"),
    )


def create_profile(
    connection: sqlite3.Connection,
    *,
    workspace_id: int = 1,
    name: str = "机器人工程师",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO requirement_profiles(workspace_id, name, role_direction)
        VALUES (?, ?, '机器人工程')
        """,
        (workspace_id, name),
    )
    return int(cursor.lastrowid)


def create_opportunity(
    connection: sqlite3.Connection,
    profile_id: int,
    *,
    workspace_id: int = 1,
    company: str = "示例公司",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO job_opportunities(
            workspace_id, requirement_profile_id, company, title, raw_jd
        ) VALUES (?, ?, ?, '机器人工程师', '岗位职责')
        """,
        (workspace_id, profile_id, company),
    )
    return int(cursor.lastrowid)


def create_template(connection: sqlite3.Connection, key: str = "classic") -> int:
    cursor = connection.execute(
        """
        INSERT INTO templates(template_key, display_name, renderer_key)
        VALUES (?, ?, ?)
        """,
        (key, key.title(), f"renderer:{key}"),
    )
    return int(cursor.lastrowid)


def create_draft(
    connection: sqlite3.Connection,
    profile_id: int,
    template_id: int,
    *,
    workspace_id: int = 1,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO linked_resumes(
            workspace_id, requirement_profile_id, template_id
        ) VALUES (?, ?, ?)
        """,
        (workspace_id, profile_id, template_id),
    )
    return int(cursor.lastrowid)


def create_resume(
    connection: sqlite3.Connection,
    profile_id: int,
    template_id: int,
    *,
    workspace_id: int = 1,
    origin_draft_id: int | None = None,
    status: str = "active",
    display_name: str = "正式简历",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO resumes(
            workspace_id, requirement_profile_id, origin_linked_resume_id,
            template_id, display_name, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, profile_id, origin_draft_id, template_id, display_name, status),
    )
    return int(cursor.lastrowid)


def create_version(
    connection: sqlite3.Connection,
    resume_id: int,
    *,
    workspace_id: int = 1,
    version_number: int = 1,
    reason: str = "format_conversion",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO resume_versions(
            workspace_id, resume_id, version_number, content_json,
            profile_snapshot_json, profile_snapshot_hash,
            source_manifest_json, evidence_manifest_json,
            content_hash, reason
        ) VALUES (?, ?, ?, '{}', '{}', ?, '[]', '[]', ?, ?)
        """,
        (workspace_id, resume_id, version_number, HASH, HASH, reason),
    )
    return int(cursor.lastrowid)


def create_working_copy(
    connection: sqlite3.Connection,
    resume_id: int,
    version_id: int,
    template_id: int,
    *,
    workspace_id: int = 1,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO resume_working_copies(
            workspace_id, resume_id, base_version_id, template_id, content_json
        ) VALUES (?, ?, ?, ?, '{}')
        """,
        (workspace_id, resume_id, version_id, template_id),
    )
    return int(cursor.lastrowid)


def validate_documents() -> list[str]:
    errors: list[str] = []
    required = [
        ROOT / "README.md",
        DOCS / "README.md",
        DOCS / "capabilities.md",
        DOCS / "domain" / "system-map.md",
        DOCS / "resource-library" / "design.md",
        DOCS / "resource-library" / "schema.sql",
        DOCS / "resource-library" / "diagrams-zh.md",
    ]
    for module_dir in MODULE_SPECS.values():
        required.extend(
            module_dir / name
            for name in ("design.md", "schema.sql", "diagrams-zh.md")
        )
    for path in required:
        if not path.exists():
            errors.append(f"missing document: {path.relative_to(ROOT)}")

    for path in LIVING_DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "living-design" not in text:
            errors.append(f"{path.relative_to(ROOT)} missing living-design status")

    for path in HISTORICAL_DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "历史快照，不作为现行规范" not in text:
            errors.append(f"{path.relative_to(ROOT)} missing historical banner")

    for path in sorted(set(required + LIVING_DOCS + HISTORICAL_DOCS)):
        if not path.exists():
            continue
        for target in MARKDOWN_LINK_RE.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative_target = target.split("#", 1)[0]
            if relative_target and not (path.parent / relative_target).resolve().exists():
                errors.append(
                    f"{path.relative_to(ROOT)} has broken link: {target}"
                )
        if path.suffix == ".md" and path.read_text(encoding="utf-8").count("```") % 2:
            errors.append(f"{path.relative_to(ROOT)} has unbalanced code fences")

    for path in (DOCS / "functional-design.md", DOCS / "interaction-design.md"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("ResumeIdentity", "identity_key", "来源侧栏"):
            if forbidden in text:
                errors.append(
                    f"{path.relative_to(ROOT)} contains non-current term: {forbidden}"
                )

    for prefix, module_dir in MODULE_SPECS.items():
        schema = (module_dir / "schema.sql").read_text(encoding="utf-8")
        design = (module_dir / "design.md").read_text(encoding="utf-8")
        diagrams = (module_dir / "diagrams-zh.md").read_text(encoding="utf-8")
        schema_tokens = set(
            re.findall(rf"\b{prefix}-[A-Z]+-\d{{3}}\b", schema)
        )
        design_tokens = set(
            re.findall(rf"\b{prefix}-[A-Z]+-\d{{3}}\b", design)
        )
        missing_design = sorted(schema_tokens - design_tokens)
        if missing_design:
            errors.append(
                f"{module_dir.name} schema IDs absent from design: {missing_design}"
            )
        if not schema_tokens:
            errors.append(f"{module_dir.name} schema has no stable IDs")
        if "erDiagram" in diagrams or "||--" in diagrams or "}o--" in diagrams:
            errors.append(f"{module_dir.name} diagrams contain crow's-foot syntax")
        for line in diagrams.splitlines():
            if ("-->" in line or "<-->" in line) and "|" in line:
                label = line.split("|", 2)
                if len(label) < 2 or ":" not in label[1]:
                    errors.append(
                        f"{module_dir.name} relation lacks cardinality: {line.strip()}"
                    )

    capabilities = (DOCS / "capabilities.md").read_text(encoding="utf-8")
    if not re.search(r"\bCAP-[A-Z]+-\d{3}\b", capabilities):
        errors.append("capability matrix has no CAP IDs")
    for status in ("implemented", "target", "deferred"):
        if f"| {status} |" not in capabilities:
            errors.append(f"capability matrix missing status: {status}")
    return errors


def validate_schema() -> list[str]:
    connection = load_target_schema()
    try:
        errors: list[str] = []
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            errors.append("foreign keys are not enabled")
        required_tables = {
            "requirement_profiles",
            "job_opportunities",
            "profile_audit_events",
            "linked_resumes",
            "resumes",
            "resume_versions",
            "resume_working_copies",
            "resume_fact_uses",
            "resume_version_fact_snapshots",
            "resume_evidence_uses",
            "resume_version_evidence_snapshots",
            "pending_issues",
            "templates",
            "workspace_template_preferences",
            "export_events",
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        missing = sorted(required_tables - tables)
        if missing:
            errors.append(f"missing target tables: {', '.join(missing)}")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            errors.append(f"foreign key check failed: {foreign_key_errors}")
        return errors
    finally:
        connection.close()


def validate() -> list[str]:
    return validate_documents() + validate_schema()


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "Domain specs OK: 3 modules, 3 SQL contracts, "
        f"{len(HISTORICAL_DOCS)} historical documents, "
        "living/historical status checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
