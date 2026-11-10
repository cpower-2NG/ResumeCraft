"""Install target append-only and cross-object SQLite guards."""

from alembic import op
import sqlalchemy as sa


revision = "0008_domain_integrity_guards"
down_revision = "0007_target_domain_upgrade"
branch_labels = None
depends_on = None


TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_resume_version_no_update
    BEFORE UPDATE ON resume_versions
    BEGIN
        SELECT RAISE(ABORT, 'resume versions are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_resume_version_no_delete
    BEFORE DELETE ON resume_versions
    BEGIN
        SELECT RAISE(ABORT, 'resume versions are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_version_fact_snapshot_no_update
    BEFORE UPDATE ON resume_version_fact_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'version fact snapshots are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_version_fact_snapshot_no_delete
    BEFORE DELETE ON resume_version_fact_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'version fact snapshots are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_version_evidence_snapshot_no_update
    BEFORE UPDATE ON resume_version_evidence_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'version evidence snapshots are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_version_evidence_snapshot_no_delete
    BEFORE DELETE ON resume_version_evidence_snapshots
    BEGIN
        SELECT RAISE(ABORT, 'version evidence snapshots are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_export_event_no_update
    BEFORE UPDATE ON export_events
    BEGIN
        SELECT RAISE(ABORT, 'export events are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_export_event_no_delete
    BEFORE DELETE ON export_events
    BEGIN
        SELECT RAISE(ABORT, 'export events are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_fact_audit_no_update
    BEFORE UPDATE ON fact_audits
    BEGIN
        SELECT RAISE(ABORT, 'fact audits are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_fact_audit_no_delete
    BEFORE DELETE ON fact_audits
    BEGIN
        SELECT RAISE(ABORT, 'fact audits are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_profile_audit_no_update
    BEFORE UPDATE ON profile_audit_events
    BEGIN
        SELECT RAISE(ABORT, 'profile audits are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_profile_audit_no_delete
    BEFORE DELETE ON profile_audit_events
    BEGIN
        SELECT RAISE(ABORT, 'profile audits are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_evidence_payload_immutable
    BEFORE UPDATE OF kind, url, storage_key, filename, mime_type, size_bytes, checksum, note
    ON evidence
    WHEN NEW.kind IS NOT OLD.kind
      OR NEW.url IS NOT OLD.url
      OR NEW.storage_key IS NOT OLD.storage_key
      OR NEW.filename IS NOT OLD.filename
      OR NEW.mime_type IS NOT OLD.mime_type
      OR NEW.size_bytes IS NOT OLD.size_bytes
      OR NEW.checksum IS NOT OLD.checksum
      OR NEW.note IS NOT OLD.note
    BEGIN
        SELECT RAISE(ABORT, 'evidence payload is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_evidence_no_delete
    BEFORE DELETE ON evidence
    BEGIN
        SELECT RAISE(ABORT, 'evidence cannot be physically deleted');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_resume_status_transition
    BEFORE UPDATE OF status ON resumes
    WHEN NEW.status <> OLD.status
     AND NOT (
        (OLD.status = 'active' AND NEW.status IN ('archived', 'recycled'))
        OR (OLD.status = 'archived' AND NEW.status IN ('active', 'recycled'))
        OR (OLD.status = 'recycled' AND NEW.status IN ('active', 'archived', 'purged'))
     )
    BEGIN
        SELECT RAISE(ABORT, 'invalid resume status transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_linked_conversion_once
    BEFORE UPDATE OF status, converted_resume_id ON linked_resumes
    WHEN OLD.status = 'converted'
      AND (NEW.status <> 'converted' OR NEW.converted_resume_id IS NOT OLD.converted_resume_id)
    BEGIN
        SELECT RAISE(ABORT, 'converted draft is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_profile_purge_guard
    BEFORE UPDATE OF status ON requirement_profiles
    WHEN NEW.status = 'purged'
     AND EXISTS (
        SELECT 1 FROM resumes
        WHERE workspace_id = NEW.workspace_id
          AND requirement_profile_id = NEW.id
          AND status <> 'purged'
     )
    BEGIN
        SELECT RAISE(ABORT, 'profile still owns formal Resume history');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_current_version_matches_resume
    BEFORE UPDATE OF current_version_id ON resumes
    WHEN NEW.current_version_id IS NOT NULL
     AND NOT EXISTS (
        SELECT 1 FROM resume_versions
        WHERE workspace_id = NEW.workspace_id
          AND resume_id = NEW.id
          AND id = NEW.current_version_id
     )
    BEGIN
        SELECT RAISE(ABORT, 'current version belongs to another Resume');
    END
    """,
)


def upgrade() -> None:
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_file_checksum
        ON evidence(workspace_id, checksum)
        WHERE kind = 'file'
        """
    )
    for statement in TRIGGERS:
        op.execute(statement)


def downgrade() -> None:
    for name in (
        "trg_current_version_matches_resume",
        "trg_profile_purge_guard",
        "trg_linked_conversion_once",
        "trg_resume_status_transition",
        "trg_evidence_no_delete",
        "trg_evidence_payload_immutable",
        "trg_profile_audit_no_delete",
        "trg_profile_audit_no_update",
        "trg_fact_audit_no_delete",
        "trg_fact_audit_no_update",
        "trg_export_event_no_delete",
        "trg_export_event_no_update",
        "trg_version_evidence_snapshot_no_delete",
        "trg_version_evidence_snapshot_no_update",
        "trg_version_fact_snapshot_no_delete",
        "trg_version_fact_snapshot_no_update",
        "trg_resume_version_no_delete",
        "trg_resume_version_no_update",
    ):
        op.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    op.execute("DROP INDEX IF EXISTS uq_evidence_file_checksum")
