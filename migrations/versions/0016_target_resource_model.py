"""Replace the resource compatibility schema with the target strong-type model."""

from __future__ import annotations

import json
import re

import sqlalchemy as sa
from alembic import op


revision = "0016_target_resource_model"
down_revision = "0015_fix_competition_experience_parents"
branch_labels = None
depends_on = None


CATEGORIES = {
    "basics": ("基本信息", 10, 1),
    "education": ("教育经历", 20, 2),
    "experience": ("经历", 30, 3),
    "skill": ("技能", 40, 4),
    "achievement": ("成果", 50, 5),
}

FIELD_ROWS = [
    ("basics", 1, "name", "姓名", "text", "required_for_output", "fact_basics_details", "name", 10),
    ("basics", 1, "phone", "电话", "text", "recommended", "fact_basics_details", "phone", 20),
    ("basics", 1, "email", "邮箱", "text", "recommended", "fact_basics_details", "email", 30),
    ("basics", 1, "city", "所在地", "text", "optional", "fact_basics_details", "city", 40),
    ("basics", 1, "desired_city", "目标城市", "text", "optional", "fact_basics_details", "desired_city", 50),
    ("basics", 1, "birth_date", "出生日期", "date", "optional", "fact_basics_details", "birth_date", 60),
    ("basics", 1, "age_text", "年龄", "text", "optional", "fact_basics_details", "age_text", 70),
    ("basics", 1, "hometown", "籍贯", "text", "optional", "fact_basics_details", "hometown", 80),
    ("basics", 1, "identity_status", "身份状态", "text", "optional", "fact_basics_details", "identity_status", 90),
    ("basics", 1, "graduation_date", "毕业时间", "year_month", "optional", "fact_basics_details", "graduation_date", 100),
    ("basics", 1, "availability", "到岗安排", "long_text", "optional", "fact_basics_details", "availability", 110),
    ("basics", 1, "bio", "个人简介", "long_text", "optional", "fact_basics_details", "bio", 120),
    ("education", 2, "school", "学校", "text", "required_for_output", "fact_education_details", "school", 10),
    ("education", 2, "major", "专业", "text", "optional", "fact_education_details", "major", 20),
    ("education", 2, "degree", "学历", "text", "recommended", "fact_education_details", "degree", 30),
    ("education", 2, "start_date", "入学时间", "year_month", "optional", "fact_education_details", "start_date", 40),
    ("education", 2, "end_date", "毕业时间", "year_month", "optional", "fact_education_details", "end_date", 50),
    ("education", 2, "period_text", "展示时间段", "text", "optional", "fact_education_details", "period_text", 60),
    ("education", 2, "gpa", "GPA", "text", "optional", "fact_education_details", "gpa", 70),
    ("education", 2, "ranking", "排名", "text", "optional", "fact_education_details", "ranking", 80),
    ("education", 2, "achievement", "成绩与成果", "long_text", "optional", "fact_education_details", "achievement", 90),
    ("education", 2, "courses", "相关课程", "long_text", "optional", "fact_education_details", "courses", 100),
    ("experience", 3, "experience_kind", "经历类型", "enum", "required_for_output", "fact_experience_details", "experience_kind", 10),
    ("experience", 3, "period_text", "展示时间段", "text", "recommended", "fact_experience_details", "period_text", 20),
    ("experience", 3, "start_date", "开始时间", "year_month", "optional", "fact_experience_details", "start_date", 30),
    ("experience", 3, "end_date", "结束时间", "year_month", "optional", "fact_experience_details", "end_date", 40),
    ("experience", 3, "organization", "组织/公司", "text", "optional", "fact_experience_details", "organization", 50),
    ("experience", 3, "role", "角色", "text", "optional", "fact_experience_details", "role", 60),
    ("experience", 3, "team_size", "团队规模", "text", "optional", "fact_experience_details", "team_size", 70),
    ("experience", 3, "context_summary", "背景", "long_text", "optional", "fact_experience_details", "context_summary", 80),
    ("experience", 3, "work_summary", "具体工作", "long_text", "recommended", "fact_experience_details", "work_summary", 90),
    ("experience", 3, "tools_summary", "工具与技术", "long_text", "optional", "fact_experience_details", "tools_summary", 100),
    ("experience", 3, "result_summary", "结果摘要", "long_text", "optional", "fact_experience_details", "result_summary", 110),
    ("experience", 3, "challenge", "挑战", "long_text", "optional", "fact_experience_details", "challenge", 120),
    ("experience", 3, "solution", "解决方案", "long_text", "optional", "fact_experience_details", "solution", 130),
    ("experience", 3, "public_note", "公开说明", "long_text", "optional", "fact_experience_details", "public_note", 140),
    ("skill", 4, "skill_group_id", "技能分组", "integer", "recommended", "fact_skill_details", "skill_group_id", 10),
    ("skill", 4, "proficiency", "熟练程度", "text", "optional", "fact_skill_details", "proficiency", 20),
    ("skill", 4, "usage_context", "使用场景", "long_text", "optional", "fact_skill_details", "usage_context", 30),
    ("achievement", 5, "achievement_kind", "成果类型", "enum", "required_for_output", "fact_achievement_details", "achievement_kind", 10),
    ("achievement", 5, "period_text", "展示时间段", "text", "optional", "fact_achievement_details", "period_text", 20),
    ("achievement", 5, "occurred_on", "取得日期", "date", "optional", "fact_achievement_details", "occurred_on", 30),
    ("achievement", 5, "issuer", "颁发方", "text", "optional", "fact_achievement_details", "issuer", 40),
    ("achievement", 5, "result_text", "成果内容", "text", "required_for_output", "fact_achievement_details", "result_text", 50),
    ("achievement", 5, "note", "说明", "long_text", "optional", "fact_achievement_details", "note", 60),
    ("achievement", 5, "experience_fact_id", "主经历", "integer", "optional", "fact_achievement_details", "experience_fact_id", 70),
]

