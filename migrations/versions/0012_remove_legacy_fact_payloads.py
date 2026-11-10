"""Remove unused JSON payload and free-form custom-field storage."""

from alembic import op
import sqlalchemy as sa


revision = "0012_remove_legacy_fact_payloads"
down_revision = "0011_resource_category_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "fact_categories" in sa.inspect(bind).get_table_names():
        return
    tables = set(sa.inspect(bind).get_table_names())
    if "fact_custom_fields" in tables:
        op.drop_table("fact_custom_fields")
    columns = {item["name"] for item in sa.inspect(bind).get_columns("fact_records")}
    if "content" in columns or "tags" in columns:
        with op.batch_alter_table("fact_records", recreate="always") as batch:
            if "content" in columns:
                batch.drop_column("content")
            if "tags" in columns:
                batch.drop_column("tags")


def downgrade() -> None:
    raise RuntimeError(
        "Legacy JSON payload columns are intentionally removed; restore the "
        "pre-reorganization database backup."
    )
