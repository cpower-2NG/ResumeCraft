"""Give imported competition awards their own competition experiences."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0015_fix_competition_experience_parents"
down_revision = "0014_remove_link_fact_category"
branch_labels = None
depends_on = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(
    bind: sa.Connection,
    fact_id: int,
    action: str,
    summary: str,
    before: dict,
    after: dict,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO fact_audits(
                workspace_id, fact_id, action, summary,
                before_content, after_content, created_at
            ) VALUES (
                1, :fact_id, :action, :summary,
                :before_content, :after_content, :created_at
            )
            """
        ),
        {
            "fact_id": fact_id,
            "action": action,
            "summary": summary,
            "before_content": json.dumps(before, ensure_ascii=False, sort_keys=True),
            "after_content": json.dumps(after, ensure_ascii=False, sort_keys=True),
            "created_at": _now(),
        },
    )


def _find_or_create_experience(
    bind: sa.Connection,
    *,
    title: str,
    period: str,
    organization: str,
    outcome: str,
    tag_names: list[str],
) -> int:
    existing = bind.execute(
        sa.text(
            """
            SELECT id FROM fact_records
             WHERE workspace_id=1 AND category='experience' AND title=:title
             ORDER BY id LIMIT 1
            """
        ),
        {"title": title},
    ).scalar()
    if existing:
        return int(existing)

    now_value = _now()
    result = bind.execute(
        sa.text(
            """
            INSERT INTO fact_records(
                workspace_id, category, title, status, source_note,
                created_at, updated_at
            ) VALUES (
                1, 'experience', :title, 'active',
                '由原竞赛成果补齐主经历', :created_at, :updated_at
            )
            """
        ),
        {"title": title, "created_at": now_value, "updated_at": now_value},
    )
    experience_id = int(result.lastrowid)
    details = {
        "kind": "competition",
        "setting": "competition",
        "period": period,
        "organization": organization,
        "outcome": outcome,
    }
    bind.execute(
        sa.text(
            """
            INSERT INTO experience_fact_details(
                fact_id, kind, setting, period, organization, role,
                team_size, context, work, tools, outcome, challenge,
                solution, public_note
            ) VALUES (
                :fact_id, 'competition', 'competition', :period,
                :organization, '', '', '', '', '', :outcome, '', '', ''
            )
            """
        ),
        {
            "fact_id": experience_id,
            "period": period,
            "organization": organization,
            "outcome": outcome,
        },
    )
    for tag_name in tag_names:
        normalized = tag_name.strip().lower()
        tag_id = bind.execute(
            sa.text(
                """
                SELECT id FROM tags
                 WHERE workspace_id=1 AND normalized_name=:normalized
                 LIMIT 1
                """
            ),
            {"normalized": normalized},
        ).scalar()
        if tag_id is None:
            tag_id = int(
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO tags(
                            workspace_id, display_name, normalized_name,
                            status, created_at
                        ) VALUES (1, :display_name, :normalized, 'active', :created_at)
                        """
                    ),
                    {
                        "display_name": tag_name,
                        "normalized": normalized,
                        "created_at": now_value,
                    },
                ).lastrowid
            )
        bind.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO fact_tags(workspace_id, fact_id, tag_id)
                VALUES (1, :fact_id, :tag_id)
                """
            ),
            {"fact_id": experience_id, "tag_id": tag_id},
        )
    _audit(
        bind,
        experience_id,
        "created",
        "从原竞赛成果补齐对应主经历",
        {},
        details,
    )
    return experience_id


def _reparent_award(
    bind: sa.Connection,
    *,
    award_title: str,
    experience_id: int,
    expected_period: str,
) -> None:
    award = bind.execute(
        sa.text(
            """
            SELECT f.id, a.experience_fact_id
              FROM fact_records f
              JOIN achievement_fact_details a ON a.fact_id=f.id
             WHERE f.workspace_id=1
               AND f.category='achievement'
               AND f.title=:title
               AND a.period=:period
             ORDER BY f.id LIMIT 1
            """
        ),
        {"title": award_title, "period": expected_period},
    ).mappings().first()
    if not award or award["experience_fact_id"] == experience_id:
        return
    before = {"experience_fact_id": award["experience_fact_id"]}
    after = {"experience_fact_id": experience_id}
    bind.execute(
        sa.text(
            """
            UPDATE achievement_fact_details
               SET experience_fact_id=:experience_id
             WHERE fact_id=:fact_id
            """
        ),
        {"experience_id": experience_id, "fact_id": award["id"]},
    )
    _audit(
        bind,
        int(award["id"]),
        "reparented",
        "把竞赛成果改挂到对应竞赛经历",
        before,
        after,
    )


def _has_award(
    bind: sa.Connection,
    *,
    award_title: str,
    expected_period: str,
) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                  FROM fact_records f
                  JOIN achievement_fact_details a ON a.fact_id=f.id
                 WHERE f.workspace_id=1
                   AND f.category='achievement'
                   AND f.title=:title
                   AND a.period=:period
                 LIMIT 1
                """
            ),
            {"title": award_title, "period": expected_period},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()
    if "fact_categories" in sa.inspect(bind).get_table_names():
        return
    xtrainer_title = "越疆 X-Trainer 竞赛"
    if _has_award(bind, award_title=xtrainer_title, expected_period="2026.06"):
        xtrainer = _find_or_create_experience(
            bind,
            title=xtrainer_title,
            period="2026.06",
            organization="越疆",
            outcome="省级三等奖",
            tag_names=["机器人", "竞赛"],
        )
        _reparent_award(
            bind,
            award_title=xtrainer_title,
            experience_id=xtrainer,
            expected_period="2026.06",
        )

    ubt_title = "优必选天工无疆全球人形机器人挑战赛"
    if _has_award(bind, award_title=ubt_title, expected_period="2026.08"):
        ubt = _find_or_create_experience(
            bind,
            title=ubt_title,
            period="2026.08",
            organization="优必选",
            outcome="第 20 名",
            tag_names=["具身智能", "机器人", "竞赛"],
        )
        _reparent_award(
            bind,
            award_title=ubt_title,
            experience_id=ubt,
            expected_period="2026.08",
        )


def downgrade() -> None:
    # The new parent facts are audited domain data; restoring deleted rows would
    # make an explicit repair look like it never happened.
    pass
