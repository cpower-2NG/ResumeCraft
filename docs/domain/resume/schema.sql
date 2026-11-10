-- ResumeCraft resume-chain target schema.
-- Prerequisites: workspaces(id), users(id), requirement_profiles(workspace_id,id),
-- fact_records(workspace_id,id), evidence(workspace_id,id), templates(id).
-- This file is an executable design contract, not an Alembic migration.
PRAGMA foreign_keys = ON;

-- RS-ENT-001 LinkedResume
CREATE TABLE linked_resumes (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    requirement_profile_id  INTEGER NOT NULL,
    template_id             INTEGER NOT NULL REFERENCES templates(id) ON DELETE RESTRICT,
    selection_json          TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(selection_json)),
    status                  TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'converted', 'abandoned')),
    converted_resume_id     INTEGER,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, requirement_profile_id)
        REFERENCES requirement_profiles(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, converted_resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, converted_resume_id)
) STRICT;

-- RS-ENT-002 Resume
CREATE TABLE resumes (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    requirement_profile_id  INTEGER NOT NULL,
    origin_linked_resume_id INTEGER,
    template_id             INTEGER NOT NULL REFERENCES templates(id) ON DELETE RESTRICT,
    display_name            TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    current_version_id      INTEGER,
    status                  TEXT NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'archived', 'recycled', 'purged')),
    archived_at             TEXT,
    recycled_at             TEXT,
    purged_at               TEXT,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, requirement_profile_id)
        REFERENCES requirement_profiles(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, origin_linked_resume_id)
        REFERENCES linked_resumes(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, origin_linked_resume_id)
) STRICT;

CREATE UNIQUE INDEX uq_active_resume_per_profile
    ON resumes(workspace_id, requirement_profile_id)
    WHERE status = 'active';

-- RS-ENT-003 ResumeVersion
CREATE TABLE resume_versions (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    resume_id               INTEGER NOT NULL,
    version_number          INTEGER NOT NULL CHECK (version_number > 0),
    content_json            TEXT NOT NULL CHECK (json_valid(content_json)),
    profile_snapshot_json   TEXT NOT NULL CHECK (json_valid(profile_snapshot_json)),
    profile_snapshot_hash   TEXT NOT NULL CHECK (length(profile_snapshot_hash) = 64),
    source_manifest_json    TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(source_manifest_json)),
    evidence_manifest_json  TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(evidence_manifest_json)),
    content_hash            TEXT NOT NULL CHECK (length(content_hash) = 64),
    reason                  TEXT NOT NULL CHECK (reason IN (
                                'format_conversion', 'user_save',
                                'rollback', 'evidence_sync'
                            )),
    change_summary          TEXT NOT NULL DEFAULT '',
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, resume_id, version_number),
    UNIQUE (workspace_id, resume_id, id)
) STRICT;

-- RS-ENT-004 ResumeWorkingCopy
CREATE TABLE resume_working_copies (
    id                      INTEGER PRIMARY KEY,
    workspace_id            INTEGER NOT NULL,
    resume_id               INTEGER NOT NULL,
    base_version_id         INTEGER,
    template_id             INTEGER NOT NULL REFERENCES templates(id) ON DELETE RESTRICT,
    content_json            TEXT NOT NULL CHECK (json_valid(content_json)),
    content_state           TEXT NOT NULL DEFAULT 'clean'
                            CHECK (content_state IN ('clean', 'dirty')),
    evidence_sync_state     TEXT NOT NULL DEFAULT 'clean'
                            CHECK (evidence_sync_state IN ('clean', 'pending', 'conflict')),
    baseline_state          TEXT NOT NULL DEFAULT 'current'
                            CHECK (baseline_state IN ('current', 'stale')),
    pending_reason          TEXT,
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, resume_id, base_version_id)
        REFERENCES resume_versions(workspace_id, resume_id, id) ON DELETE RESTRICT,
    UNIQUE (workspace_id, resume_id)
) STRICT;

-- RS-ENT-005 Current fact use
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

-- RS-ENT-006 Version fact snapshot
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

-- RS-ENT-007 Current evidence use
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

-- RS-ENT-008 Version evidence snapshot
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

