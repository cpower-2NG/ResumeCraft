-- Resource library target schema.
-- Canonical structural source: docs/resource-library/schema.sql
-- Human-readable semantics: docs/resource-library/design.md
-- Target engine: SQLite. This file is a design contract, not an Alembic migration.
--
-- Stable IDs in this file:
--   RL-ENT-*  entity/table
--   RL-FLD-*  field definition
--
-- Every connection applying this contract must execute:
PRAGMA foreign_keys = ON;

-- RL-ENT-001 User boundary
CREATE TABLE users (
    id              INTEGER PRIMARY KEY,
    display_name    TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- RL-ENT-002 Workspace boundary
-- RL-REL-001 Workspace owns its facts and dictionaries.
CREATE TABLE workspaces (
    id              INTEGER PRIMARY KEY,
    owner_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name            TEXT NOT NULL CHECK (length(trim(name)) > 0),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- RL-ENT-003 Fact category registry
-- RL-REL-002 A category owns one or more immutable schema versions.
CREATE TABLE fact_categories (
    code            TEXT PRIMARY KEY
                    CHECK (code IN ('basics', 'education', 'experience', 'skill', 'achievement')),
    display_name    TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    sort_order      INTEGER NOT NULL CHECK (sort_order >= 0),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'deprecated'))
) STRICT;

-- RL-ENT-004 Fact schema version
CREATE TABLE fact_schema_versions (
    id              INTEGER PRIMARY KEY,
    category_code   TEXT NOT NULL REFERENCES fact_categories(code) ON DELETE RESTRICT,
    version_number  INTEGER NOT NULL CHECK (version_number > 0),
    status          TEXT NOT NULL DEFAULT 'published'
                    CHECK (status IN ('draft', 'published', 'retired')),
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (category_code, version_number),
    UNIQUE (category_code, id)
) STRICT;

-- RL-INV-016 A category has at most one currently published schema version.
CREATE UNIQUE INDEX uq_fact_schema_current_published
    ON fact_schema_versions(category_code)
    WHERE status = 'published';

-- RL-ENT-005 Controlled field definition
-- RL-REL-003 A schema version owns its controlled field definitions.
CREATE TABLE fact_field_definitions (
    id                  INTEGER PRIMARY KEY,
    category_code       TEXT NOT NULL,
    schema_version_id   INTEGER NOT NULL,
    field_key           TEXT NOT NULL CHECK (length(trim(field_key)) > 0),
    label               TEXT NOT NULL CHECK (length(trim(label)) > 0),
    value_type          TEXT NOT NULL
                        CHECK (value_type IN ('text', 'long_text', 'number', 'date', 'year_month', 'url', 'enum', 'boolean', 'integer')),
    requirement_level   TEXT NOT NULL DEFAULT 'optional'
                        CHECK (requirement_level IN ('optional', 'recommended', 'required_for_output')),
    is_extension        INTEGER NOT NULL DEFAULT 0 CHECK (is_extension IN (0, 1)),
    storage_table       TEXT NOT NULL,
    storage_column      TEXT NOT NULL,
    sort_order          INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    FOREIGN KEY (category_code, schema_version_id)
        REFERENCES fact_schema_versions(category_code, id) ON DELETE RESTRICT,
    UNIQUE (schema_version_id, field_key),
    UNIQUE (id, category_code, schema_version_id)
) STRICT;

-- RL-ENT-006 Fact identity and lifecycle
-- RL-REL-004 A fact pins exactly one category and schema version.
CREATE TABLE fact_records (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    category_code       TEXT NOT NULL REFERENCES fact_categories(code) ON DELETE RESTRICT,
    schema_version_id   INTEGER NOT NULL,
    title               TEXT NOT NULL CHECK (length(trim(title)) > 0),
    business_key        TEXT CHECK (business_key IS NULL OR length(trim(business_key)) > 0),
    source_note         TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    archived_at         TEXT,
    recycled_at         TEXT,
    purged_at           TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (category_code, schema_version_id)
        REFERENCES fact_schema_versions(category_code, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, id, category_code),
    UNIQUE (workspace_id, id, category_code, schema_version_id)
) STRICT;

CREATE UNIQUE INDEX uq_fact_business_key_live
    ON fact_records(workspace_id, category_code, business_key)
    WHERE business_key IS NOT NULL
      AND status IN ('active', 'archived', 'recycled');

-- A purged basics tombstone no longer blocks creating a new primary record.
CREATE UNIQUE INDEX uq_one_live_basics_per_workspace
    ON fact_records(workspace_id)
    WHERE category_code = 'basics'
      AND status IN ('active', 'archived', 'recycled');