SCHEMA_SQL = (
    """
    CREATE TABLE fact_categories (
        code TEXT PRIMARY KEY CHECK (code IN ('basics','education','experience','skill','achievement')),
        display_name TEXT NOT NULL,
        sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated'))
    ) STRICT
    """,
    """
    CREATE TABLE fact_schema_versions (
        id INTEGER PRIMARY KEY,
        category_code TEXT NOT NULL REFERENCES fact_categories(code) ON DELETE RESTRICT,
        version_number INTEGER NOT NULL CHECK (version_number > 0),
        status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft','published','retired')),
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE (category_code, version_number),
        UNIQUE (category_code, id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_field_definitions (
        id INTEGER PRIMARY KEY,
        category_code TEXT NOT NULL,
        schema_version_id INTEGER NOT NULL,
        field_key TEXT NOT NULL,
        label TEXT NOT NULL,
        value_type TEXT NOT NULL CHECK (value_type IN ('text','long_text','number','date','year_month','url','enum','boolean','integer')),
        requirement_level TEXT NOT NULL DEFAULT 'optional' CHECK (requirement_level IN ('optional','recommended','required_for_output')),
        is_extension INTEGER NOT NULL DEFAULT 0 CHECK (is_extension IN (0,1)),
        storage_table TEXT NOT NULL,
        storage_column TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
        FOREIGN KEY (category_code, schema_version_id)
            REFERENCES fact_schema_versions(category_code, id) ON DELETE RESTRICT,
        UNIQUE (schema_version_id, field_key),
        UNIQUE (id, category_code, schema_version_id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_records (
        id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
        category_code TEXT NOT NULL REFERENCES fact_categories(code) ON DELETE RESTRICT,
        schema_version_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        business_key TEXT CHECK (business_key IS NULL OR length(trim(business_key)) > 0),
        source_note TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','recycled','purged')),
        archived_at TEXT,
        recycled_at TEXT,
        purged_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (category_code, schema_version_id)
            REFERENCES fact_schema_versions(category_code, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, id),
        UNIQUE (workspace_id, id, category_code),
        UNIQUE (workspace_id, id, category_code, schema_version_id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_basics_details (
        fact_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL,
        category_code TEXT NOT NULL DEFAULT 'basics' CHECK (category_code = 'basics'),
        name TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '', city TEXT NOT NULL DEFAULT '',
        desired_city TEXT NOT NULL DEFAULT '', birth_date TEXT NOT NULL DEFAULT '',
        age_text TEXT NOT NULL DEFAULT '', hometown TEXT NOT NULL DEFAULT '',
        identity_status TEXT NOT NULL DEFAULT '', graduation_date TEXT NOT NULL DEFAULT '',
        availability TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, fact_id, category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
    ) STRICT
    """,
    """
    CREATE TABLE fact_education_details (
        fact_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL,
        category_code TEXT NOT NULL DEFAULT 'education' CHECK (category_code = 'education'),
        school TEXT NOT NULL DEFAULT '', major TEXT NOT NULL DEFAULT '',
        degree TEXT NOT NULL DEFAULT '', start_date TEXT NOT NULL DEFAULT '',
        end_date TEXT NOT NULL DEFAULT '', period_text TEXT NOT NULL DEFAULT '',
        gpa TEXT NOT NULL DEFAULT '', ranking TEXT NOT NULL DEFAULT '',
        achievement TEXT NOT NULL DEFAULT '', courses TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, fact_id, category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
    ) STRICT
    """,
    """
    CREATE TABLE fact_experience_details (
        fact_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL,
        category_code TEXT NOT NULL DEFAULT 'experience' CHECK (category_code = 'experience'),
        experience_kind TEXT NOT NULL DEFAULT 'project'
            CHECK (experience_kind IN ('project','work_internship','competition','research','campus_volunteer','other')),
        period_text TEXT NOT NULL DEFAULT '', start_date TEXT NOT NULL DEFAULT '',
        end_date TEXT NOT NULL DEFAULT '', organization TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT '', team_size TEXT NOT NULL DEFAULT '',
        context_summary TEXT NOT NULL DEFAULT '', work_summary TEXT NOT NULL DEFAULT '',
        tools_summary TEXT NOT NULL DEFAULT '', result_summary TEXT NOT NULL DEFAULT '',
        challenge TEXT NOT NULL DEFAULT '', solution TEXT NOT NULL DEFAULT '',
        public_note TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, fact_id, category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
    ) STRICT
    """,
    """
    CREATE TABLE skill_groups (
        id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
        code TEXT NOT NULL, display_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
        UNIQUE (workspace_id, code), UNIQUE (workspace_id, normalized_name), UNIQUE (workspace_id, id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_skill_details (
        fact_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL,
        category_code TEXT NOT NULL DEFAULT 'skill' CHECK (category_code = 'skill'),
        skill_group_id INTEGER NOT NULL, proficiency TEXT NOT NULL DEFAULT '',
        usage_context TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, fact_id, category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, skill_group_id)
            REFERENCES skill_groups(workspace_id, id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE fact_achievement_details (
        fact_id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL,
        category_code TEXT NOT NULL DEFAULT 'achievement' CHECK (category_code = 'achievement'),
        achievement_kind TEXT NOT NULL DEFAULT 'honor'
            CHECK (achievement_kind IN ('honor','certificate','publication_patent','project_result','other')),
        period_text TEXT NOT NULL DEFAULT '', occurred_on TEXT NOT NULL DEFAULT '',
        issuer TEXT NOT NULL DEFAULT '', result_text TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '', experience_fact_id INTEGER,
        parent_category_code TEXT NOT NULL DEFAULT 'experience' CHECK (parent_category_code = 'experience'),
        FOREIGN KEY (workspace_id, fact_id, category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, experience_fact_id, parent_category_code)
            REFERENCES fact_records(workspace_id, id, category_code) ON DELETE RESTRICT,
        CHECK (experience_fact_id IS NULL OR experience_fact_id <> fact_id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_extension_values (
        id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL, fact_id INTEGER NOT NULL,
        category_code TEXT NOT NULL, schema_version_id INTEGER NOT NULL,
        field_definition_id INTEGER NOT NULL,
        text_value TEXT, numeric_value REAL,
        boolean_value INTEGER CHECK (boolean_value IS NULL OR boolean_value IN (0,1)),
        json_value TEXT CHECK (json_value IS NULL OR json_valid(json_value)),
        FOREIGN KEY (workspace_id, fact_id, category_code, schema_version_id)
            REFERENCES fact_records(workspace_id, id, category_code, schema_version_id) ON DELETE CASCADE,
        FOREIGN KEY (field_definition_id, category_code, schema_version_id)
            REFERENCES fact_field_definitions(id, category_code, schema_version_id) ON DELETE RESTRICT,
        UNIQUE (fact_id, field_definition_id),
        CHECK ((text_value IS NOT NULL)+(numeric_value IS NOT NULL)+(boolean_value IS NOT NULL)+(json_value IS NOT NULL)=1)
    ) STRICT
    """,
    """
    CREATE TABLE tags (
        id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
        display_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','merged')),
        merged_into_tag_id INTEGER, created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id, merged_into_tag_id) REFERENCES tags(workspace_id, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, normalized_name), UNIQUE (workspace_id, id)
    ) STRICT
    """,
    """
    CREATE TABLE tag_aliases (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
        alias TEXT NOT NULL, normalized_alias TEXT NOT NULL,
        FOREIGN KEY (workspace_id, tag_id) REFERENCES tags(workspace_id, id) ON DELETE CASCADE,
        UNIQUE (workspace_id, normalized_alias)
    ) STRICT
    """,
    """
    CREATE TABLE fact_tags (
        workspace_id INTEGER NOT NULL, fact_id INTEGER NOT NULL, tag_id INTEGER NOT NULL,
        PRIMARY KEY (workspace_id, fact_id, tag_id),
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, tag_id) REFERENCES tags(workspace_id, id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE evidence (
        id INTEGER PRIMARY KEY,
        workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
        kind TEXT NOT NULL CHECK (kind IN ('file','link','note')),
        title TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', storage_key TEXT NOT NULL DEFAULT '',
        filename TEXT NOT NULL DEFAULT '', mime_type TEXT NOT NULL DEFAULT '',
        size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
        checksum TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','invalid','archived')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        CHECK (
            (kind='link' AND length(trim(url))>0 AND storage_key='' AND filename='' AND mime_type='' AND size_bytes=0 AND checksum='')
            OR (kind='file' AND url='' AND length(trim(storage_key))>0 AND length(trim(filename))>0 AND length(trim(mime_type))>0 AND size_bytes>0 AND size_bytes<=10485760 AND length(checksum)=64)
            OR (kind='note' AND url='' AND storage_key='' AND filename='' AND mime_type='' AND size_bytes=0 AND checksum='' AND length(trim(note))>0)
        ),
        UNIQUE (workspace_id, id)
    ) STRICT
    """,
    """
    CREATE TABLE fact_evidence (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, fact_id INTEGER NOT NULL,
        evidence_id INTEGER NOT NULL, relation_note TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
        UNIQUE (workspace_id, fact_id, evidence_id),
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, evidence_id) REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE fact_audit_events (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, fact_id INTEGER NOT NULL,
        actor_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        action TEXT NOT NULL CHECK (action IN ('created','updated','archived','restored','recycled','purged','reclassified','merged','split','tag_changed','evidence_changed')),
        schema_version_id INTEGER, changed_fields TEXT NOT NULL,
        before_values TEXT NOT NULL, after_values TEXT NOT NULL,
        related_fact_ids TEXT NOT NULL DEFAULT '[]', reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
        FOREIGN KEY (schema_version_id) REFERENCES fact_schema_versions(id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE evidence_audit_events (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, evidence_id INTEGER NOT NULL,
        actor_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        action TEXT NOT NULL CHECK (action IN ('created','updated_metadata','marked_invalid','marked_active','archived')),
        changed_fields TEXT NOT NULL, before_values TEXT NOT NULL, after_values TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
        FOREIGN KEY (workspace_id, evidence_id) REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT
    ) STRICT
    """,
    """
    CREATE TABLE experience_skill_links (
        workspace_id INTEGER NOT NULL, experience_fact_id INTEGER NOT NULL,
        skill_fact_id INTEGER NOT NULL,
        experience_category TEXT NOT NULL DEFAULT 'experience' CHECK (experience_category='experience'),
        skill_category TEXT NOT NULL DEFAULT 'skill' CHECK (skill_category='skill'),
        PRIMARY KEY (workspace_id, experience_fact_id, skill_fact_id),
        FOREIGN KEY (workspace_id, experience_fact_id, experience_category) REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, skill_fact_id, skill_category) REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
        CHECK (experience_fact_id <> skill_fact_id)
    ) STRICT
    """,
    """
    CREATE TABLE resume_fact_uses (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, resume_id INTEGER NOT NULL,
        fact_id INTEGER NOT NULL, section_code TEXT NOT NULL, block_key TEXT NOT NULL,
        display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
        fact_content_hash TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, resume_id) REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, resume_id, fact_id, section_code, block_key)
    ) STRICT
    """,
    """
    CREATE TABLE resume_version_fact_snapshots (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, resume_version_id INTEGER NOT NULL,
        fact_id INTEGER NOT NULL, section_code TEXT NOT NULL, block_key TEXT NOT NULL,
        display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
        fact_content_hash TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (workspace_id, resume_version_id) REFERENCES resume_versions(workspace_id, id) ON DELETE RESTRICT,
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, resume_version_id, fact_id, section_code, block_key)
    ) STRICT
    """,
    """
    CREATE TABLE resume_evidence_uses (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, resume_id INTEGER NOT NULL,
        evidence_id INTEGER NOT NULL, section_code TEXT NOT NULL, block_key TEXT NOT NULL,
        display_mode TEXT NOT NULL CHECK (display_mode IN ('hidden','inline_link','attachment','reference')),
        label TEXT NOT NULL DEFAULT '', display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
        FOREIGN KEY (workspace_id, resume_id) REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, evidence_id) REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, resume_id, evidence_id, section_code, block_key)
    ) STRICT
    """,
    """
    CREATE TABLE resume_version_evidence_snapshots (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, resume_version_id INTEGER NOT NULL,
        evidence_id INTEGER NOT NULL, section_code TEXT NOT NULL, block_key TEXT NOT NULL,
        display_mode TEXT NOT NULL CHECK (display_mode IN ('hidden','inline_link','attachment','reference')),
        label TEXT NOT NULL DEFAULT '', display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
        FOREIGN KEY (workspace_id, resume_version_id) REFERENCES resume_versions(workspace_id, id) ON DELETE RESTRICT,
        FOREIGN KEY (workspace_id, evidence_id) REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT,
        UNIQUE (workspace_id, resume_version_id, evidence_id, section_code, block_key)
    ) STRICT
    """,
    """
    CREATE TABLE pending_issues (
        id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('source_changed','source_recycled','evidence_sync','evidence_conflict','profile_changed','export_warning','other')),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','dismissed')),
        fact_id INTEGER, evidence_id INTEGER, profile_id INTEGER, resume_id INTEGER,
        section_code TEXT NOT NULL DEFAULT '', block_key TEXT NOT NULL DEFAULT '',
        message TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT,
        FOREIGN KEY (workspace_id, fact_id) REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, evidence_id) REFERENCES evidence(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, profile_id) REFERENCES requirement_profiles(workspace_id, id) ON DELETE CASCADE,
        FOREIGN KEY (workspace_id, resume_id) REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
        CHECK ((fact_id IS NOT NULL)+(evidence_id IS NOT NULL)+(profile_id IS NOT NULL)+(resume_id IS NOT NULL) >= 1)
    ) STRICT
    """,
)


