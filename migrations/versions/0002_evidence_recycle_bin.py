"""Add evidence records and recycle-bin state."""

from alembic import op
import sqlalchemy as sa


revision = "0002_evidence_recycle_bin"
down_revision = "0001_workbench_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fact_records", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requirement_profiles", sa.Column("status", sa.String(length=30), nullable=False, server_default="active"))
    op.add_column("requirement_profiles", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("resume_identities", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("storage_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("filename", sa.String(length=250), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "fact_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), nullable=False, index=True),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False, index=True),
        sa.UniqueConstraint("fact_id", "evidence_id", name="uq_fact_evidence"),
    )


def downgrade():
    op.drop_table("fact_evidence")
    op.drop_table("evidence")
    op.drop_column("resume_identities", "deleted_at")
    op.drop_column("requirement_profiles", "deleted_at")
    op.drop_column("requirement_profiles", "status")
    op.drop_column("fact_records", "deleted_at")
