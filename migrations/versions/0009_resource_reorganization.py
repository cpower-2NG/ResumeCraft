"""Reorganize the resource library around stable facts and explicit relations."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0009_resource_reorganization"
down_revision = "0008_domain_integrity_guards"
branch_labels = None
depends_on = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _category(code: str) -> str:
    return {"skills": "skill", "awards": "achievement"}.get(code, code)


def _add_columns() -> None:
    experience_columns = _columns("experience_fact_details")
    if "setting" not in experience_columns:
        op.add_column(
            "experience_fact_details",
            sa.Column("setting", sa.String(80), nullable=False, server_default=""),
        )

    achievement_columns = _columns("achievement_fact_details")
    if "achievement_kind" not in achievement_columns:
        op.add_column(
            "achievement_fact_details",
            sa.Column(
                "achievement_kind",
                sa.String(40),
                nullable=False,
                server_default="honor",
            ),
        )
    if "experience_fact_id" not in achievement_columns:
        with op.batch_alter_table("achievement_fact_details", recreate="always") as batch:
            batch.add_column(sa.Column("experience_fact_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_achievement_parent_experience",
                "fact_records",
                ["experience_fact_id"],
                ["id"],
            )

    profile_columns = _columns("requirement_profiles")
    for name in ("desired_city", "availability", "personal_summary"):
        if name not in profile_columns:
            op.add_column(
                "requirement_profiles",
                sa.Column(name, sa.Text(), nullable=False, server_default=""),
            )


def _create_relation_tables() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "tags" not in tables:
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("display_name", sa.String(120), nullable=False),
            sa.Column("normalized_name", sa.String(120), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("merged_into_tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_tag_name"),
        )
        op.create_index("ix_tags_workspace_id", "tags", ["workspace_id"])
    if "fact_tags" not in tables:
        op.create_table(
            "fact_tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), nullable=False),
            sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
            sa.UniqueConstraint("fact_id", "tag_id", name="uq_fact_tag"),
        )
        op.create_index("ix_fact_tags_workspace_id", "fact_tags", ["workspace_id"])
        op.create_index("ix_fact_tags_fact_id", "fact_tags", ["fact_id"])
        op.create_index("ix_fact_tags_tag_id", "fact_tags", ["tag_id"])
    if "experience_skill_links" not in tables:
        op.create_table(
            "experience_skill_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("experience_fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), nullable=False),
            sa.Column("skill_fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), nullable=False),
            sa.UniqueConstraint(
                "experience_fact_id",
                "skill_fact_id",
                name="uq_experience_skill",
            ),
        )
        op.create_index(
            "ix_experience_skill_links_workspace_id",
            "experience_skill_links",
            ["workspace_id"],
        )
        op.create_index(
            "ix_experience_skill_links_experience_fact_id",
            "experience_skill_links",
            ["experience_fact_id"],
        )
        op.create_index(
            "ix_experience_skill_links_skill_fact_id",
            "experience_skill_links",
            ["skill_fact_id"],
        )


def _restore_basics_and_profile(bind: sa.Connection) -> None:
    basic = bind.execute(
        sa.text("SELECT * FROM personal_fact_details WHERE fact_id = 1")
    ).mappings().first()
    if not basic:
        return
    populated = any(
        str(basic[name] or "").strip()
        for name in ("name", "phone", "email", "city", "status", "graduation")
    )
    audit = bind.execute(
        sa.text(
            """
            SELECT after_content FROM fact_audits
            WHERE fact_id = 1
              AND json_valid(after_content)
              AND after_content NOT IN ('', '{}')
            ORDER BY id DESC LIMIT 1
            """
        )
    ).scalar()
    legacy = json.loads(audit or "{}")
    if not populated and legacy:
        bind.execute(
            sa.text(
                """
                UPDATE personal_fact_details
                   SET name=:name, phone=:phone, email=:email, city=:city,
                       birth_date=:birth_date, age=:age, hometown=:hometown,
                       status=:status, graduation=:graduation
                 WHERE fact_id=1
                """
            ),
            {
                "name": str(legacy.get("name", "")),
                "phone": str(legacy.get("phone", "")),
                "email": str(legacy.get("email", "")),
                "city": str(legacy.get("city", "")),
                "birth_date": str(legacy.get("birth_date", "")),
                "age": str(legacy.get("age", "")),
                "hometown": str(legacy.get("hometown", "")),
                "status": str(legacy.get("status", "")),
                "graduation": str(legacy.get("graduation", "")),
            },
        )
        retained = {
            key: legacy[key]
            for key in ("name", "phone", "email", "city", "status", "graduation")
            if legacy.get(key)
        }
        bind.execute(
            sa.text("UPDATE fact_records SET content=:content WHERE id=1"),
            {"content": json.dumps(retained, ensure_ascii=False, sort_keys=True)},
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_audits(
                    workspace_id, fact_id, action, summary,
                    before_content, after_content, created_at
                )
                VALUES (1, 1, 'reorganized', '从审计恢复个人档案并拆分岗位表达字段',
                        '{}', :content, :created_at)
                """
            ),
            {
                "content": json.dumps(retained, ensure_ascii=False, sort_keys=True),
                "created_at": _now(),
            },
        )

    profile = bind.execute(
        sa.text("SELECT id FROM requirement_profiles WHERE workspace_id=1 ORDER BY id LIMIT 1")
    ).scalar()
    if profile:
        bind.execute(
            sa.text(
                """
                UPDATE requirement_profiles
                   SET desired_city=:desired_city,
                       availability=:availability,
                       personal_summary=:personal_summary
                 WHERE id=:profile_id
                """
            ),
            {
                "desired_city": str(legacy.get("desired_city", "")),
                "availability": str(legacy.get("availability", "")),
                "personal_summary": str(legacy.get("bio", "")),
                "profile_id": profile,
            },
        )
    bind.execute(
        sa.text(
            """
            UPDATE personal_fact_details
               SET desired_city='', availability='', bio=''
             WHERE fact_id=1
            """
        )
    )