TRIGGERS = (
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_resumes_workspace_id_id
    ON resumes(workspace_id, id)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_resume_versions_workspace_id_id
    ON resume_versions(workspace_id, id)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_requirement_profiles_workspace_id_id
    ON requirement_profiles(workspace_id, id)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_business_key_live ON fact_records(workspace_id, category_code, business_key)
    WHERE business_key IS NOT NULL AND status IN ('active','archived','recycled')
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_one_live_basics_per_workspace ON fact_records(workspace_id)
    WHERE category_code='basics' AND status IN ('active','archived','recycled')
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_schema_current_published ON fact_schema_versions(category_code)
    WHERE status='published'
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_file_checksum ON evidence(workspace_id, checksum)
    WHERE kind='file'
    """,
    """
    CREATE TRIGGER trg_fact_business_key_required BEFORE INSERT ON fact_records
    WHEN NEW.status <> 'purged' AND (NEW.business_key IS NULL OR length(trim(NEW.business_key))=0)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-001: live fact requires business_key'); END
    """,
    """
    CREATE TRIGGER trg_fact_category_immutable BEFORE UPDATE OF category_code ON fact_records
    WHEN NEW.category_code <> OLD.category_code
    BEGIN SELECT RAISE(ABORT, 'RL-INV-002: fact category is immutable'); END
    """,
    """
    CREATE TRIGGER trg_fact_status_transition BEFORE UPDATE OF status ON fact_records
    WHEN NEW.status <> OLD.status AND NOT (
        (OLD.status='active' AND NEW.status IN ('archived','recycled'))
        OR (OLD.status='archived' AND NEW.status IN ('active','recycled'))
        OR (OLD.status='recycled' AND NEW.status IN ('active','archived','purged'))
    )
    BEGIN SELECT RAISE(ABORT, 'RL-STS-001: invalid fact status transition'); END
    """,
    """
    CREATE TRIGGER trg_fact_purge_reference_guard BEFORE UPDATE OF status ON fact_records
    WHEN NEW.status='purged' AND (
        EXISTS (SELECT 1 FROM resume_fact_uses WHERE workspace_id=OLD.workspace_id AND fact_id=OLD.id)
        OR EXISTS (SELECT 1 FROM resume_version_fact_snapshots WHERE workspace_id=OLD.workspace_id AND fact_id=OLD.id)
        OR EXISTS (SELECT 1 FROM fact_achievement_details WHERE workspace_id=OLD.workspace_id AND experience_fact_id=OLD.id)
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-003: referenced fact cannot be purged'); END
    """,
    """
    CREATE TRIGGER trg_fact_purge_tombstone AFTER UPDATE OF status ON fact_records
    WHEN NEW.status='purged'
    BEGIN
        DELETE FROM fact_basics_details WHERE fact_id=NEW.id;
        DELETE FROM fact_education_details WHERE fact_id=NEW.id;
        DELETE FROM fact_experience_details WHERE fact_id=NEW.id;
        DELETE FROM fact_skill_details WHERE fact_id=NEW.id;
        DELETE FROM fact_achievement_details WHERE fact_id=NEW.id;
        DELETE FROM fact_extension_values WHERE fact_id=NEW.id;
        DELETE FROM fact_tags WHERE fact_id=NEW.id;
        DELETE FROM fact_evidence WHERE fact_id=NEW.id;
        DELETE FROM experience_skill_links WHERE experience_fact_id=NEW.id OR skill_fact_id=NEW.id;
        UPDATE fact_records SET title='[purged]', business_key=NULL, source_note=NULL WHERE id=NEW.id;
    END
    """,
    """
    CREATE TRIGGER trg_extension_value_definition BEFORE INSERT ON fact_extension_values
    WHEN NOT EXISTS (SELECT 1 FROM fact_field_definitions WHERE id=NEW.field_definition_id AND category_code=NEW.category_code AND schema_version_id=NEW.schema_version_id AND is_extension=1)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-004: extension field does not match fact schema'); END
    """,
    """
    CREATE TRIGGER trg_extension_value_type BEFORE INSERT ON fact_extension_values
    WHEN EXISTS (SELECT 1 FROM fact_field_definitions WHERE id=NEW.field_definition_id AND (
        (value_type IN ('text','long_text','date','year_month','url','enum') AND NEW.text_value IS NULL)
        OR (value_type='number' AND NEW.numeric_value IS NULL)
        OR (value_type='boolean' AND NEW.boolean_value IS NULL)
        OR (value_type='integer' AND NEW.json_value IS NULL)
    ))
    BEGIN SELECT RAISE(ABORT, 'RL-INV-005: extension value type mismatch'); END
    """,
    """
    CREATE TRIGGER trg_extension_value_definition_update BEFORE UPDATE ON fact_extension_values
    WHEN NOT EXISTS (
        SELECT 1 FROM fact_field_definitions
        WHERE id=NEW.field_definition_id AND category_code=NEW.category_code
          AND schema_version_id=NEW.schema_version_id AND is_extension=1
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-018: extension field does not match fact schema'); END
    """,
    """
    CREATE TRIGGER trg_extension_value_type_update BEFORE UPDATE ON fact_extension_values
    WHEN EXISTS (
        SELECT 1 FROM fact_field_definitions
        WHERE id=NEW.field_definition_id AND (
            (value_type IN ('text','long_text','date','year_month','url','enum') AND NEW.text_value IS NULL)
            OR (value_type='number' AND NEW.numeric_value IS NULL)
            OR (value_type='boolean' AND NEW.boolean_value IS NULL)
            OR (value_type='integer' AND NEW.json_value IS NULL)
        )
    )
    BEGIN SELECT RAISE(ABORT, 'RL-INV-018: extension value type mismatch'); END
    """,
    """
    CREATE TRIGGER trg_field_definition_insert_draft_only BEFORE INSERT ON fact_field_definitions
    WHEN NOT EXISTS (SELECT 1 FROM fact_schema_versions WHERE id=NEW.schema_version_id AND status='draft')
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: fields can only be added to a draft schema'); END
    """,
    """
    CREATE TRIGGER trg_published_field_definition_no_update BEFORE UPDATE ON fact_field_definitions
    WHEN EXISTS (SELECT 1 FROM fact_schema_versions WHERE id=OLD.schema_version_id AND status IN ('published','retired'))
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable'); END
    """,
    """
    CREATE TRIGGER trg_published_field_definition_no_delete BEFORE DELETE ON fact_field_definitions
    WHEN EXISTS (SELECT 1 FROM fact_schema_versions WHERE id=OLD.schema_version_id AND status IN ('published','retired'))
    BEGIN SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable'); END
    """,
    """
    CREATE TRIGGER trg_schema_version_status_transition BEFORE UPDATE OF status ON fact_schema_versions
    WHEN NEW.status <> OLD.status AND NOT (
        (OLD.status='draft' AND NEW.status='published')
        OR (OLD.status='published' AND NEW.status='retired')
    )
    BEGIN SELECT RAISE(ABORT, 'RL-STS-004: invalid schema status transition'); END
    """,
    """
    CREATE TRIGGER trg_evidence_payload_immutable BEFORE UPDATE OF workspace_id,kind,url,storage_key,filename,mime_type,size_bytes,checksum,note ON evidence
    BEGIN SELECT RAISE(ABORT, 'RL-INV-006: evidence payload is immutable'); END
    """,
    """
    CREATE TRIGGER trg_evidence_no_delete BEFORE DELETE ON evidence
    BEGIN SELECT RAISE(ABORT, 'RL-INV-007: evidence cannot be physically deleted'); END
    """,
    """
    CREATE TRIGGER trg_fact_audit_no_update BEFORE UPDATE ON fact_audit_events
    BEGIN SELECT RAISE(ABORT, 'RL-INV-008: fact audit is append-only'); END
    """,
    """
    CREATE TRIGGER trg_fact_audit_no_delete BEFORE DELETE ON fact_audit_events
    BEGIN SELECT RAISE(ABORT, 'RL-INV-008: fact audit is append-only'); END
    """,
    """
    CREATE TRIGGER trg_evidence_audit_no_update BEFORE UPDATE ON evidence_audit_events
    BEGIN SELECT RAISE(ABORT, 'RL-INV-008: evidence audit is append-only'); END
    """,
    """
    CREATE TRIGGER trg_evidence_audit_no_delete BEFORE DELETE ON evidence_audit_events
    BEGIN SELECT RAISE(ABORT, 'RL-INV-008: evidence audit is append-only'); END
    """,
    """
    CREATE TRIGGER trg_tag_name_not_alias BEFORE INSERT ON tags
    WHEN EXISTS (SELECT 1 FROM tag_aliases WHERE workspace_id=NEW.workspace_id AND normalized_alias=NEW.normalized_name)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias'); END
    """,
    """
    CREATE TRIGGER trg_tag_alias_not_name BEFORE INSERT ON tag_aliases
    WHEN EXISTS (SELECT 1 FROM tags WHERE workspace_id=NEW.workspace_id AND normalized_name=NEW.normalized_alias)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name'); END
    """,
    """
    CREATE TRIGGER trg_tag_name_not_alias_update BEFORE UPDATE OF workspace_id,normalized_name ON tags
    WHEN EXISTS (SELECT 1 FROM tag_aliases WHERE workspace_id=NEW.workspace_id AND normalized_alias=NEW.normalized_name)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias'); END
    """,
    """
    CREATE TRIGGER trg_tag_alias_not_name_update BEFORE UPDATE OF workspace_id,normalized_alias ON tag_aliases
    WHEN EXISTS (SELECT 1 FROM tags WHERE workspace_id=NEW.workspace_id AND normalized_name=NEW.normalized_alias)
    BEGIN SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name'); END
    """,
    """
    CREATE TRIGGER trg_fact_tag_requires_active_tag BEFORE INSERT ON fact_tags
    WHEN NOT EXISTS (SELECT 1 FROM tags WHERE workspace_id=NEW.workspace_id AND id=NEW.tag_id AND status='active')
    BEGIN SELECT RAISE(ABORT, 'RL-INV-019: fact tags must reference an active tag'); END
    """,
    """
    CREATE TRIGGER trg_version_fact_snapshot_no_update BEFORE UPDATE ON resume_version_fact_snapshots
    BEGIN SELECT RAISE(ABORT, 'RL-INV-010: version fact snapshot is immutable'); END
    """,
    """
    CREATE TRIGGER trg_version_fact_snapshot_no_delete BEFORE DELETE ON resume_version_fact_snapshots
    BEGIN SELECT RAISE(ABORT, 'RL-INV-010: version fact snapshot is immutable'); END
    """,
    """
    CREATE TRIGGER trg_version_evidence_snapshot_no_update BEFORE UPDATE ON resume_version_evidence_snapshots
    BEGIN SELECT RAISE(ABORT, 'RL-INV-010: version evidence snapshot is immutable'); END
    """,
    """
    CREATE TRIGGER trg_version_evidence_snapshot_no_delete BEFORE DELETE ON resume_version_evidence_snapshots
    BEGIN SELECT RAISE(ABORT, 'RL-INV-010: version evidence snapshot is immutable'); END
    """,
)


def _key(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text.lower() if re.fullmatch(r"[\x00-\x7f ]*", text) else text


def _business_key(category: str, row, used: set[str]) -> str:
    if category == "basics":
        return "primary"
    title = row["title"]
    parts = {
        "education": [row.get("school"), row.get("degree"), row.get("major"), row.get("start_date"), row.get("end_date")],
        "experience": [row.get("kind"), row.get("organization"), title, row.get("start_date"), row.get("end_date")],
        "skill": [title],
        "achievement": [row.get("achievement_kind"), row.get("issuer"), row.get("result"), row.get("occurred_on"), row.get("experience_fact_id")],
    }.get(category, [title])
    key = "|".join(_key(value) for value in parts if str(value or "").strip()) or _key(title) or category
    if key in used:
        key = f"{key}#{row['id']}"
    used.add(key)
    return key


def _drop_compatibility_triggers(bind: sa.Connection) -> None:
    for name in (
        "trg_fact_category_valid",
        "trg_fact_category_immutable",
        "trg_fact_audit_no_update",
        "trg_fact_audit_no_delete",
        "trg_evidence_no_delete",
        "trg_evidence_payload_immutable",
        "trg_version_fact_snapshot_no_update",
        "trg_version_fact_snapshot_no_delete",
        "trg_version_evidence_snapshot_no_update",
        "trg_version_evidence_snapshot_no_delete",
    ):
        bind.execute(sa.text(f'DROP TRIGGER IF EXISTS "{name}"'))


def _seed_catalog(bind: sa.Connection) -> None:
    if bind.execute(sa.text("SELECT count(*) FROM fact_categories")).scalar():
        return
    for code, (display_name, sort_order, _) in CATEGORIES.items():
        bind.execute(
            sa.text(
                "INSERT INTO fact_categories(code,display_name,sort_order,status) VALUES (:code,:name,:sort,'active')"
            ),
            {"code": code, "name": display_name, "sort": sort_order},
        )
    for code, (_, _, version_id) in CATEGORIES.items():
        bind.execute(
            sa.text(
                "INSERT INTO fact_schema_versions(id,category_code,version_number,status,note,created_at) VALUES (:id,:code,1,'published',:note,strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
            ),
            {
                "id": version_id,
                "code": code,
                "note": f"{display_name_for(code)} v1",
            },
        )
    for category, schema_id, key, label, value_type, requirement, storage_table, storage_column, sort_order in FIELD_ROWS:
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_field_definitions(
                    category_code,schema_version_id,field_key,label,value_type,
                    requirement_level,is_extension,storage_table,storage_column,sort_order
                ) VALUES(:category,:schema,:key,:label,:value_type,:requirement,0,:table,:column,:sort)
                """
            ),
            {
                "category": category,
                "schema": schema_id,
                "key": key,
                "label": label,
                "value_type": value_type,
                "requirement": requirement,
                "table": storage_table,
                "column": storage_column,
                "sort": sort_order,
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "fact_categories" in tables:
        _seed_catalog(bind)
        for statement in TRIGGERS:
            if "CREATE UNIQUE INDEX" in statement:
                bind.execute(sa.text(statement))
            elif "CREATE TRIGGER" in statement:
                name = statement.split("CREATE TRIGGER", 1)[1].split()[0]
                exists = bind.execute(
                    sa.text(
                        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name=:name"
                    ),
                    {"name": name},
                ).scalar()
                if not exists:
                    bind.execute(sa.text(statement))
        return
    _drop_compatibility_triggers(bind)

    # Restore profile-hosted presentation fields into the target basics record.
    if bind.execute(sa.text("SELECT 1 FROM personal_fact_details WHERE fact_id=1")).scalar():
        bind.execute(
            sa.text(
                """
                UPDATE personal_fact_details
                   SET desired_city=COALESCE(NULLIF(desired_city,''),
                       (SELECT desired_city FROM requirement_profiles WHERE status='active' ORDER BY id LIMIT 1), ''),
                       availability=COALESCE(NULLIF(availability,''),
                       (SELECT availability FROM requirement_profiles WHERE status='active' ORDER BY id LIMIT 1), ''),
                       bio=COALESCE(NULLIF(bio,''),
                       (SELECT personal_summary FROM requirement_profiles WHERE status='active' ORDER BY id LIMIT 1), '')
                 WHERE fact_id=1
                """
            )
        )

    rename_map = {
        "fact_records": "legacy_fact_records",
        "personal_fact_details": "legacy_personal_fact_details",
        "education_fact_details": "legacy_education_fact_details",
        "experience_fact_details": "legacy_experience_fact_details",
        "skill_fact_details": "legacy_skill_fact_details",
        "achievement_fact_details": "legacy_achievement_fact_details",
        "tags": "legacy_tags",
        "fact_tags": "legacy_fact_tags",
        "experience_skill_links": "legacy_experience_skill_links",
        "evidence": "legacy_evidence",
        "fact_evidence": "legacy_fact_evidence",
        "fact_audits": "legacy_fact_audits",
        "resume_fact_uses": "legacy_resume_fact_uses",
        "resume_version_fact_snapshots": "legacy_resume_version_fact_snapshots",
        "resume_evidence_uses": "legacy_resume_evidence_uses",
        "resume_version_evidence_snapshots": "legacy_resume_version_evidence_snapshots",
        "pending_issues": "legacy_pending_issues",
    }
    for source, target in rename_map.items():
        if source in tables:
            bind.execute(sa.text(f'ALTER TABLE "{source}" RENAME TO "{target}"'))

    for statement in SCHEMA_SQL:
        bind.execute(sa.text(statement))
    _seed_catalog(bind)

    legacy_facts = bind.execute(
        sa.text("SELECT * FROM legacy_fact_records ORDER BY id")
    ).mappings().all()
    fact_by_id = {row["id"]: row for row in legacy_facts}
    used_keys: set[str] = set()
    live_basics: set[int] = set()
    duplicate_basics: set[int] = set()
    for row in legacy_facts:
        category = {"skills": "skill", "awards": "achievement"}.get(row["category"], row["category"])
        if category not in CATEGORIES:
            continue
        if (
            category == "basics"
            and row["status"] in {"active", "archived", "recycled"}
        ):
            if row["workspace_id"] in live_basics:
                duplicate_basics.add(row["id"])
            else:
                live_basics.add(row["workspace_id"])
        archived_at = row["created_at"] if row["status"] == "archived" else None
        recycled_at = row["deleted_at"]
        purged_at = row["updated_at"] if row["status"] == "purged" else None
        target_status = (
            "purged" if row["id"] in duplicate_basics else row["status"]
        )
        if target_status == "purged":
            archived_at = None
            recycled_at = row["deleted_at"] or row["updated_at"]
            purged_at = row["updated_at"]
        business_key = (
            None
            if target_status == "purged"
            else _business_key(category, row, used_keys)
        )
        if business_key is not None:
            base_key = business_key
            suffix = 2
            while bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM fact_records
                     WHERE workspace_id=:workspace AND category_code=:category
                       AND business_key=:business_key
                       AND status IN ('active','archived','recycled')
                     LIMIT 1
                    """
                ),
                {
                    "workspace": row["workspace_id"],
                    "category": category,
                    "business_key": business_key,
                },
            ).scalar():
                business_key = f"{base_key}#{suffix}"
                suffix += 1
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_records(
                    id,workspace_id,category_code,schema_version_id,title,business_key,
                    source_note,status,archived_at,recycled_at,purged_at,created_at,updated_at
                ) VALUES(
                    :id,:workspace,:category,:schema,:title,:business_key,
                    :source_note,:status,:archived_at,:recycled_at,:purged_at,:created_at,:updated_at
                )
                """
            ),
            {
                "id": row["id"],
                "workspace": row["workspace_id"],
                "category": category,
                "schema": CATEGORIES[category][2],
                "title": "[purged]" if target_status == "purged" else row["title"],
                "business_key": business_key,
                "source_note": None if target_status == "purged" else row["source_note"],
                "status": target_status,
                "archived_at": archived_at,
                "recycled_at": recycled_at,
                "purged_at": purged_at,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    # Skill groups retain the former free-text groupings as a controlled dictionary.
    raw_skill_rows = bind.execute(
        sa.text(
            """
            SELECT d.fact_id,d.skill_category,d.proficiency,d.context
              FROM legacy_skill_fact_details d
              JOIN fact_records f ON f.id=d.fact_id
              WHERE f.category_code='skill'
            """
        )
    ).mappings().all()
    group_ids: dict[str, int] = {}
    group_order = 10
    for row in raw_skill_rows:
        name = str(row["skill_category"] or "其他").strip() or "其他"
        if name in group_ids:
            continue
        normalized = name.lower()
        code = {
            "编程语言": "programming",
            "视觉与模型": "vision-model",
            "机器人开发": "robotics",
            "仿真平台": "simulation",
            "数据采集设备": "data-capture",
            "开发环境": "dev-environment",
            "其他": "other",
        }.get(name, f"group-{len(group_ids)+1}")
        result = bind.execute(
            sa.text(
                "INSERT INTO skill_groups(workspace_id,code,display_name,normalized_name,sort_order,status) VALUES(1,:code,:name,:normalized,:sort,'active')"
            ),
            {"code": code, "name": name, "normalized": normalized, "sort": group_order},
        )
        group_ids[name] = int(result.lastrowid)
        group_order += 10
    if "其他" not in group_ids:
        result = bind.execute(
            sa.text(
                "INSERT INTO skill_groups(workspace_id,code,display_name,normalized_name,sort_order,status) VALUES(1,'other','其他','其他',999,'active')"
            )
        )
        group_ids["其他"] = int(result.lastrowid)

    for row in bind.execute(sa.text("SELECT * FROM legacy_personal_fact_details")).mappings():
        if (
            row["fact_id"] not in fact_by_id
            or fact_by_id[row["fact_id"]]["category"] != "basics"
        ):
            continue
        profile = bind.execute(
            sa.text(
                "SELECT desired_city,availability,personal_summary FROM requirement_profiles WHERE status='active' ORDER BY id LIMIT 1"
            )
        ).mappings().first() or {}
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_basics_details(
                    fact_id,workspace_id,name,phone,email,city,desired_city,birth_date,
                    age_text,hometown,identity_status,graduation_date,availability,bio
                ) VALUES(:fact_id,:workspace,:name,:phone,:email,:city,:desired_city,:birth_date,
                         :age_text,:hometown,:identity_status,:graduation_date,:availability,:bio)
                """
            ),
            {
                "fact_id": row["fact_id"],
                "workspace": fact_by_id[row["fact_id"]]["workspace_id"],
                "name": row["name"],
                "phone": row["phone"],
                "email": row["email"],
                "city": row["city"],
                "desired_city": row["desired_city"] or profile.get("desired_city", ""),
                "birth_date": row["birth_date"],
                "age_text": row["age"],
                "hometown": row["hometown"],
                "identity_status": row["status"],
                "graduation_date": row["graduation"],
                "availability": row["availability"] or profile.get("availability", ""),
                "bio": row["bio"] or profile.get("personal_summary", ""),
            },
        )
    for row in bind.execute(sa.text("SELECT * FROM legacy_education_fact_details")).mappings():
        if (
            row["fact_id"] not in fact_by_id
            or fact_by_id[row["fact_id"]]["category"] != "education"
        ):
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_education_details(
                    fact_id,workspace_id,school,major,degree,start_date,end_date,
                    period_text,gpa,ranking,achievement,courses
                ) VALUES(:fact_id,:workspace,:school,:major,:degree,:start_date,:end_date,
                         :period_text,:gpa,:ranking,:achievement,:courses)
                """
            ),
            {**dict(row), "workspace": fact_by_id[row["fact_id"]]["workspace_id"], "period_text": row["period"]},
        )
    for row in bind.execute(sa.text("SELECT * FROM legacy_experience_fact_details")).mappings():
        if (
            row["fact_id"] not in fact_by_id
            or fact_by_id[row["fact_id"]]["category"] != "experience"
        ):
            continue
        kind = row["kind"] if row["kind"] in {"project","work_internship","competition","research","campus_volunteer","other"} else "project"
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_experience_details(
                    fact_id,workspace_id,experience_kind,period_text,organization,role,team_size,
                    context_summary,work_summary,tools_summary,result_summary,challenge,solution,public_note
                ) VALUES(:fact_id,:workspace,:kind,:period_text,:organization,:role,:team_size,
                         :context,:work,:tools,:outcome,:challenge,:solution,:public_note)
                """
            ),
            {
                "fact_id": row["fact_id"],
                "workspace": fact_by_id[row["fact_id"]]["workspace_id"],
                "kind": kind,
                "period_text": row["period"],
                "organization": row["organization"],
                "role": row["role"],
                "team_size": row["team_size"],
                "context": row["context"],
                "work": row["work"],
                "tools": row["tools"],
                "outcome": row["outcome"],
                "challenge": row["challenge"],
                "solution": row["solution"],
                "public_note": row["public_note"],
            },
        )
    for row in raw_skill_rows:
        bind.execute(
            sa.text(
                "INSERT INTO fact_skill_details(fact_id,workspace_id,skill_group_id,proficiency,usage_context) VALUES(:fact_id,:workspace,:group_id,:proficiency,:context)"
            ),
            {
                "fact_id": row["fact_id"],
                "workspace": fact_by_id[row["fact_id"]]["workspace_id"],
                "group_id": group_ids[str(row["skill_category"] or "其他").strip() or "其他"],
                "proficiency": row["proficiency"],
                "context": row["context"],
            },
        )
    for row in bind.execute(sa.text("SELECT * FROM legacy_achievement_fact_details")).mappings():
        if (
            row["fact_id"] not in fact_by_id
            or fact_by_id[row["fact_id"]]["category"] != "achievement"
        ):
            continue
        kind = row["achievement_kind"] if row["achievement_kind"] in {"honor","certificate","publication_patent","project_result","other"} else "honor"
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_achievement_details(
                    fact_id,workspace_id,achievement_kind,period_text,issuer,result_text,note,experience_fact_id
                ) VALUES(:fact_id,:workspace,:kind,:period_text,:issuer,:result,:note,:parent)
                """
            ),
            {
                "fact_id": row["fact_id"],
                "workspace": fact_by_id[row["fact_id"]]["workspace_id"],
                "kind": kind,
                "period_text": row["period"],
                "issuer": row["issuer"],
                "result": row["result"],
                "note": row["note"],
                "parent": row["experience_fact_id"],
            },
        )

    for row in bind.execute(sa.text("SELECT * FROM legacy_tags")).mappings():
        bind.execute(
            sa.text(
                "INSERT INTO tags(id,workspace_id,display_name,normalized_name,status,merged_into_tag_id,created_at) VALUES(:id,:workspace_id,:display_name,:normalized_name,:status,:merged_into_tag_id,:created_at)"
            ),
            dict(row),
        )
    for row in bind.execute(sa.text("SELECT * FROM legacy_fact_tags")).mappings():
        if row["fact_id"] in fact_by_id:
            bind.execute(
                sa.text("INSERT INTO fact_tags(workspace_id,fact_id,tag_id) VALUES(:workspace_id,:fact_id,:tag_id)"),
                dict(row),
            )
    for row in bind.execute(sa.text("SELECT * FROM legacy_experience_skill_links")).mappings():
        if row["experience_fact_id"] in fact_by_id and row["skill_fact_id"] in fact_by_id:
            bind.execute(
                sa.text("INSERT INTO experience_skill_links(workspace_id,experience_fact_id,skill_fact_id) VALUES(:workspace_id,:experience_fact_id,:skill_fact_id)"),
                dict(row),
            )
    for row in bind.execute(sa.text("SELECT * FROM legacy_evidence ORDER BY id")).mappings():
        bind.execute(
            sa.text(
                """
                INSERT INTO evidence(
                    id,workspace_id,kind,title,url,storage_key,filename,mime_type,
                    size_bytes,checksum,note,status,created_at,updated_at
                ) VALUES(:id,:workspace_id,:kind,:title,:url,:storage_key,:filename,:mime_type,
                         :size_bytes,:checksum,:note,:status,:created_at,:updated_at)
                """
            ),
            dict(row),
        )
    for row in bind.execute(sa.text("SELECT * FROM legacy_fact_evidence")).mappings():
        if row["fact_id"] in fact_by_id:
            bind.execute(
                sa.text("INSERT INTO fact_evidence(id,workspace_id,fact_id,evidence_id) VALUES(:id,:workspace,:fact_id,:evidence_id)"),
                {**dict(row), "workspace": fact_by_id[row["fact_id"]]["workspace_id"]},
            )
    owners = dict(bind.execute(sa.text("SELECT id,owner_id FROM workspaces")).all())
    for row in bind.execute(sa.text("SELECT * FROM legacy_fact_audits ORDER BY id")).mappings():
        fact = fact_by_id.get(row["fact_id"])
        if not fact:
            continue
        action = row["action"] if row["action"] in {"created","updated","archived","restored","recycled","purged","reclassified","merged","split","tag_changed","evidence_changed"} else "updated"
        bind.execute(
            sa.text(
                """
                INSERT INTO fact_audit_events(
                    id,workspace_id,fact_id,actor_user_id,action,schema_version_id,
                    changed_fields,before_values,after_values,related_fact_ids,reason,created_at
                ) VALUES(:id,:workspace,:fact_id,:actor,:action,:schema,'["snapshot"]',:before,:after,'[]',:reason,:created_at)
                """
            ),
            {
                "id": row["id"],
                "workspace": fact["workspace_id"],
                "fact_id": row["fact_id"],
                "actor": owners[fact["workspace_id"]],
                "action": action,
                "schema": CATEGORIES[fact["category"]][2],
                "before": row["before_content"] or "{}",
                "after": row["after_content"] or "{}",
                "reason": row["summary"] or "",
                "created_at": row["created_at"],
            },
        )
    for row in bind.execute(sa.text("SELECT * FROM evidence ORDER BY id")).mappings():
        bind.execute(
            sa.text(
                "INSERT INTO evidence_audit_events(workspace_id,evidence_id,actor_user_id,action,changed_fields,before_values,after_values,reason,created_at) VALUES(:workspace,:evidence,:actor,'created','[]','{}',:after,'迁移建档',:created_at)"
            ),
            {
                "workspace": row["workspace_id"],
                "evidence": row["id"],
                "actor": owners[row["workspace_id"]],
                "after": json.dumps({"title": row["title"], "status": row["status"]}, ensure_ascii=False),
                "created_at": row["created_at"],
            },
        )

    for row in bind.execute(sa.text("SELECT * FROM legacy_resume_fact_uses")).mappings():
        if row["fact_id"] in fact_by_id:
            bind.execute(
                sa.text("INSERT INTO resume_fact_uses(id,workspace_id,resume_id,fact_id,section_code,block_key,display_order,fact_content_hash) VALUES(:id,:workspace_id,:resume_id,:fact_id,:section_code,:block_key,:display_order,:fact_content_hash)"),
                {**dict(row), "section_code": row["section_code"] or "unknown", "block_key": row["block_key"] or "unknown"},
            )
    for row in bind.execute(sa.text("SELECT * FROM legacy_resume_version_fact_snapshots")).mappings():
        if row["fact_id"] in fact_by_id:
            bind.execute(
                sa.text("INSERT INTO resume_version_fact_snapshots(id,workspace_id,resume_version_id,fact_id,section_code,block_key,display_order,fact_content_hash) VALUES(:id,:workspace_id,:resume_version_id,:fact_id,:section_code,:block_key,:display_order,:fact_content_hash)"),
                {**dict(row), "section_code": row["section_code"] or "unknown", "block_key": row["block_key"] or "unknown"},
            )
    for row in bind.execute(sa.text("SELECT * FROM legacy_resume_evidence_uses")).mappings():
        bind.execute(sa.text("INSERT INTO resume_evidence_uses(id,workspace_id,resume_id,evidence_id,section_code,block_key,display_mode,label,display_order) VALUES(:id,:workspace_id,:resume_id,:evidence_id,:section_code,:block_key,:display_mode,:label,:display_order)"), dict(row))
    for row in bind.execute(sa.text("SELECT * FROM legacy_resume_version_evidence_snapshots")).mappings():
        bind.execute(sa.text("INSERT INTO resume_version_evidence_snapshots(id,workspace_id,resume_version_id,evidence_id,section_code,block_key,display_mode,label,display_order) VALUES(:id,:workspace_id,:resume_version_id,:evidence_id,:section_code,:block_key,:display_mode,:label,:display_order)"), dict(row))
    allowed_kinds = {"source_changed","source_recycled","evidence_sync","evidence_conflict","profile_changed","export_warning","other"}
    for row in bind.execute(sa.text("SELECT * FROM legacy_pending_issues ORDER BY id")).mappings():
        if not any(row[name] for name in ("fact_id","evidence_id","profile_id","resume_id")):
            continue
        bind.execute(
            sa.text(
                "INSERT INTO pending_issues(id,workspace_id,kind,status,fact_id,evidence_id,profile_id,resume_id,section_code,block_key,message,created_at,resolved_at) VALUES(:id,:workspace_id,:kind,:status,:fact_id,:evidence_id,:profile_id,:resume_id,:section_code,:block_key,:message,:created_at,:resolved_at)"
            ),
            {**dict(row), "kind": row["kind"] if row["kind"] in allowed_kinds else "other"},
        )

    for table in (
        "legacy_resume_version_fact_snapshots",
        "legacy_resume_version_evidence_snapshots",
        "legacy_resume_fact_uses",
        "legacy_resume_evidence_uses",
        "legacy_pending_issues",
        "legacy_fact_evidence",
        "legacy_fact_tags",
        "legacy_experience_skill_links",
        "legacy_fact_audits",
        "legacy_personal_fact_details",
        "legacy_education_fact_details",
        "legacy_experience_fact_details",
        "legacy_skill_fact_details",
        "legacy_achievement_fact_details",
        "legacy_tags",
        "legacy_evidence",
        "legacy_fact_records",
    ):
        bind.execute(sa.text(f'DROP TABLE IF EXISTS "{table}"'))

    profile_columns = {column["name"] for column in sa.inspect(bind).get_columns("requirement_profiles")}
    removable_profile_columns = [
        column
        for column in ("identity_key","deleted_at","desired_city","availability","personal_summary")
        if column in profile_columns
    ]
    if removable_profile_columns:
        with op.batch_alter_table("requirement_profiles", recreate="always") as batch:
            for column in removable_profile_columns:
                batch.drop_column(column)

    pref_columns = {column["name"] for column in sa.inspect(bind).get_columns("workspace_template_preferences")}
    if "id" in pref_columns:
        bind.execute(sa.text("ALTER TABLE workspace_template_preferences RENAME TO legacy_workspace_template_preferences"))
        bind.execute(
            sa.text(
                """
                CREATE TABLE workspace_template_preferences (
                    workspace_id INTEGER PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
                    default_template_id INTEGER REFERENCES templates(id) ON DELETE RESTRICT,
                    last_selected_template_id INTEGER REFERENCES templates(id) ON DELETE RESTRICT,
                    updated_at TEXT NOT NULL
                ) STRICT
                """
            )
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO workspace_template_preferences(
                    workspace_id,default_template_id,last_selected_template_id,updated_at
                )
                SELECT workspace_id,default_template_id,last_selected_template_id,updated_at
                  FROM legacy_workspace_template_preferences
                 GROUP BY workspace_id
                """
            )
        )
        bind.execute(sa.text("DROP TABLE legacy_workspace_template_preferences"))
    for table in ("template_versions","resume_templates"):
        if table in set(sa.inspect(bind).get_table_names()):
            bind.execute(sa.text(f'DROP TABLE "{table}"'))

    for statement in TRIGGERS:
        bind.execute(sa.text(statement))
    violations = bind.execute(sa.text("PRAGMA foreign_key_check")).fetchall()
    if violations:
        raise RuntimeError(
            "target resource migration left foreign key violations: "
            + repr([tuple(row) for row in violations[:20]])
        )


def display_name_for(code: str) -> str:
    return {
        "basics": "基本信息",
        "education": "教育经历",
        "experience": "经历",
        "skill": "技能",
        "achievement": "成果",
    }[code]


def downgrade() -> None:
    raise RuntimeError(
        "The target resource migration is intentionally irreversible; restore the "
        "pre-0016 database backup recorded by the release process."
    )