-- RL-ENT-007 Basics detail
-- RL-REL-005 A fact has one typed detail row in its category-specific table.
CREATE TABLE fact_basics_details (
    fact_id             INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    category_code       TEXT NOT NULL DEFAULT 'basics' CHECK (category_code = 'basics'),
    -- RL-FLD-001
    name                TEXT NOT NULL DEFAULT '',
    -- RL-FLD-002
    phone               TEXT NOT NULL DEFAULT '',
    -- RL-FLD-003
    email               TEXT NOT NULL DEFAULT '',
    -- RL-FLD-004
    city                TEXT NOT NULL DEFAULT '',
    -- RL-FLD-005
    desired_city        TEXT NOT NULL DEFAULT '',
    -- RL-FLD-006
    birth_date          TEXT NOT NULL DEFAULT '',
    -- RL-FLD-007
    age_text            TEXT NOT NULL DEFAULT '',
    -- RL-FLD-008
    hometown            TEXT NOT NULL DEFAULT '',
    -- RL-FLD-009
    identity_status     TEXT NOT NULL DEFAULT '',
    -- RL-FLD-010
    graduation_date     TEXT NOT NULL DEFAULT '',
    -- RL-FLD-011
    availability        TEXT NOT NULL DEFAULT '',
    -- RL-FLD-012
    bio                 TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, fact_id, category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
) STRICT;

-- RL-ENT-008 Education detail
CREATE TABLE fact_education_details (
    fact_id             INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    category_code       TEXT NOT NULL DEFAULT 'education' CHECK (category_code = 'education'),
    -- RL-FLD-013
    school              TEXT NOT NULL DEFAULT '',
    -- RL-FLD-014
    major               TEXT NOT NULL DEFAULT '',
    -- RL-FLD-015
    degree              TEXT NOT NULL DEFAULT '',
    -- RL-FLD-016
    start_date          TEXT NOT NULL DEFAULT '',
    -- RL-FLD-017
    end_date            TEXT NOT NULL DEFAULT '',
    -- RL-FLD-018
    period_text         TEXT NOT NULL DEFAULT '',
    -- RL-FLD-019
    gpa                 TEXT NOT NULL DEFAULT '',
    -- RL-FLD-020
    ranking             TEXT NOT NULL DEFAULT '',
    -- RL-FLD-021
    achievement         TEXT NOT NULL DEFAULT '',
    -- RL-FLD-022
    courses             TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, fact_id, category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
) STRICT;

-- RL-ENT-009 Experience detail
CREATE TABLE fact_experience_details (
    fact_id             INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    category_code       TEXT NOT NULL DEFAULT 'experience' CHECK (category_code = 'experience'),
    -- RL-FLD-023
    experience_kind     TEXT NOT NULL DEFAULT 'project'
                        CHECK (experience_kind IN (
                            'project', 'work_internship', 'competition',
                            'research', 'campus_volunteer', 'other'
                        )),
    -- RL-FLD-024
    period_text         TEXT NOT NULL DEFAULT '',
    -- RL-FLD-025
    start_date          TEXT NOT NULL DEFAULT '',
    -- RL-FLD-026
    end_date            TEXT NOT NULL DEFAULT '',
    -- RL-FLD-027
    organization        TEXT NOT NULL DEFAULT '',
    -- RL-FLD-028
    role                TEXT NOT NULL DEFAULT '',
    -- RL-FLD-029
    team_size           TEXT NOT NULL DEFAULT '',
    -- RL-FLD-030
    context_summary     TEXT NOT NULL DEFAULT '',
    -- RL-FLD-031
    work_summary        TEXT NOT NULL DEFAULT '',
    -- RL-FLD-032
    tools_summary       TEXT NOT NULL DEFAULT '',
    -- RL-FLD-033
    result_summary      TEXT NOT NULL DEFAULT '',
    -- RL-FLD-034
    challenge           TEXT NOT NULL DEFAULT '',
    -- RL-FLD-035
    solution            TEXT NOT NULL DEFAULT '',
    -- RL-FLD-036
    public_note         TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, fact_id, category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE
) STRICT;

-- RL-ENT-010 Skill group dictionary
-- RL-REL-016 A skill group belongs to one workspace and is reused by skills.
CREATE TABLE skill_groups (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL CHECK (length(trim(code)) > 0),
    display_name    TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    normalized_name TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
    sort_order      INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived')),
    UNIQUE (workspace_id, code),
    UNIQUE (workspace_id, normalized_name),
    UNIQUE (workspace_id, id)
) STRICT;

