"""Normalize experience setting values from display labels to stable codes."""

from alembic import op
import sqlalchemy as sa


revision = "0013_normalize_experience_setting_codes"
down_revision = "0012_remove_legacy_fact_payloads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    for label, code in (
        ("课程", "course"),
        ("实验室", "lab"),
        ("公司", "company"),
        ("个人", "personal"),
        ("团队", "team"),
        ("社群/公益", "community"),
        ("竞赛", "competition"),
        ("其他", "other"),
    ):
        op.get_bind().execute(
            __import__("sqlalchemy").text(
                "UPDATE experience_fact_details SET setting=:code WHERE setting=:label"
            ),
            {"label": label, "code": code},
        )


def downgrade() -> None:
    pass
