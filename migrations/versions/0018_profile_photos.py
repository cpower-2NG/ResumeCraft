"""Add one current profile photo with retained history per personal archive."""

from alembic import op


revision = "0018_profile_photos"
down_revision = "0017_target_guard_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_photos (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL,
            basics_fact_id INTEGER NOT NULL,
            basics_category_code TEXT NOT NULL DEFAULT 'basics'
                CHECK (basics_category_code = 'basics'),
            evidence_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
            created_at TEXT NOT NULL,
            archived_at TEXT,
            FOREIGN KEY (workspace_id, basics_fact_id, basics_category_code)
                REFERENCES fact_records(workspace_id, id, category_code)
                ON DELETE CASCADE,
            FOREIGN KEY (workspace_id, evidence_id)
                REFERENCES evidence(workspace_id, id)
                ON DELETE RESTRICT,
            UNIQUE (workspace_id, evidence_id)
        ) STRICT
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_profile_photo
        ON profile_photos(workspace_id, basics_fact_id)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_profile_photo_evidence_file_insert
        BEFORE INSERT ON profile_photos
        WHEN NOT EXISTS (
            SELECT 1 FROM evidence
             WHERE workspace_id = NEW.workspace_id
               AND id = NEW.evidence_id
               AND kind = 'file'
               AND mime_type LIKE 'image/%'
        )
        BEGIN
            SELECT RAISE(ABORT, 'profile photo must reference an image file');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_profile_photo_evidence_file_update
        BEFORE UPDATE OF workspace_id, evidence_id ON profile_photos
        WHEN NOT EXISTS (
            SELECT 1 FROM evidence
             WHERE workspace_id = NEW.workspace_id
               AND id = NEW.evidence_id
               AND kind = 'file'
               AND mime_type LIKE 'image/%'
        )
        BEGIN
            SELECT RAISE(ABORT, 'profile photo must reference an image file');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_profile_photo_evidence_file_update")
    op.execute("DROP TRIGGER IF EXISTS trg_profile_photo_evidence_file_insert")
    op.execute("DROP INDEX IF EXISTS uq_active_profile_photo")
    op.execute("DROP TABLE IF EXISTS profile_photos")