-- RS-ENT-009 PendingIssue
CREATE TABLE pending_issues (
    id              INTEGER PRIMARY KEY,
    workspace_id    INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    kind            TEXT NOT NULL CHECK (kind IN (
                        'source_changed', 'source_recycled', 'evidence_sync',
                        'evidence_conflict', 'profile_changed',
                        'export_warning', 'other'
                    )),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved', 'dismissed')),
    fact_id         INTEGER,
    evidence_id     INTEGER,
    profile_id      INTEGER,
    resume_id       INTEGER,
    section_code    TEXT NOT NULL DEFAULT '',
    block_key       TEXT NOT NULL DEFAULT '',
    message         TEXT NOT NULL CHECK (length(trim(message)) > 0),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at     TEXT,
    FOREIGN KEY (workspace_id, fact_id)
        REFERENCES fact_records(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, evidence_id)
        REFERENCES evidence(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, profile_id)
        REFERENCES requirement_profiles(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE CASCADE,
    CHECK (
        (fact_id IS NOT NULL) + (evidence_id IS NOT NULL)
        + (profile_id IS NOT NULL) + (resume_id IS NOT NULL) >= 1
    )
) STRICT;

-- RS-STS-001 Resume lifecycle.
CREATE TRIGGER trg_resume_status_transition
BEFORE UPDATE OF status ON resumes
WHEN NEW.status <> OLD.status
 AND NOT (
    (OLD.status = 'active' AND NEW.status IN ('archived', 'recycled'))
    OR (OLD.status = 'archived' AND NEW.status IN ('active', 'recycled'))
    OR (OLD.status = 'recycled' AND NEW.status IN ('active', 'archived', 'purged'))
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-STS-001: invalid resume status transition');
END;

-- RS-INV-001 Current version must belong to the same Resume.
CREATE TRIGGER trg_resume_current_version_insert
BEFORE INSERT ON resumes
WHEN NEW.current_version_id IS NOT NULL
 AND NOT EXISTS (
    SELECT 1 FROM resume_versions
    WHERE workspace_id = NEW.workspace_id
      AND resume_id = NEW.id
      AND id = NEW.current_version_id
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-001: current version belongs to another resume');
END;

CREATE TRIGGER trg_resume_current_version
BEFORE UPDATE OF current_version_id ON resumes
WHEN NEW.current_version_id IS NOT NULL
 AND NOT EXISTS (
    SELECT 1 FROM resume_versions
    WHERE workspace_id = NEW.workspace_id
      AND resume_id = NEW.id
      AND id = NEW.current_version_id
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-001: current version belongs to another resume');
END;

-- RS-INV-002 LinkedResume conversion is one-way and one-to-one.
CREATE TRIGGER trg_linked_conversion_state_insert
BEFORE INSERT ON linked_resumes
WHEN (
    NEW.status = 'converted' AND NEW.converted_resume_id IS NULL
 )
 OR (
    NEW.status <> 'converted' AND NEW.converted_resume_id IS NOT NULL
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-002: converted draft requires exactly one Resume');
END;

CREATE TRIGGER trg_linked_conversion_state
BEFORE UPDATE OF status, converted_resume_id ON linked_resumes
WHEN (
    NEW.status = 'converted' AND NEW.converted_resume_id IS NULL
 )
 OR (
    NEW.status <> 'converted' AND NEW.converted_resume_id IS NOT NULL
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-002: converted draft requires exactly one Resume');
END;

-- RS-INV-003 One draft can produce at most one formal Resume.
CREATE TRIGGER trg_resume_origin_once
BEFORE INSERT ON resumes
WHEN NEW.origin_linked_resume_id IS NOT NULL
 AND EXISTS (
    SELECT 1 FROM resumes
    WHERE workspace_id = NEW.workspace_id
      AND origin_linked_resume_id = NEW.origin_linked_resume_id
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-003: draft already produced a Resume');
END;

-- RS-INV-004 Resume versions are append-only.
CREATE TRIGGER trg_resume_version_no_update
BEFORE UPDATE ON resume_versions
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-004: resume versions are immutable');
END;

CREATE TRIGGER trg_resume_version_no_delete
BEFORE DELETE ON resume_versions
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-004: resume versions are immutable');
END;

-- RS-INV-005 Version fact/evidence snapshots are immutable.
CREATE TRIGGER trg_resume_version_fact_no_update
BEFORE UPDATE ON resume_version_fact_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-005: version fact snapshot is immutable');
END;

CREATE TRIGGER trg_resume_version_fact_no_delete
BEFORE DELETE ON resume_version_fact_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-005: version fact snapshot is immutable');
END;

CREATE TRIGGER trg_resume_version_evidence_no_update
BEFORE UPDATE ON resume_version_evidence_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-005: version evidence snapshot is immutable');
END;

CREATE TRIGGER trg_resume_version_evidence_no_delete
BEFORE DELETE ON resume_version_evidence_snapshots
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-005: version evidence snapshot is immutable');
END;

-- RS-INV-006 A profile with a stored formal Resume cannot be purged.
CREATE TRIGGER trg_profile_resume_purge_guard
BEFORE UPDATE OF status ON requirement_profiles
WHEN NEW.status = 'purged'
 AND EXISTS (
    SELECT 1 FROM resumes
    WHERE workspace_id = NEW.workspace_id
      AND requirement_profile_id = NEW.id
      AND status <> 'purged'
 )
BEGIN
    SELECT RAISE(ABORT, 'RS-INV-006: profile still owns formal Resume history');
END;