def _migrate_classifications(bind: sa.Connection) -> None:
    bind.execute(sa.text("UPDATE fact_records SET category='skill' WHERE category='skills'"))
    bind.execute(
        sa.text("UPDATE fact_records SET category='achievement' WHERE category='awards'")
    )

    experience_rows = bind.execute(
        sa.text(
            """
            SELECT f.id, f.title, d.kind, d.organization
              FROM fact_records f
              JOIN experience_fact_details d ON d.fact_id=f.id
             WHERE f.category='experience'
            """
        )
    ).mappings()
    for row in experience_rows:
        raw_kind = str(row["kind"] or "").strip()
        if raw_kind in {"竞赛", "比赛", "competition"}:
            kind, setting = "competition", "competition"
        elif raw_kind in {"科研项目", "科研", "research"}:
            kind, setting = "research", "lab"
        elif raw_kind in {"实习", "工作", "work_internship"}:
            kind, setting = "work_internship", "company"
        elif "课程" in raw_kind or "课程项目" in str(row["organization"] or ""):
            kind, setting = "project", "course"
        elif raw_kind in {"教材开发", "项目"}:
            kind, setting = "project", "lab"
        else:
            kind, setting = "project", ""
        bind.execute(
            sa.text(
                "UPDATE experience_fact_details SET kind=:kind, setting=:setting WHERE fact_id=:id"
            ),
            {"kind": kind, "setting": setting, "id": row["id"]},
        )

    # Keep one project as the source of two competition outcomes.
    bind.execute(
        sa.text(
            """
            UPDATE fact_records
               SET title='机器人数据采集与模仿学习项目'
             WHERE id=3 AND title='越疆 X-Trainer 竞赛与优必选人形机器人挑战赛'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE experience_fact_details
               SET kind='project', setting='lab',
                   outcome='包裹分拣任务可完成约 60% - 70%。'
             WHERE fact_id=3
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE experience_fact_details
               SET kind='competition', setting='competition',
                   outcome='完成多场景全流程任务。'
             WHERE fact_id=27
            """
        )
    )

    parent_map = {
        19: 3,
        20: 3,
        21: 10,
    }
    for achievement_id, experience_id in parent_map.items():
        bind.execute(
            sa.text(
                """
                UPDATE achievement_fact_details
                   SET achievement_kind='honor', experience_fact_id=:parent
                 WHERE fact_id=:id
                """
            ),
            {"parent": experience_id, "id": achievement_id},
        )

    # Materialize the second-place national award as an explicit outcome.
    existing_award = bind.execute(
        sa.text(
            """
            SELECT fact_id FROM achievement_fact_details
             WHERE experience_fact_id=27
             LIMIT 1
            """
        )
    ).scalar()
    parent_exists = bind.execute(
        sa.text("SELECT 1 FROM fact_records WHERE id=27 AND category='experience'")
    ).scalar()
    if existing_award is None and parent_exists:
        now_value = _now()
        result = bind.execute(
            sa.text(
                """
                INSERT INTO fact_records(
                    workspace_id, category, title, content, tags, status,
                    source_note, created_at, updated_at
                ) VALUES (
                    1, 'achievement', '全国通用人工智能挑战赛国家二等奖',
                    '{}', '[]', 'active', '由经历结果拆分', :created_at, :updated_at
                )
                """
            ),
            {"created_at": now_value, "updated_at": now_value},
        )
        award_id = int(result.lastrowid)
        content = {
            "period": "10.22",
            "issuer": "全国通用人工智能挑战赛",
            "result": "国家二等奖（决赛第二名）",
        }
        bind.execute(
            sa.text(
                """
                INSERT INTO achievement_fact_details(
                    fact_id, period, issuer, result, note,
                    achievement_kind, experience_fact_id
                ) VALUES (
                    :fact_id, '10.22', '全国通用人工智能挑战赛',
                    '国家二等奖（决赛第二名）', '', 'honor', 27
                )
                """
            ),
            {"fact_id": award_id},
        )
        bind.execute(
            sa.text("UPDATE fact_records SET content=:content WHERE id=:fact_id"),
            {
                "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
                "fact_id": award_id,
            },
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_audits(
                    workspace_id, fact_id, action, summary,
                    before_content, after_content, created_at
                ) VALUES (1, :fact_id, 'created', '从竞赛结果拆分成果',
                          '{}', :content, :created_at)
                """
            ),
            {
                "fact_id": award_id,
                "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
                "created_at": now_value,
            },
        )


def _make_skills_atomic(bind: sa.Connection) -> None:
    combined = bind.execute(
        sa.text(
            """
            SELECT f.id FROM fact_records f
             WHERE f.category='skill'
               AND f.title='Isaac Sim / Gazebo / CoppeliaSim'
             LIMIT 1
            """
        )
    ).scalar()
    if combined:
        bind.execute(
            sa.text("UPDATE fact_records SET title='Isaac Sim' WHERE id=:id"),
            {"id": combined},
        )
        for title in ("Gazebo", "CoppeliaSim"):
            exists = bind.execute(
                sa.text(
                    "SELECT id FROM fact_records WHERE workspace_id=1 AND category='skill' AND title=:title"
                ),
                {"title": title},
            ).scalar()
            if exists:
                continue
            now_value = _now()
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO fact_records(
                        workspace_id, category, title, content, tags, status,
                        source_note, created_at, updated_at
                    ) VALUES (
                        1, 'skill', :title, '{}', '[]', 'active',
                        '从组合技能拆分', :created_at, :updated_at
                    )
                    """
                ),
                {"title": title, "created_at": now_value, "updated_at": now_value},
            )
            detail_id = int(result.lastrowid)
            content = {
                "skill_category": "仿真平台",
                "proficiency": "能用",
                "context": "机器人课程项目与实验室任务",
            }
            bind.execute(
                sa.text(
                    """
                    INSERT INTO skill_fact_details(
                        fact_id, skill_category, proficiency, context
                    ) VALUES (:fact_id, '仿真平台', '能用', '机器人课程项目与实验室任务')
                    """
                ),
                {"fact_id": detail_id},
            )
            bind.execute(
                sa.text("UPDATE fact_records SET content=:content WHERE id=:fact_id"),
                {
                    "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
                    "fact_id": detail_id,
                },
            )

    additions = {
        "嵌入式开发": {
            "skill_category": "机器人开发",
            "proficiency": "能用",
            "context": "开源鸿蒙智能台灯项目",
        },
        "UE5": {
            "skill_category": "仿真平台",
            "proficiency": "能用",
            "context": "通用人工智能挑战赛 Agent 场景开发",
        },
        "TongSim": {
            "skill_category": "仿真平台",
            "proficiency": "能用",
            "context": "通用人工智能挑战赛多场景仿真",
        },
        "Agent 设计与仿真": {
            "skill_category": "视觉与模型",
            "proficiency": "能用",
            "context": "密室逃脱多场景全流程任务",
        },
    }
    for title, content in additions.items():
        exists = bind.execute(
            sa.text(
                "SELECT id FROM fact_records WHERE workspace_id=1 AND category='skill' AND title=:title"
            ),
            {"title": title},
        ).scalar()
        if exists:
            continue
        now_value = _now()
        result = bind.execute(
            sa.text(
                """
                INSERT INTO fact_records(
                    workspace_id, category, title, content, tags, status,
                    source_note, created_at, updated_at
                ) VALUES (
                    1, 'skill', :title, :content, '[]', 'active',
                    '重组时补充', :created_at, :updated_at
                )
                """
            ),
            {
                "title": title,
                "content": json.dumps(content, ensure_ascii=False, sort_keys=True),
                "created_at": now_value,
                "updated_at": now_value,
            },
        )
        skill_id = int(result.lastrowid)
        bind.execute(
            sa.text(
                """
                INSERT INTO skill_fact_details(
                    fact_id, skill_category, proficiency, context
                ) VALUES (:fact_id, :group_name, :proficiency, :context)
                """
            ),
            {
                "fact_id": skill_id,
                "group_name": content["skill_category"],
                "proficiency": content["proficiency"],
                "context": content["context"],
            },
        )


