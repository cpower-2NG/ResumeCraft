-- ResumeCraft rendering and delivery target schema.
-- Prerequisites: workspaces(id), resumes(workspace_id,id),
-- resume_versions(workspace_id,id).
-- This file is an executable design contract, not an Alembic migration.
PRAGMA foreign_keys = ON;

-- RD-ENT-001 Template
CREATE TABLE templates (
    id                      INTEGER PRIMARY KEY,
    template_key            TEXT NOT NULL UNIQUE CHECK (length(trim(template_key)) > 0),
    display_name            TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    description             TEXT NOT NULL DEFAULT '',
    renderer_key            TEXT NOT NULL CHECK (length(trim(renderer_key)) > 0),
    supported_sections_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(supported_sections_json)),
    default_sections_json   TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(default_sections_json)),
    status                  TEXT NOT NULL DEFAULT 'available'
                            CHECK (status IN ('available', 'retired')),
    successor_template_id   INTEGER REFERENCES templates(id) ON DELETE RESTRICT,
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (successor_template_id IS NULL OR successor_template_id <> id),
    CHECK (
        (status = 'available' AND successor_template_id IS NULL)
        OR status = 'retired'
    )
) STRICT;

-- RD-ENT-002 WorkspaceTemplatePreference
CREATE TABLE workspace_template_preferences (
    workspace_id                    INTEGER PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    default_template_id             INTEGER REFERENCES templates(id) ON DELETE RESTRICT,
    last_selected_template_id       INTEGER REFERENCES templates(id) ON DELETE RESTRICT,
    updated_at                      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

-- RD-ENT-003 ExportEvent
CREATE TABLE export_events (
    id                  INTEGER PRIMARY KEY,
    workspace_id        INTEGER NOT NULL,
    resume_id           INTEGER NOT NULL,
    resume_version_id   INTEGER NOT NULL,
    template_id         INTEGER NOT NULL REFERENCES templates(id) ON DELETE RESTRICT,
    format              TEXT NOT NULL CHECK (format IN ('html', 'zip')),
    warnings_json       TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(warnings_json)),
    forced              INTEGER NOT NULL DEFAULT 0 CHECK (forced IN (0, 1)),
    content_hash        TEXT NOT NULL CHECK (length(content_hash) = 64),
    output_hash         TEXT NOT NULL CHECK (length(output_hash) = 64),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (workspace_id, resume_id)
        REFERENCES resumes(workspace_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (workspace_id, resume_version_id)
        REFERENCES resume_versions(workspace_id, id) ON DELETE RESTRICT
) STRICT;

-- RD-STS-001 Template lifecycle.
CREATE TRIGGER trg_template_status_transition
BEFORE UPDATE OF status ON templates
WHEN NEW.status <> OLD.status
 AND NOT (OLD.status = 'available' AND NEW.status = 'retired')
BEGIN
    SELECT RAISE(ABORT, 'RD-STS-001: invalid template status transition');
END;

-- RD-INV-001 Templates referenced by Resumes cannot be physically deleted.
CREATE TRIGGER trg_template_no_delete
BEFORE DELETE ON templates
WHEN EXISTS (SELECT 1 FROM resumes WHERE template_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'RD-INV-001: template is referenced by Resume');
END;

-- RD-INV-002 Export events are append-only.
CREATE TRIGGER trg_export_event_no_update
BEFORE UPDATE ON export_events
BEGIN
    SELECT RAISE(ABORT, 'RD-INV-002: export events are append-only');
END;

CREATE TRIGGER trg_export_event_no_delete
BEFORE DELETE ON export_events
BEGIN
    SELECT RAISE(ABORT, 'RD-INV-002: export events are append-only');
END;

-- RD-INV-003 Export version must belong to the same Resume.
CREATE TRIGGER trg_export_version_matches_resume
BEFORE INSERT ON export_events
WHEN NOT EXISTS (
    SELECT 1 FROM resume_versions
    WHERE workspace_id = NEW.workspace_id
      AND resume_id = NEW.resume_id
      AND id = NEW.resume_version_id
)
BEGIN
    SELECT RAISE(ABORT, 'RD-INV-003: export version belongs to another Resume');
END;