-- RL-ENT-011 Skill detail
CREATE TABLE fact_skill_details (
    fact_id             INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    category_code       TEXT NOT NULL DEFAULT 'skill' CHECK (category_code = 'skill'),
    -- RL-FLD-037
    skill_group_id      INTEGER NOT NULL,
    -- RL-FLD-038
    proficiency         TEXT NOT NULL DEFAULT '',
    -- RL-FLD-039
    usage_context       TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, fact_id, category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, skill_group_id)
        REFERENCES skill_groups(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- RL-ENT-012 Achievement detail
-- RL-REL-009 An achievement may belong to exactly one parent experience or none.
CREATE TABLE fact_achievement_details (
    fact_id                 INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    category_code           TEXT NOT NULL DEFAULT 'achievement' CHECK (category_code = 'achievement'),
    -- RL-FLD-040
    achievement_kind        TEXT NOT NULL DEFAULT 'honor'
                            CHECK (achievement_kind IN (
                                'honor', 'certificate', 'publication_patent',
                                'project_result', 'other'
                            )),
    -- RL-FLD-041
    period_text             TEXT NOT NULL DEFAULT '',
    -- RL-FLD-042
    occurred_on             TEXT NOT NULL DEFAULT '',
    -- RL-FLD-043
    issuer                  TEXT NOT NULL DEFAULT '',
    -- RL-FLD-044
    result_text             TEXT NOT NULL DEFAULT '',
    -- RL-FLD-045
    note                    TEXT NOT NULL DEFAULT '',
    -- RL-FLD-046
    experience_fact_id      INTEGER,
    parent_category_code    TEXT NOT NULL DEFAULT 'experience'
                            CHECK (parent_category_code = 'experience'),
    FOREIGN KEY (workspace_id, fact_id, category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, experience_fact_id, parent_category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE RESTRICT,
    CHECK (experience_fact_id IS NULL OR experience_fact_id <> fact_id)
) STRICT;

-- RL-ENT-014 Controlled extension value
CREATE TABLE fact_extension_values (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    fact_id                 INTEGER NOT NULL,
    category_code           TEXT NOT NULL,
    schema_version_id       INTEGER NOT NULL,
    field_definition_id     INTEGER NOT NULL,
    text_value              TEXT,
    numeric_value           REAL,
    boolean_value           INTEGER CHECK (boolean_value IS NULL OR boolean_value IN (0, 1)),
    json_value              TEXT CHECK (json_value IS NULL OR json_valid(json_value)),
    FOREIGN KEY (workspace_id, fact_id, category_code, schema_version_id)
        REFERENCES fact_records(workspace_id, id, category_code, schema_version_id)
        ON DELETE CASCADE,
    FOREIGN KEY (field_definition_id, category_code, schema_version_id)
        REFERENCES fact_field_definitions(id, category_code, schema_version_id)
        ON DELETE RESTRICT,
    UNIQUE (fact_id, field_definition_id),
    CHECK (
        (text_value IS NOT NULL)
        + (numeric_value IS NOT NULL)
        + (boolean_value IS NOT NULL)
        + (json_value IS NOT NULL)
        = 1
    )
) STRICT;

-- RL-ENT-015 Flat controlled tag
-- RL-REL-006 Facts and tags have a many-to-many association through fact_tags.
CREATE TABLE tags (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    display_name        TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    normalized_name     TEXT NOT NULL CHECK (length(trim(normalized_name)) > 0),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'archived', 'merged')),
    merged_into_tag_id  INTEGER,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, merged_into_tag_id)
        REFERENCES tags(workspace_id, id) ON DELETE RESTRICT,
    CHECK (merged_into_tag_id IS NULL OR merged_into_tag_id <> id),
    CHECK (
        (status = 'merged' AND merged_into_tag_id IS NOT NULL)
        OR (status <> 'merged' AND merged_into_tag_id IS NULL)
    ),
    UNIQUE (workspace_id, normalized_name),
    UNIQUE (workspace_id, id)
) STRICT;

-- RL-ENT-016 Tag alias
CREATE TABLE tag_aliases (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL,
    tag_id          INTEGER NOT NULL,
    alias           TEXT NOT NULL CHECK (length(trim(alias)) > 0),
    normalized_alias TEXT NOT NULL CHECK (length(trim(normalized_alias)) > 0),
    FOREIGN KEY (workspace_id, tag_id)
        REFERENCES tags(workspace_id, id) ON DELETE CASCADE,
    UNIQUE (workspace_id, normalized_alias)
) STRICT;

-- RL-ENT-017 Fact-tag association
CREATE TABLE fact_tags (
    workspace_id    INTEGER NOT NULL,
    fact_id         INTEGER NOT NULL,
    tag_id          INTEGER NOT NULL,
    PRIMARY KEY (workspace_id, fact_id, tag_id),
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, tag_id)
        REFERENCES tags(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- RL-ENT-018 Reusable immutable evidence payload
-- RL-REL-007 Facts and evidence have a many-to-many association through fact_evidence.
CREATE TABLE evidence (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    kind            TEXT NOT NULL CHECK (kind IN ('file', 'link', 'note')),
    title           TEXT NOT NULL CHECK (length(trim(title)) > 0),
    url             TEXT NOT NULL DEFAULT '',
    storage_key     TEXT NOT NULL DEFAULT '',
    filename        TEXT NOT NULL DEFAULT '',
    mime_type       TEXT NOT NULL DEFAULT '',
    size_bytes      INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    checksum        TEXT NOT NULL DEFAULT '',
    note            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'invalid', 'archived')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (
        (kind = 'link'
            AND length(trim(url)) > 0
            AND storage_key = '' AND filename = '' AND mime_type = ''
            AND size_bytes = 0 AND checksum = '')
        OR
        (kind = 'file'
            AND url = '' AND length(trim(storage_key)) > 0
            AND length(trim(filename)) > 0 AND length(trim(mime_type)) > 0
            AND size_bytes > 0 AND size_bytes <= 10485760
            AND length(checksum) = 64)
        OR
        (kind = 'note'
            AND url = '' AND storage_key = '' AND filename = ''
            AND mime_type = '' AND size_bytes = 0 AND checksum = ''
            AND length(trim(note)) > 0)
    ),
    UNIQUE (workspace_id, id)
) STRICT;