def _build_relations(bind: sa.Connection) -> None:
    title_to_id = {
        row["title"]: row["id"]
        for row in bind.execute(
            sa.text(
                "SELECT id, title FROM fact_records WHERE workspace_id=1 AND status='active'"
            )
        ).mappings()
    }
    links = {
        "机器人数据采集与模仿学习项目": [
            "Python", "Isaac Sim", "Gazebo", "CoppeliaSim",
            "ACT / Diffusion", "VR 头显与主从机械臂",
        ],
        "优必选机器人教材开发：YOLO 视觉检测与 IK": [
            "C/C++", "Python", "YOLO", "ROS2", "Gazebo", "Windows + WSL / Ubuntu",
        ],
        "基于 YOLO 的跌倒检测系统": ["Python", "YOLO"],
        "基于 Isaac Sim 的小车自主走迷宫": [
            "Python", "Isaac Sim", "Windows + WSL / Ubuntu",
        ],
        "B 站弹幕网页爬虫与数据分析": ["Python"],
        "城市餐饮数据分析": ["Python"],
        "智能台灯：鸿蒙星闪应用": ["嵌入式开发"],
        "蓝桥杯与码蹄杯算法竞赛": ["C/C++"],
        "全国通用人工智能挑战赛": ["UE5", "TongSim", "Agent 设计与仿真"],
    }
    for experience_title, skill_titles in links.items():
        experience_id = title_to_id.get(experience_title)
        if not experience_id:
            continue
        for skill_title in skill_titles:
            skill_id = title_to_id.get(skill_title)
            if not skill_id:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT OR IGNORE INTO experience_skill_links(
                        workspace_id, experience_fact_id, skill_fact_id
                    ) VALUES (1, :experience_id, :skill_id)
                    """
                ),
                {"experience_id": experience_id, "skill_id": skill_id},
            )


def _apply_tags(bind: sa.Connection) -> None:
    aliases = {
        "视觉": "计算机视觉",
        "计算机视觉": "计算机视觉",
        "设备开发": "嵌入式与设备",
        "鸿蒙": "嵌入式与设备",
        "嵌入式": "嵌入式与设备",
        "模型训练": "模型训练",
        "机器学习": "模型训练",
        "算法": "算法",
        "数据分析": "数据分析",
        "数据采集": "数据采集",
        "数据标注": "数据采集",
        "具身智能": "具身智能",
        "机器人": "机器人",
        "仿真": "仿真",
    }
    ignored = {
        "python", "yolo", "ros2", "c++", "isaac sim", "vr", "linux",
        "开发工具", "数据结构", "竞赛", "爬虫", "自动化",
    }
    rows = bind.execute(
        sa.text("SELECT id, category, title, tags FROM fact_records WHERE status='active'")
    ).mappings()
    now_value = _now()
    for row in rows:
        try:
            raw = json.loads(row["tags"] or "[]")
        except (TypeError, json.JSONDecodeError):
            raw = []
        desired = {
            aliases[value]
            for value in raw
            if value not in ignored and value in aliases
        }
        if row["category"] == "achievement":
            desired = set()
        if row["title"] == "优必选机器人教材开发：YOLO 视觉检测与 IK":
            desired.add("计算机视觉")
        if row["title"] == "智能台灯：鸿蒙星闪应用":
            desired.add("嵌入式与设备")
        if row["title"] == "全国通用人工智能挑战赛":
            desired.update({"具身智能", "仿真"})
        if row["title"] == "越疆 X-Trainer 竞赛":
            desired.update({"机器人", "竞赛"})
        elif row["title"] == "优必选天工无疆全球人形机器人挑战赛":
            desired.update({"机器人", "具身智能", "竞赛"})
        elif row["title"] == "蓝桥杯 / 码蹄杯算法竞赛":
            desired.add("算法竞赛")
        if row["title"] == "全国通用人工智能挑战赛国家二等奖":
            desired.update({"机器人", "具身智能", "竞赛"})
        clean = sorted(desired)
        bind.execute(
            sa.text("UPDATE fact_records SET tags=:tags WHERE id=:id"),
            {"tags": json.dumps(clean, ensure_ascii=False), "id": row["id"]},
        )
        for tag_name in clean:
            normalized = tag_name.strip().lower()
            tag_id = bind.execute(
                sa.text(
                    "SELECT id FROM tags WHERE workspace_id=1 AND normalized_name=:normalized"
                ),
                {"normalized": normalized},
            ).scalar()
            if tag_id is None:
                tag_id = int(
                    bind.execute(
                        sa.text(
                            """
                            INSERT INTO tags(
                                workspace_id, display_name, normalized_name, status, created_at
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
                {"fact_id": row["id"], "tag_id": tag_id},
            )


