"""Allow a new formal resume after the previous identity is recycled."""

from alembic import op
import sqlalchemy as sa


revision = "0004_allow_recreated_resume_identity"
down_revision = "0003_structured_fact_details"
branch_labels = None
depends_on = None


def upgrade():
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    if "resume_identities" not in sa.inspect(op.get_bind()).get_table_names():
        return
    with op.batch_alter_table("resume_identities", recreate="always") as batch:
        batch.drop_constraint("uq_resume_per_profile", type_="unique")


def downgrade():
    with op.batch_alter_table("resume_identities", recreate="always") as batch:
        batch.create_unique_constraint("uq_resume_per_profile", ["workspace_id", "requirement_profile_id"])