CREATE UNIQUE INDEX uq_evidence_file_checksum
    ON evidence(workspace_id, checksum)
    WHERE kind = 'file';

-- RL-ENT-019 Fact-evidence association
CREATE TABLE fact_evidence (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL,
    fact_id         INTEGER NOT NULL,
    evidence_id     INTEGER NOT NULL,
    relation_note   TEXT NOT NULL DEFAULT '',
    sort_order      INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    UNIQUE (workspace_id, fact_id, evidence_id),
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- RL-ENT-029 Profile photo history
-- RL-REL-017 A personal archive has zero or more profile photos over time.
-- RL-REL-018 A profile photo references one immutable image file.
-- RL-REL-019 A personal archive has at most one active profile photo.
CREATE TABLE profile_photos (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    basics_fact_id          INTEGER NOT NULL,
    basics_category_code    TEXT NOT NULL DEFAULT 'basics'
                            CHECK (basics_category_code = 'basics'),
    evidence_id             INTEGER NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'archived')),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    archived_at             TEXT,
    FOREIGN KEY (workspace_id, basics_fact_id, basics_category_code)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, evidence_id)
) STRICT;

CREATE UNIQUE INDEX uq_active_profile_photo
    ON profile_photos(workspace_id, basics_fact_id)
    WHERE status = 'active';

CREATE TRIGGER trg_profile_photo_evidence_file_insert
BEFORE INSERT ON profile_photos
WHEN NOT EXISTS (
    SELECT 1 FROM evidence
     WHERE workspace_id = NEW.workspace_id
       AND id = NEW.evidence_id
       AND kind = 'file'
       AND mime_type LIKE 'image/%'
)
BEGIN
    SELECT RAISE(ABORT, 'profile photo must reference an image file');
END;

CREATE TRIGGER trg_profile_photo_evidence_file_update
BEFORE UPDATE OF workspace_id, evidence_id ON profile_photos
WHEN NOT EXISTS (
    SELECT 1 FROM evidence
     WHERE workspace_id = NEW.workspace_id
       AND id = NEW.evidence_id
       AND kind = 'file'
       AND mime_type LIKE 'image/%'
)
BEGIN
    SELECT RAISE(ABORT, 'profile photo must reference an image file');
END;

-- RL-ENT-020 Fact append-only audit event
-- RL-REL-010 A fact has zero or more append-only audit events.
CREATE TABLE fact_audit_events (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    fact_id             INTEGER NOT NULL,
    actor_user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action              TEXT NOT NULL CHECK (action IN (
                            'created', 'updated', 'archived', 'restored',
                            'recycled', 'purged', 'reclassified', 'merged',
                            'split', 'tag_changed', 'evidence_changed'
                        )),
    schema_version_id   INTEGER,
    changed_fields      TEXT NOT NULL CHECK (json_valid(changed_fields)),
    before_values       TEXT NOT NULL CHECK (json_valid(before_values)),
    after_values        TEXT NOT NULL CHECK (json_valid(after_values)),
    related_fact_ids    TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(related_fact_ids)),
    reason              TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (schema_version_id)
        REFERENCES fact_schema_versions(id) ON DELETE RESTRICT
) STRICT;

-- RL-ENT-021 Evidence metadata/state audit event
-- RL-REL-011 Evidence has zero or more append-only metadata/state audit events.
CREATE TABLE evidence_audit_events (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL,
    evidence_id     INTEGER NOT NULL,
    actor_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action          TEXT NOT NULL CHECK (action IN (
                        'created', 'updated_metadata', 'marked_invalid',
                        'marked_active', 'archived'
                    )),
    changed_fields  TEXT NOT NULL CHECK (json_valid(changed_fields)),
    before_values   TEXT NOT NULL CHECK (json_valid(before_values)),
    after_values    TEXT NOT NULL CHECK (json_valid(after_values)),
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- RL-ENT-022 Experience-skill dedicated association
-- RL-REL-008 Experience and skill have a dedicated many-to-many association.
CREATE TABLE experience_skill_links (
    workspace_id        INTEGER NOT NULL,
    experience_fact_id  INTEGER NOT NULL,
    skill_fact_id       INTEGER NOT NULL,
    experience_category TEXT NOT NULL DEFAULT 'experience'
                        CHECK (experience_category = 'experience'),
    skill_category      TEXT NOT NULL DEFAULT 'skill'
                        CHECK (skill_category = 'skill'),
    PRIMARY KEY (workspace_id, experience_fact_id, skill_fact_id),
    FOREIGN KEY (workspace_id, experience_fact_id, experience_category)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, skill_fact_id, skill_category)
        REFERENCES fact_records(workspace_id, id, category_code) ON DELETE CASCADE,
    CHECK (experience_fact_id <> skill_fact_id)
) STRICT;

-- The following tables are minimal cross-module anchors. The resume domain
-- specification owns their complete definitions; they are included here so
-- this contract can be executed and its foreign keys tested independently.
-- RL-ENT-023 Resume boundary
CREATE TABLE resumes (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL,
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    UNIQUE (workspace_id, id)
) STRICT;

-- RL-ENT-024 Resume version boundary
CREATE TABLE resume_versions (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_id           INTEGER NOT NULL,
    version_number      INTEGER NOT NULL CHECK (version_number > 0),
    content_hash        TEXT NOT NULL,
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, resume_id, version_number)
) STRICT;

