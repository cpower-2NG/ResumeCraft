"""Guarantee that resource rows use the canonical five primary categories."""

from alembic import op
import sqlalchemy as sa


revision = "0011_resource_category_guard"
down_revision = "0010_hide_remaining_test_chain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_fact_category_valid
        BEFORE INSERT ON fact_records
        WHEN NEW.category NOT IN (
            'basics', 'education', 'experience', 'skill', 'achievement', 'link'
        )
        BEGIN
            SELECT RAISE(ABORT, 'unsupported resource category');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_fact_category_valid")