def _hide_test_data(bind: sa.Connection) -> None:
    now_value = _now()
    test_profiles = bind.execute(
        sa.text(
            """
            SELECT id FROM requirement_profiles
             WHERE lower(name) LIKE '%test%'
                OR name LIKE '%交互测试%'
                OR name LIKE '%交互验证%'
                OR name LIKE '%GUI测试%'
                OR name='后端开发'
            """
        )
    ).scalars().all()
    bind.execute(
        sa.text(
            """
            UPDATE fact_records
               SET status='recycled', deleted_at=:now
             WHERE status='active'
               AND (
                   lower(title) LIKE '%test%'
                   OR title LIKE '%交互测试%'
                   OR title LIKE '%GUI测试%'
               )
            """
        ),
        {"now": now_value},
    )
    for profile_id in test_profiles:
        bind.execute(
            sa.text(
                "UPDATE requirement_profiles SET status='recycled', recycled_at=:now WHERE id=:id"
            ),
            {"now": now_value, "id": profile_id},
        )
    if test_profiles:
        placeholders = ",".join(f":p{i}" for i in range(len(test_profiles)))
        params = {f"p{i}": value for i, value in enumerate(test_profiles)}
        params["now"] = now_value
        bind.execute(
            sa.text(
                f"""
                UPDATE resumes SET status='recycled', recycled_at=:now
                 WHERE requirement_profile_id IN ({placeholders})
                   AND status='active'
                """
            ),
            params,
        )
        bind.execute(
            sa.text(
                f"""
                UPDATE linked_resumes SET status='abandoned'
                 WHERE requirement_profile_id IN ({placeholders})
                   AND status='open'
                """
            ),
            params,
        )
    bind.execute(
        sa.text(
            """
            UPDATE pending_issues
               SET status='dismissed', resolved_at=:now
             WHERE status='open'
               AND (
                   fact_id IN (SELECT id FROM fact_records WHERE status='recycled')
                   OR resume_id IN (SELECT id FROM resumes WHERE status='recycled')
               )
            """
        ),
        {"now": now_value},
    )