-- RL-ENT-025 Current resume fact use
-- RL-REL-012 A Resume currently uses zero or more facts.
CREATE TABLE resume_fact_uses (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_id           INTEGER NOT NULL,
    fact_id             INTEGER NOT NULL,
    section_code        TEXT NOT NULL CHECK (length(trim(section_code)) > 0),
    block_key           TEXT NOT NULL CHECK (length(trim(block_key)) > 0),
    display_order       INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    fact_content_hash   TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, resume_id, fact_id, section_code, block_key)
) STRICT;

-- RL-ENT-026 Immutable resume-version fact snapshot
-- RL-REL-013 A formal resume version snapshots zero or more fact uses.
CREATE TABLE resume_version_fact_snapshots (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_version_id   INTEGER NOT NULL,
    fact_id             INTEGER NOT NULL,
    section_code        TEXT NOT NULL CHECK (length(trim(section_code)) > 0),
    block_key           TEXT NOT NULL CHECK (length(trim(block_key)) > 0),
    display_order       INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    fact_content_hash   TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (workspace_id, resume_version_id)
        REFERENCES resume_versions(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, resume_version_id, fact_id, section_code, block_key)
) STRICT;

-- RL-ENT-027 Current resume evidence use
-- RL-REL-014 A Resume currently uses zero or more evidence rows.
CREATE TABLE resume_evidence_uses (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_id           INTEGER NOT NULL,
    evidence_id         INTEGER NOT NULL,
    section_code        TEXT NOT NULL CHECK (length(trim(section_code)) > 0),
    block_key           TEXT NOT NULL CHECK (length(trim(block_key)) > 0),
    display_mode        TEXT NOT NULL
                        CHECK (display_mode IN ('hidden', 'inline_link', 'attachment', 'reference')),
    label               TEXT NOT NULL DEFAULT '',
    display_order       INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, resume_id, evidence_id, section_code, block_key)
) STRICT;

-- RL-ENT-028 Immutable resume-version evidence snapshot
-- RL-REL-015 A formal resume version snapshots zero or more evidence uses.
CREATE TABLE resume_version_evidence_snapshots (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_version_id   INTEGER NOT NULL,
    evidence_id         INTEGER NOT NULL,
    section_code        TEXT NOT NULL CHECK (length(trim(section_code)) > 0),
    block_key           TEXT NOT NULL CHECK (length(trim(block_key)) > 0),
    display_mode        TEXT NOT NULL
                        CHECK (display_mode IN ('hidden', 'inline_link', 'attachment', 'reference')),
    label               TEXT NOT NULL DEFAULT '',
    display_order       INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    FOREIGN KEY (workspace_id, resume_version_id)
        REFERENCES resume_versions(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, resume_version_id, evidence_id, section_code, block_key)
) STRICT;

-- Seeded categories and version 1 schemas.
INSERT INTO fact_categories(code, display_name, sort_order, status) VALUES
    ('basics',      '基本信息',       10, 'active'),
    ('education',   '教育经历',       20, 'active'),
    ('experience',  '经历',           30, 'active'),
    ('skill',       '技能',           40, 'active'),
    ('achievement', '成果',           50, 'active');

INSERT INTO fact_schema_versions(id, category_code, version_number, status, note) VALUES
    (1, 'basics',      1, 'published', '基本信息主档 v1'),
    (2, 'education',   1, 'published', '教育经历 v1'),
    (3, 'experience',  1, 'published', '经历 v1'),
    (4, 'skill',       1, 'published', '技能 v1'),
    (5, 'achievement', 1, 'published', '成果 v1');

