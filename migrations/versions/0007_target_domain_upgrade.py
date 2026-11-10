"""Upgrade the legacy resume and delivery tables to the target domain model.

The migration builds new tables and copies data before replacing the legacy
tables, so a failure leaves the original transaction untouched. Resource
facts remain on their compatibility schema until the user-confirmed resource
reorganisation in docs/resource-library/data-reorganization-2026-11-02.md.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_target_domain_upgrade"
down_revision = "0006_working_copy_template"
branch_labels = None
depends_on = None


TEMPLATE_SQL = """
CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    template_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    renderer_key TEXT NOT NULL,
    supported_sections_json TEXT NOT NULL DEFAULT '[]',
    default_sections_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'retired')),
    successor_template_id INTEGER REFERENCES templates(id),
    updated_at TEXT NOT NULL
)
"""

LINKED_SQL = """
CREATE TABLE linked_resumes (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    requirement_profile_id INTEGER NOT NULL REFERENCES requirement_profiles(id),
    template_id INTEGER NOT NULL REFERENCES templates(id),
    selection_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'converted', 'abandoned')),
    converted_resume_id INTEGER UNIQUE REFERENCES resumes(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

RESUME_SQL = """
CREATE TABLE resumes (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    requirement_profile_id INTEGER NOT NULL REFERENCES requirement_profiles(id),
    origin_linked_resume_id INTEGER UNIQUE REFERENCES linked_resumes(id),
    template_id INTEGER NOT NULL REFERENCES templates(id),
    display_name TEXT NOT NULL,
    current_version_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    archived_at TEXT,
    recycled_at TEXT,
    purged_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

VERSION_SQL = """
CREATE TABLE resume_versions (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    content_json TEXT NOT NULL,
    source_manifest_json TEXT NOT NULL DEFAULT '[]',
    profile_snapshot_json TEXT NOT NULL,
    profile_snapshot_hash TEXT NOT NULL,
    evidence_manifest_json TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL,
    change_summary TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (resume_id, version_number)
)
"""

WORKING_SQL = """
CREATE TABLE resume_working_copies (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_id INTEGER NOT NULL UNIQUE REFERENCES resumes(id),
    base_version_id INTEGER REFERENCES resume_versions(id),
    template_id INTEGER NOT NULL REFERENCES templates(id),
    content_json TEXT NOT NULL,
    content_state TEXT NOT NULL DEFAULT 'clean'
        CHECK (content_state IN ('clean', 'dirty')),
    evidence_sync_state TEXT NOT NULL DEFAULT 'clean'
        CHECK (evidence_sync_state IN ('clean', 'pending', 'conflict')),
    baseline_state TEXT NOT NULL DEFAULT 'current'
        CHECK (baseline_state IN ('current', 'stale')),
    pending_reason TEXT,
    updated_at TEXT NOT NULL
)
"""

FACT_USE_SQL = """
CREATE TABLE resume_fact_uses (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    fact_id INTEGER NOT NULL REFERENCES fact_records(id),
    section_code TEXT NOT NULL,
    block_key TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    fact_content_hash TEXT NOT NULL DEFAULT '',
    UNIQUE (resume_id, fact_id, section_code, block_key)
)
"""

FACT_SNAPSHOT_SQL = """
CREATE TABLE resume_version_fact_snapshots (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_version_id INTEGER NOT NULL REFERENCES resume_versions(id),
    fact_id INTEGER NOT NULL REFERENCES fact_records(id),
    section_code TEXT NOT NULL,
    block_key TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    fact_content_hash TEXT NOT NULL DEFAULT '',
    UNIQUE (resume_version_id, fact_id, section_code, block_key)
)
"""

EVIDENCE_USE_SQL = """
CREATE TABLE resume_evidence_uses (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_id INTEGER NOT NULL REFERENCES resumes(id),
    evidence_id INTEGER NOT NULL REFERENCES evidence(id),
    section_code TEXT NOT NULL,
    block_key TEXT NOT NULL,
    display_mode TEXT NOT NULL DEFAULT 'reference',
    label TEXT NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (resume_id, evidence_id, section_code, block_key)
)
"""

EVIDENCE_SNAPSHOT_SQL = """
CREATE TABLE resume_version_evidence_snapshots (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    resume_version_id INTEGER NOT NULL REFERENCES resume_versions(id),
    evidence_id INTEGER NOT NULL REFERENCES evidence(id),
    section_code TEXT NOT NULL,
    block_key TEXT NOT NULL,
    display_mode TEXT NOT NULL DEFAULT 'reference',
    label TEXT NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (resume_version_id, evidence_id, section_code, block_key)
)
"""

PENDING_SQL = """
CREATE TABLE pending_issues (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL DEFAULT 'source_changed',
    status TEXT NOT NULL DEFAULT 'open',
    fact_id INTEGER REFERENCES fact_records(id),
    evidence_id INTEGER REFERENCES evidence(id),
    profile_id INTEGER REFERENCES requirement_profiles(id),
    resume_id INTEGER REFERENCES resumes(id),
    section_code TEXT NOT NULL DEFAULT '',
    block_key TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
)
"""


def _columns(table: str) -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_columns(table)
    }


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "fact_categories" in tables:
        return
    if "resumes" in tables:
        return
    if "resume_identities" not in tables:
        raise RuntimeError("legacy resume_identities table is missing")

    duplicates = bind.execute(
        sa.text(
            """
            SELECT workspace_id, requirement_profile_id, count(*) AS n
            FROM resume_identities
            WHERE status = 'active'
            GROUP BY workspace_id, requirement_profile_id
            HAVING count(*) > 1
            """
        )
    ).all()
    if duplicates:
        raise RuntimeError(
            "active Resume uniqueness cannot be established; resolve duplicate "
            f"profile/resume groups first: {duplicates}"
        )

    # Global template catalogue. Keep the old template tables as migration
    # history, but application reads only the stable template ID.
    op.execute(TEMPLATE_SQL)
    bind.execute(
        sa.text(
            """
            INSERT INTO templates(
                id, template_key, display_name, description, renderer_key,
                supported_sections_json, default_sections_json, status,
                successor_template_id, updated_at
            )
            SELECT
                min(id), slug, min(name), min(description), slug,
                '[]', '[]',
                CASE WHEN max(CASE WHEN active = 1 THEN 1 ELSE 0 END) = 1
                     THEN 'available' ELSE 'retired' END,
                NULL,
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            FROM resume_templates
            GROUP BY slug
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE TEMP TABLE template_version_map AS
            SELECT tv.id AS template_version_id, t.id AS template_id
            FROM template_versions tv
            JOIN resume_templates rt ON rt.id = tv.template_id
            JOIN templates t ON t.template_key = rt.slug
            """
        )
    )
    default_template = bind.execute(
        sa.text(
            "SELECT COALESCE(min(CASE WHEN status='available' THEN id END), min(id)) FROM templates"
        )
    ).scalar()
    if default_template is None:
        raise RuntimeError("no template is available for resume migration")

    profile_columns = _columns("requirement_profiles")
    for name in ("archived_at", "recycled_at", "purged_at"):
        if name not in profile_columns:
            op.add_column(
                "requirement_profiles",
                sa.Column(name, sa.DateTime(timezone=True), nullable=True),
            )
    opportunity_columns = _columns("job_opportunities")
    if "status" not in opportunity_columns:
        op.add_column(
            "job_opportunities",
            sa.Column(
                "status",
                sa.String(30),
                nullable=False,
                server_default="active",
            ),
        )
    if "updated_at" not in opportunity_columns:
        op.add_column(
            "job_opportunities",
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        bind.execute(
            sa.text(
                "UPDATE job_opportunities SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )
        )

    op.create_table(
        "profile_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("requirement_profiles.id"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("changed_fields_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("before_values_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_values_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("related_profile_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_profile_audit_events_workspace_id", "profile_audit_events", ["workspace_id"])
    op.create_index("ix_profile_audit_events_profile_id", "profile_audit_events", ["profile_id"])

    # Rebuild resume-chain tables under their target names.
    bind.execute(sa.text("ALTER TABLE linked_resumes RENAME TO legacy_linked_resumes"))
    op.execute(LINKED_SQL)
    bind.execute(sa.text("ALTER TABLE resume_identities RENAME TO legacy_resume_identities"))
    op.execute(RESUME_SQL)
    bind.execute(sa.text("ALTER TABLE resume_versions RENAME TO legacy_resume_versions"))
    op.execute(VERSION_SQL)
    bind.execute(sa.text("ALTER TABLE resume_working_copies RENAME TO legacy_resume_working_copies"))
    op.execute(WORKING_SQL)

    bind.execute(
        sa.text(
            """
            INSERT INTO linked_resumes(
                id, workspace_id, requirement_profile_id, template_id,
                selection_json, status, converted_resume_id,
                created_at, updated_at
            )
            SELECT
                l.id, l.workspace_id, l.requirement_profile_id,
                COALESCE(m.template_id, :default_template),
                l.selection, 'open', NULL, l.created_at, l.updated_at
            FROM legacy_linked_resumes l
            LEFT JOIN template_version_map m
              ON m.template_version_id = l.template_version_id
            """
        ),
        {"default_template": default_template},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO resumes(
                id, workspace_id, requirement_profile_id, origin_linked_resume_id,
                template_id, display_name, current_version_id, status,
                archived_at, recycled_at, purged_at, created_at, updated_at
            )
            SELECT
                r.id, r.workspace_id, r.requirement_profile_id, NULL,
                COALESCE(
                    cwm.template_id,
                    vwm.template_id,
                    :default_template
                ),
                r.display_name, r.current_version_id, r.status,
                NULL, r.deleted_at, NULL, r.created_at, r.updated_at
            FROM legacy_resume_identities r
            LEFT JOIN legacy_resume_working_copies c
              ON c.resume_identity_id = r.id
            LEFT JOIN template_version_map cwm
              ON cwm.template_version_id = c.template_version_id
            LEFT JOIN legacy_resume_versions v
              ON v.id = r.current_version_id
            LEFT JOIN template_version_map vwm
              ON vwm.template_version_id = v.template_version_id
            """
        ),
        {"default_template": default_template},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO resume_versions(
                id, workspace_id, resume_id, version_number, content_json,
                source_manifest_json, profile_snapshot_json,
                profile_snapshot_hash, evidence_manifest_json, reason,
                change_summary, content_hash, created_at
            )
            SELECT
                v.id, r.workspace_id, v.resume_identity_id, v.version_number,
                v.content, v.source_manifest, v.profile_snapshot,
                printf('%064d', 0), '[]',
                CASE
                    WHEN v.reason IN (
                        'format_conversion', 'user_save', 'rollback', 'evidence_sync'
                    ) THEN v.reason
                    ELSE 'user_save'
                END,
                v.change_summary, v.content_hash, v.created_at
            FROM legacy_resume_versions v
            JOIN legacy_resume_identities r ON r.id = v.resume_identity_id
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO resume_working_copies(
                id, workspace_id, resume_id, base_version_id, template_id,
                content_json, content_state, evidence_sync_state,
                baseline_state, pending_reason, updated_at
            )
            SELECT
                c.id, r.workspace_id, c.resume_identity_id, c.base_version_id,
                COALESCE(
                    cwm.template_id,
                    vwm.template_id,
                    :default_template
                ),
                c.content,
                CASE WHEN c.dirty = 1 THEN 'dirty' ELSE 'clean' END,
                'clean',
                CASE
                    WHEN c.base_version_id IS NULL
                      OR c.base_version_id = r.current_version_id
                    THEN 'current'
                    ELSE 'stale'
                END,
                c.pending_reason, c.updated_at
            FROM legacy_resume_working_copies c
            JOIN legacy_resume_identities r
              ON r.id = c.resume_identity_id
            LEFT JOIN template_version_map cwm
              ON cwm.template_version_id = c.template_version_id
            LEFT JOIN legacy_resume_versions v
              ON v.id = r.current_version_id
            LEFT JOIN template_version_map vwm
              ON vwm.template_version_id = v.template_version_id
            """
        ),
        {"default_template": default_template},
    )

    op.create_index("ix_resumes_workspace_id", "resumes", ["workspace_id"])
    op.create_index(
        "uq_active_resume_per_profile",
        "resumes",
        ["workspace_id", "requirement_profile_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_resume_versions_workspace_id", "resume_versions", ["workspace_id"])
    op.create_index("ix_resume_versions_resume_id", "resume_versions", ["resume_id"])

    # Current and immutable fact references.
    old_refs = "resume_fact_references" in tables
    if old_refs:
        bind.execute(sa.text("ALTER TABLE resume_fact_references RENAME TO legacy_resume_fact_references"))
    op.execute(FACT_USE_SQL)
    op.execute(FACT_SNAPSHOT_SQL)
    if old_refs:
        bind.execute(
            sa.text(
                """
                INSERT INTO resume_fact_uses(
                    id, workspace_id, resume_id, fact_id, section_code,
                    block_key, display_order, fact_content_hash
                )
                SELECT
                    x.id, r.workspace_id, x.resume_identity_id, x.fact_id,
                    x.section_id, x.block_id,
                    row_number() OVER (
                        PARTITION BY x.resume_identity_id
                        ORDER BY x.id
                    ) - 1,
                    ''
                FROM legacy_resume_fact_references x
                JOIN resumes r ON r.id = x.resume_identity_id
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO resume_version_fact_snapshots(
                    workspace_id, resume_version_id, fact_id, section_code,
                    block_key, display_order, fact_content_hash
                )
                SELECT
                    v.workspace_id, v.id,
                    CAST(json_extract(j.value, '$.fact_id') AS INTEGER),
                    CAST(json_extract(j.value, '$.section_id') AS TEXT),
                    CAST(json_extract(j.value, '$.block_id') AS TEXT),
                    CAST(j.key AS INTEGER),
                    ''
                FROM resume_versions v, json_each(v.source_manifest_json) j
                WHERE json_extract(j.value, '$.fact_id') IS NOT NULL
                """
            )
        )
    op.create_index("ix_resume_fact_uses_workspace_id", "resume_fact_uses", ["workspace_id"])
    op.create_index("ix_resume_fact_uses_resume_id", "resume_fact_uses", ["resume_id"])

    # Target evidence-use tables start empty because the legacy implementation
    # never stored resume-level evidence display settings.
    op.execute(EVIDENCE_USE_SQL)
    op.execute(EVIDENCE_SNAPSHOT_SQL)

    bind.execute(sa.text("ALTER TABLE pending_items RENAME TO legacy_pending_items"))
    op.execute(PENDING_SQL)
    bind.execute(
        sa.text(
            """
            INSERT INTO pending_issues(
                id, workspace_id, kind, status, fact_id, evidence_id,
                profile_id, resume_id, section_code, block_key, message,
                created_at, resolved_at
            )
            SELECT
                id, workspace_id, kind, status, fact_id, NULL, NULL,
                resume_identity_id, '', '', message, created_at, NULL
            FROM legacy_pending_items
            """
        )
    )

    op.create_table(
        "workspace_template_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), unique=True, nullable=False),
        sa.Column("default_template_id", sa.Integer(), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("last_selected_template_id", sa.Integer(), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO workspace_template_preferences(
                workspace_id, default_template_id, last_selected_template_id,
                updated_at
            )
            SELECT id, :default_template, NULL,
                   strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            FROM workspaces
            """
        ),
        {"default_template": default_template},
    )
    op.create_table(
        "export_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id"), nullable=False, index=True),
        sa.Column("resume_version_id", sa.Integer(), sa.ForeignKey("resume_versions.id"), nullable=False, index=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("templates.id"), nullable=False, index=True),
        sa.Column("format", sa.String(20), nullable=False, server_default="html"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("forced", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Drop only the old copies after every row has been migrated.
    for table in (
        "legacy_resume_working_copies",
        "legacy_resume_fact_references" if old_refs else None,
        "legacy_pending_items",
        "legacy_resume_identities",
        "legacy_resume_versions",
        "legacy_linked_resumes",
    ):
        if table:
            bind.execute(sa.text(f'DROP TABLE "{table}"'))
    bind.execute(sa.text("DROP TABLE template_version_map"))


def downgrade() -> None:
    raise RuntimeError(
        "The target domain upgrade is intentionally irreversible. Restore the "
        "pre-migration database backup recorded with this release instead."
    )
