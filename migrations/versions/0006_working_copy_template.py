"""Let the working copy carry a template choice until the next formal save."""

from alembic import op
import sqlalchemy as sa


revision = "0006_working_copy_template"
down_revision = "0005_working_copy_pending_reason"
branch_labels = None
depends_on = None


def upgrade():
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("resume_working_copies")}
    if "template_version_id" in columns or "template_id" in columns:
        return
    with op.batch_alter_table("resume_working_copies", recreate="always") as batch:
        batch.add_column(sa.Column("template_version_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("resume_working_copies", recreate="always") as batch:
        batch.drop_column("template_version_id")