INSERT INTO fact_field_definitions(
    category_code, schema_version_id, field_key, label, value_type,
    requirement_level, is_extension, storage_table, storage_column, sort_order
) VALUES
    ('basics', 1, 'name', '姓名', 'text', 'required_for_output', 0, 'fact_basics_details', 'name', 10),
    ('basics', 1, 'phone', '电话', 'text', 'recommended', 0, 'fact_basics_details', 'phone', 20),
    ('basics', 1, 'email', '邮箱', 'text', 'recommended', 0, 'fact_basics_details', 'email', 30),
    ('basics', 1, 'city', '所在地', 'text', 'optional', 0, 'fact_basics_details', 'city', 40),
    ('basics', 1, 'desired_city', '目标城市', 'text', 'optional', 0, 'fact_basics_details', 'desired_city', 50),
    ('basics', 1, 'birth_date', '出生日期', 'date', 'optional', 0, 'fact_basics_details', 'birth_date', 60),
    ('basics', 1, 'age_text', '年龄', 'text', 'optional', 0, 'fact_basics_details', 'age_text', 70),
    ('basics', 1, 'hometown', '籍贯', 'text', 'optional', 0, 'fact_basics_details', 'hometown', 80),
    ('basics', 1, 'identity_status', '身份状态', 'text', 'optional', 0, 'fact_basics_details', 'identity_status', 90),
    ('basics', 1, 'graduation_date', '毕业时间', 'year_month', 'optional', 0, 'fact_basics_details', 'graduation_date', 100),
    ('basics', 1, 'availability', '到岗安排', 'long_text', 'optional', 0, 'fact_basics_details', 'availability', 110),
    ('basics', 1, 'bio', '个人简介', 'long_text', 'optional', 0, 'fact_basics_details', 'bio', 120),
    ('education', 2, 'school', '学校', 'text', 'required_for_output', 0, 'fact_education_details', 'school', 10),
    ('education', 2, 'major', '专业', 'text', 'optional', 0, 'fact_education_details', 'major', 20),
    ('education', 2, 'degree', '学历', 'text', 'recommended', 0, 'fact_education_details', 'degree', 30),
    ('education', 2, 'start_date', '入学时间', 'year_month', 'optional', 0, 'fact_education_details', 'start_date', 40),
    ('education', 2, 'end_date', '毕业时间', 'year_month', 'optional', 0, 'fact_education_details', 'end_date', 50),
    ('education', 2, 'period_text', '展示时间段', 'text', 'optional', 0, 'fact_education_details', 'period_text', 60),
    ('education', 2, 'gpa', 'GPA', 'text', 'optional', 0, 'fact_education_details', 'gpa', 70),
    ('education', 2, 'ranking', '排名', 'text', 'optional', 0, 'fact_education_details', 'ranking', 80),
    ('education', 2, 'achievement', '成绩与成果', 'long_text', 'optional', 0, 'fact_education_details', 'achievement', 90),
    ('education', 2, 'courses', '相关课程', 'long_text', 'optional', 0, 'fact_education_details', 'courses', 100),
    ('experience', 3, 'experience_kind', '经历类型', 'enum', 'required_for_output', 0, 'fact_experience_details', 'experience_kind', 10),
    ('experience', 3, 'period_text', '展示时间段', 'text', 'recommended', 0, 'fact_experience_details', 'period_text', 20),
    ('experience', 3, 'start_date', '开始时间', 'year_month', 'optional', 0, 'fact_experience_details', 'start_date', 30),
    ('experience', 3, 'end_date', '结束时间', 'year_month', 'optional', 0, 'fact_experience_details', 'end_date', 40),
    ('experience', 3, 'organization', '组织/公司', 'text', 'optional', 0, 'fact_experience_details', 'organization', 50),
    ('experience', 3, 'role', '角色', 'text', 'optional', 0, 'fact_experience_details', 'role', 60),
    ('experience', 3, 'team_size', '团队规模', 'text', 'optional', 0, 'fact_experience_details', 'team_size', 70),
    ('experience', 3, 'context_summary', '背景', 'long_text', 'optional', 0, 'fact_experience_details', 'context_summary', 80),
    ('experience', 3, 'work_summary', '具体工作', 'long_text', 'recommended', 0, 'fact_experience_details', 'work_summary', 90),
    ('experience', 3, 'tools_summary', '工具与技术', 'long_text', 'optional', 0, 'fact_experience_details', 'tools_summary', 100),
    ('experience', 3, 'result_summary', '结果摘要', 'long_text', 'optional', 0, 'fact_experience_details', 'result_summary', 110),
    ('experience', 3, 'challenge', '挑战', 'long_text', 'optional', 0, 'fact_experience_details', 'challenge', 120),
    ('experience', 3, 'solution', '解决方案', 'long_text', 'optional', 0, 'fact_experience_details', 'solution', 130),
    ('experience', 3, 'public_note', '公开说明', 'long_text', 'optional', 0, 'fact_experience_details', 'public_note', 140),
    ('skill', 4, 'skill_group_id', '技能分组', 'integer', 'recommended', 0, 'fact_skill_details', 'skill_group_id', 10),
    ('skill', 4, 'proficiency', '熟练程度', 'text', 'optional', 0, 'fact_skill_details', 'proficiency', 20),
    ('skill', 4, 'usage_context', '使用场景', 'long_text', 'optional', 0, 'fact_skill_details', 'usage_context', 30),
    ('achievement', 5, 'achievement_kind', '成果类型', 'enum', 'required_for_output', 0, 'fact_achievement_details', 'achievement_kind', 10),
    ('achievement', 5, 'period_text', '展示时间段', 'text', 'optional', 0, 'fact_achievement_details', 'period_text', 20),
    ('achievement', 5, 'occurred_on', '取得日期', 'date', 'optional', 0, 'fact_achievement_details', 'occurred_on', 30),
    ('achievement', 5, 'issuer', '颁发方', 'text', 'optional', 0, 'fact_achievement_details', 'issuer', 40),
    ('achievement', 5, 'result_text', '成果内容', 'text', 'required_for_output', 0, 'fact_achievement_details', 'result_text', 50),
    ('achievement', 5, 'note', '说明', 'long_text', 'optional', 0, 'fact_achievement_details', 'note', 60),
    ('achievement', 5, 'experience_fact_id', '主经历', 'integer', 'optional', 0, 'fact_achievement_details', 'experience_fact_id', 70);

-- RL-INV-001 Every non-purged fact has a positive, non-blank business key.
CREATE TRIGGER trg_fact_business_key_required
BEFORE INSERT ON fact_records
WHEN NEW.status <> 'purged'
 AND (NEW.business_key IS NULL OR length(trim(NEW.business_key)) = 0)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-001: live fact requires business_key');
