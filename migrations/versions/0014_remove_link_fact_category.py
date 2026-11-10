"""Remove link facts; project links are evidence attached to another fact."""

from alembic import op
import sqlalchemy as sa


revision = "0014_remove_link_fact_category"
down_revision = "0013_normalize_experience_setting_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "fact_categories" in sa.inspect(bind).get_table_names():
        return
    link_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM fact_records WHERE category='link'")
        ).all()
    ]
    if link_ids:
        raise RuntimeError(
            "Link facts exist and must be converted to evidence before this migration: "
            + repr(link_ids)
        )
    tables = set(sa.inspect(bind).get_table_names())
    if "link_fact_details" in tables:
        op.drop_table("link_fact_details")
    op.execute("DROP TRIGGER IF EXISTS trg_fact_category_valid")
    op.execute(
        """
        CREATE TRIGGER trg_fact_category_valid
        BEFORE INSERT ON fact_records
        WHEN NEW.category NOT IN (
            'basics', 'education', 'experience', 'skill', 'achievement'
        )
        BEGIN
            SELECT RAISE(ABORT, 'unsupported resource category');
        END
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_fact_category_immutable")
    op.execute(
        """
        CREATE TRIGGER trg_fact_category_immutable
        BEFORE UPDATE OF category ON fact_records
        WHEN NEW.category NOT IN (
            'basics', 'education', 'experience', 'skill', 'achievement'
        ) OR NEW.category <> OLD.category
        BEGIN
            SELECT RAISE(ABORT, 'resource category cannot be changed in place');
        END
        """
    )


def downgrade() -> None:
    pass
