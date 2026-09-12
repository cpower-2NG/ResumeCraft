"""Track the reason the next formal save should carry, e.g. rollback."""

from alembic import op
import sqlalchemy as sa


revision = "0005_working_copy_pending_reason"
down_revision = "0004_allow_recreated_resume_identity"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("resume_working_copies", recreate="always") as batch:
        batch.add_column(sa.Column("pending_reason", sa.String(40), nullable=True))


def downgrade():
    with op.batch_alter_table("resume_working_copies", recreate="always") as batch:
        batch.drop_column("pending_reason")
