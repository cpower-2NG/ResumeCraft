"""Hide the remaining manually created test profile from active lists."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0010_hide_remaining_test_chain"
down_revision = "0009_resource_reorganization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "fact_categories" in sa.inspect(bind).get_table_names():
        return
    now_value = datetime.now(timezone.utc).isoformat()
    profiles = bind.execute(
        sa.text(
            """
            SELECT id FROM requirement_profiles
             WHERE (
                   name LIKE '%交互验证%'
                   OR name LIKE '%交互测试%'
                   OR name LIKE '%GUI测试%'
                   OR lower(name) LIKE '%test%'
               )
            """
        )
    ).scalars().all()
    for profile_id in profiles:
        bind.execute(
            sa.text(
                """
                UPDATE requirement_profiles
                   SET status='recycled', recycled_at=COALESCE(recycled_at, :now)
                 WHERE id=:profile_id AND status='active'
                """
            ),
            {"profile_id": profile_id, "now": now_value},
        )
        bind.execute(
            sa.text(
                """
                UPDATE resumes
                   SET status='recycled', recycled_at=COALESCE(recycled_at, :now)
                 WHERE requirement_profile_id=:profile_id AND status='active'
                """
            ),
            {"profile_id": profile_id, "now": now_value},
        )
        bind.execute(
            sa.text(
                """
                UPDATE linked_resumes SET status='abandoned'
                 WHERE requirement_profile_id=:profile_id AND status='open'
                """
            ),
            {"profile_id": profile_id},
        )


def downgrade() -> None:
    # Test classification is data normalization, not a reversible schema change.
    pass