END;

-- RL-INV-002 Changing category requires the explicit reclassification command.
CREATE TRIGGER trg_fact_category_immutable
BEFORE UPDATE OF category_code ON fact_records
WHEN NEW.category_code <> OLD.category_code
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-002: fact category is immutable; use RL-CMD-005');
END;

-- RL-STS-001 Fact transition graph.
CREATE TRIGGER trg_fact_status_transition
BEFORE UPDATE OF status ON fact_records
WHEN NEW.status <> OLD.status
 AND NOT (
    (OLD.status = 'active' AND NEW.status IN ('archived', 'recycled'))
    OR (OLD.status = 'archived' AND NEW.status IN ('active', 'recycled'))
    OR (OLD.status = 'recycled' AND NEW.status IN ('active', 'archived', 'purged'))
 )
BEGIN
    SELECT RAISE(ABORT, 'RL-STS-001: invalid fact status transition');
END;

-- RL-INV-003 A referenced fact cannot be purged from current or historical use.
CREATE TRIGGER trg_fact_purge_reference_guard
BEFORE UPDATE OF status ON fact_records
WHEN NEW.status = 'purged'
 AND (
    EXISTS (
        SELECT 1 FROM resume_fact_uses
        WHERE workspace_id = OLD.workspace_id AND fact_id = OLD.id
    )
    OR EXISTS (
        SELECT 1 FROM resume_version_fact_snapshots
        WHERE workspace_id = OLD.workspace_id AND fact_id = OLD.id
    )
    OR EXISTS (
        SELECT 1 FROM fact_achievement_details
        WHERE workspace_id = OLD.workspace_id
          AND experience_fact_id = OLD.id
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-003: referenced fact or parent experience cannot be purged');
END;

-- RL-CMD-004 Purge creates a tombstone and removes current personal/detail data.
CREATE TRIGGER trg_fact_purge_tombstone
AFTER UPDATE OF status ON fact_records
WHEN NEW.status = 'purged'
BEGIN
    DELETE FROM fact_basics_details WHERE fact_id = NEW.id;
    DELETE FROM fact_education_details WHERE fact_id = NEW.id;
    DELETE FROM fact_experience_details WHERE fact_id = NEW.id;
    DELETE FROM fact_skill_details WHERE fact_id = NEW.id;
    DELETE FROM fact_achievement_details WHERE fact_id = NEW.id;
    DELETE FROM fact_extension_values WHERE fact_id = NEW.id;
    DELETE FROM fact_tags WHERE fact_id = NEW.id;
    DELETE FROM fact_evidence WHERE fact_id = NEW.id;
    DELETE FROM experience_skill_links
        WHERE experience_fact_id = NEW.id OR skill_fact_id = NEW.id;
    UPDATE fact_records
       SET title = '[purged]', business_key = NULL, source_note = NULL
     WHERE id = NEW.id;
END;

-- RL-INV-004 Extension values must use an extension definition from the same fact schema.
CREATE TRIGGER trg_extension_value_definition
BEFORE INSERT ON fact_extension_values
WHEN NOT EXISTS (
    SELECT 1
      FROM fact_field_definitions
     WHERE id = NEW.field_definition_id
       AND category_code = NEW.category_code
       AND schema_version_id = NEW.schema_version_id
       AND is_extension = 1
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-004: extension field does not match fact schema');
END;

CREATE TRIGGER trg_extension_value_type
BEFORE INSERT ON fact_extension_values
WHEN EXISTS (
    SELECT 1
      FROM fact_field_definitions
     WHERE id = NEW.field_definition_id
       AND (
            (value_type IN ('text', 'long_text', 'date', 'year_month', 'url', 'enum')
                AND NEW.text_value IS NULL)
         OR (value_type = 'number' AND NEW.numeric_value IS NULL)
         OR (value_type = 'boolean' AND NEW.boolean_value IS NULL)
         OR (value_type = 'integer' AND NEW.json_value IS NULL)
       )
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-005: extension value type mismatch');
END;

CREATE TRIGGER trg_extension_value_definition_update
BEFORE UPDATE ON fact_extension_values
WHEN NOT EXISTS (
    SELECT 1
      FROM fact_field_definitions
     WHERE id = NEW.field_definition_id
       AND category_code = NEW.category_code
       AND schema_version_id = NEW.schema_version_id
       AND is_extension = 1
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-018: extension field does not match fact schema');
END;

CREATE TRIGGER trg_extension_value_type_update
BEFORE UPDATE ON fact_extension_values
WHEN EXISTS (
    SELECT 1
      FROM fact_field_definitions
     WHERE id = NEW.field_definition_id
       AND (
            (value_type IN ('text', 'long_text', 'date', 'year_month', 'url', 'enum')
                AND NEW.text_value IS NULL)
         OR (value_type = 'number' AND NEW.numeric_value IS NULL)
         OR (value_type = 'boolean' AND NEW.boolean_value IS NULL)
         OR (value_type = 'integer' AND NEW.json_value IS NULL)
       )
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-018: extension value type mismatch');
END;

-- RL-INV-017 Published and retired schema field definitions are immutable.
CREATE TRIGGER trg_field_definition_insert_draft_only
BEFORE INSERT ON fact_field_definitions
WHEN NOT EXISTS (
    SELECT 1 FROM fact_schema_versions
    WHERE id = NEW.schema_version_id AND status = 'draft'
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-017: fields can only be added to a draft schema');
END;

CREATE TRIGGER trg_published_field_definition_no_update
BEFORE UPDATE ON fact_field_definitions
WHEN EXISTS (
    SELECT 1 FROM fact_schema_versions
    WHERE id = OLD.schema_version_id AND status IN ('published', 'retired')
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable');
END;

-- RL-STS-004 Schema versions advance from draft to published to retired.
CREATE TRIGGER trg_schema_version_status_transition
BEFORE UPDATE OF status ON fact_schema_versions
WHEN NEW.status <> OLD.status
 AND NOT (
    (OLD.status = 'draft' AND NEW.status = 'published')
    OR (OLD.status = 'published' AND NEW.status = 'retired')
 )
BEGIN
    SELECT RAISE(ABORT, 'RL-STS-004: invalid schema status transition');
END;

CREATE TRIGGER trg_published_field_definition_no_delete
BEFORE DELETE ON fact_field_definitions
WHEN EXISTS (
    SELECT 1 FROM fact_schema_versions
    WHERE id = OLD.schema_version_id AND status IN ('published', 'retired')
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-017: published field definitions are immutable');
END;

-- RL-INV-006 Evidence payload fields are immutable; replace with a new evidence row.
CREATE TRIGGER trg_evidence_payload_immutable
BEFORE UPDATE OF workspace_id, kind, url, storage_key, filename, mime_type, size_bytes, checksum, note
ON evidence
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-006: evidence payload is immutable');
END;

-- RL-INV-007 Evidence rows are retained for history.
CREATE TRIGGER trg_evidence_no_delete
BEFORE DELETE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-007: evidence cannot be physically deleted');
END;

-- RL-INV-008 Audit events are append-only.
CREATE TRIGGER trg_fact_audit_no_update
BEFORE UPDATE ON fact_audit_events
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-008: fact audit is append-only');
END;

CREATE TRIGGER trg_fact_audit_no_delete
BEFORE DELETE ON fact_audit_events
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-008: fact audit is append-only');
END;

CREATE TRIGGER trg_evidence_audit_no_update
BEFORE UPDATE ON evidence_audit_events
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-008: evidence audit is append-only');
END;

CREATE TRIGGER trg_evidence_audit_no_delete
BEFORE DELETE ON evidence_audit_events
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-008: evidence audit is append-only');
END;

-- RL-INV-009 Tag names and aliases share one normalized namespace.
CREATE TRIGGER trg_tag_name_not_alias
BEFORE INSERT ON tags
WHEN EXISTS (
    SELECT 1 FROM tag_aliases
    WHERE workspace_id = NEW.workspace_id
      AND normalized_alias = NEW.normalized_name
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias');
END;

CREATE TRIGGER trg_tag_alias_not_name
BEFORE INSERT ON tag_aliases
WHEN EXISTS (
    SELECT 1 FROM tags
    WHERE workspace_id = NEW.workspace_id
      AND normalized_name = NEW.normalized_alias
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name');
END;

CREATE TRIGGER trg_tag_name_not_alias_update
BEFORE UPDATE OF workspace_id, normalized_name ON tags
WHEN EXISTS (
    SELECT 1 FROM tag_aliases
    WHERE workspace_id = NEW.workspace_id
      AND normalized_alias = NEW.normalized_name
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-009: tag name collides with alias');
END;

CREATE TRIGGER trg_tag_alias_not_name_update
BEFORE UPDATE OF workspace_id, normalized_alias ON tag_aliases
WHEN EXISTS (
    SELECT 1 FROM tags
    WHERE workspace_id = NEW.workspace_id
      AND normalized_name = NEW.normalized_alias
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-009: tag alias collides with name');
END;

-- RL-INV-019 Only active tags may receive new fact associations.
CREATE TRIGGER trg_fact_tag_requires_active_tag
BEFORE INSERT ON fact_tags
WHEN NOT EXISTS (
    SELECT 1 FROM tags
    WHERE workspace_id = NEW.workspace_id
      AND id = NEW.tag_id
      AND status = 'active'
)
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-019: fact tags must reference an active tag');
END;

-- RL-INV-010 Formal resume version reference snapshots are immutable.
CREATE TRIGGER trg_version_fact_snapshot_no_update
BEFORE UPDATE ON resume_version_fact_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-010: version fact snapshot is immutable');
END;

CREATE TRIGGER trg_version_fact_snapshot_no_delete
BEFORE DELETE ON resume_version_fact_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-010: version fact snapshot is immutable');
END;

CREATE TRIGGER trg_version_evidence_snapshot_no_update
BEFORE UPDATE ON resume_version_evidence_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-010: version evidence snapshot is immutable');
END;

CREATE TRIGGER trg_version_evidence_snapshot_no_delete
BEFORE DELETE ON resume_version_evidence_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RL-INV-010: version evidence snapshot is immutable');
END;