def _refresh_current_working_copy(bind: sa.Connection) -> None:
    row = bind.execute(
        sa.text(
            "SELECT id, content_json FROM resume_working_copies WHERE resume_id=1"
        )
    ).mappings().first()
    profile = bind.execute(
        sa.text(
            "SELECT personal_summary, desired_city, availability FROM requirement_profiles WHERE id=1"
        )
    ).mappings().first()
    if not row or not profile:
        return
    content = json.loads(row["content_json"] or "{}")
    changed = False
    for section in content.get("sections", []):
        if section.get("id") == "basics":
            for block in section.get("blocks", []):
                fields = block.get("fields") or {}
                before = dict(fields)
                for key in ("bio", "desired_city", "availability"):
                    fields.pop(key, None)
                block["fields"] = fields
                block["display_fields"] = [
                    key
                    for key in block.get("display_fields", [])
                    if key not in {"bio", "desired_city", "availability"}
                ]
                changed = changed or before != fields
        if section.get("id") == "profile" and not section.get("blocks") and profile["personal_summary"]:
            section["blocks"] = [
                {
                    "id": "profile-summary",
                    "type": "profile",
                    "title": "个人简介",
                    "content": profile["personal_summary"],
                    "fields": {},
                    "field_labels": {},
                    "display_fields": [],
                    "source_refs": [],
                    "origin": "profile",
                }
            ]
            changed = True
        if section.get("id") == "experience":
            for block in section.get("blocks", []):
                if 3 in block.get("source_refs", []):
                    block["title"] = "机器人数据采集与模仿学习项目"
                    changed = True
    if changed:
        bind.execute(
            sa.text(
                """
                UPDATE resume_working_copies
                   SET content_json=:content, content_state='dirty', updated_at=:now
                 WHERE id=:id
                """
            ),
            {
                "content": json.dumps(content, ensure_ascii=False),
                "now": _now(),
                "id": row["id"],
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    if "fact_categories" in sa.inspect(bind).get_table_names():
        return
    _add_columns()
    _create_relation_tables()
    # This revision also carries the one-time normalization of the local
    # workspace data. A newly created database has no facts to normalize.
    if bind.execute(sa.text("SELECT 1 FROM fact_records LIMIT 1")).scalar():
        _restore_basics_and_profile(bind)
        _migrate_classifications(bind)
        _make_skills_atomic(bind)
        _build_relations(bind)
        _apply_tags(bind)
        _hide_test_data(bind)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_basics "
        "ON fact_records(workspace_id) WHERE category='basics' AND status='active'"
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_fact_category_immutable
        BEFORE UPDATE OF category ON fact_records
        WHEN NEW.category <> OLD.category
        BEGIN
            SELECT RAISE(ABORT, 'fact category is immutable');
        END
        """
    )
    if bind.execute(sa.text("SELECT 1 FROM resume_working_copies LIMIT 1")).scalar():
        _refresh_current_working_copy(bind)


def downgrade() -> None:
    raise RuntimeError(
        "Resource reorganization is data-normalizing and intentionally irreversible; "
        "restore the pre-0009 database backup if required."
    )
