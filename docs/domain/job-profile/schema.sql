-- ResumeCraft job-profile target schema.
-- Prerequisite: workspaces(id) and users(id).
-- This file is an executable design contract, not an Alembic migration.
PRAGMA foreign_keys = ON;

-- JP-ENT-001 RequirementProfile
CREATE TABLE requirement_profiles (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    name                    TEXT NOT NULL CHECK (length(trim(name)) > 0),
    role_direction          TEXT NOT NULL DEFAULT '',
    core_requirements_json  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(core_requirements_json)),
    general_requirements    TEXT NOT NULL DEFAULT '',
    responsibilities        TEXT NOT NULL DEFAULT '',
    resume_strategy         TEXT NOT NULL DEFAULT '',
    raw_jd                  TEXT NOT NULL DEFAULT '',
    source_note             TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    archived_at             TEXT,
    recycled_at             TEXT,
    purged_at               TEXT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (workspace_id, id)
) STRICT;

-- JP-ENT-002 JobOpportunity
CREATE TABLE job_opportunities (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    requirement_profile_id  INTEGER NOT NULL,
    company                 TEXT NOT NULL DEFAULT '',
    title                   TEXT NOT NULL DEFAULT '',
    raw_jd                  TEXT NOT NULL DEFAULT '',
    url                     TEXT NOT NULL DEFAULT '',
    source_note             TEXT NOT NULL DEFAULT '',
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, requirement_profile_id)
        REFERENCES requirement_profiles(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id)
) STRICT;

-- JP-ENT-003 ProfileAuditEvent
CREATE TABLE profile_audit_events (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    profile_id              INTEGER NOT NULL,
    actor_user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action                  TEXT NOT NULL CHECK (action IN (
                                'created', 'updated', 'archived', 'restored',
                                'recycled', 'purged', 'cloned',
                                'opportunity_changed'
                            )),
    changed_fields_json     TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(changed_fields_json)),
    before_values_json      TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(before_values_json)),
    after_values_json       TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(after_values_json)),
    related_profile_ids_json TEXT NOT NULL DEFAULT '[]'
                             CHECK (json_valid(related_profile_ids_json)),
    reason                  TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, profile_id)
        REFERENCES requirement_profiles(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- JP-STS-001 Profile lifecycle.
CREATE TRIGGER trg_profile_status_transition
BEFORE UPDATE OF status ON requirement_profiles
WHEN NEW.status <> OLD.status
 AND NOT (
    (OLD.status = 'active' AND NEW.status IN ('archived', 'recycled'))
    OR (OLD.status = 'archived' AND NEW.status IN ('active', 'recycled'))
    OR (OLD.status = 'recycled' AND NEW.status IN ('active', 'archived', 'purged'))
 )
BEGIN
    SELECT RAISE(ABORT, 'JP-STS-001: invalid profile status transition');
END;

-- JP-STS-002 Opportunity lifecycle.
CREATE TRIGGER trg_opportunity_status_transition
BEFORE UPDATE OF status ON job_opportunities
WHEN NEW.status <> OLD.status
 AND NOT (
    (OLD.status = 'active' AND NEW.status IN ('archived', 'recycled'))
    OR (OLD.status = 'archived' AND NEW.status IN ('active', 'recycled'))
    OR (OLD.status = 'recycled' AND NEW.status IN ('active', 'archived', 'purged'))
 )
BEGIN
    SELECT RAISE(ABORT, 'JP-STS-002: invalid opportunity status transition');
END;

-- JP-INV-001 Audit events are append-only.
CREATE TRIGGER trg_profile_audit_no_update
BEFORE UPDATE ON profile_audit_events
BEGIN
    SELECT RAISE(ABORT, 'JP-INV-001: profile audit is append-only');
END;

CREATE TRIGGER trg_profile_audit_no_delete
BEFORE DELETE ON profile_audit_events
BEGIN
    SELECT RAISE(ABORT, 'JP-INV-001: profile audit is append-only');
END;

-- JP-INV-002 A purged profile contains no current source rows.
CREATE TRIGGER trg_profile_purge_tombstone
AFTER UPDATE OF status ON requirement_profiles
WHEN NEW.status = 'purged'
BEGIN
    UPDATE job_opportunities
       SET status = 'purged', company = '', title = '', raw_jd = '',
           url = '', source_note = ''
     WHERE workspace_id = NEW.workspace_id
       AND requirement_profile_id = NEW.id;
    UPDATE requirement_profiles
       SET name = '[purged]', role_direction = '', core_requirements_json = '[]',
           general_requirements = '', responsibilities = '', resume_strategy = '',
           raw_jd = '', source_note = ''
     WHERE workspace_id = NEW.workspace_id AND id = NEW.id;
END;
