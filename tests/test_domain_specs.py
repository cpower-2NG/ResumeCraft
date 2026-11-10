from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check_domain_specs.py"
SPEC = importlib.util.spec_from_file_location("domain_spec_checker", CHECKER_PATH)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.fixture
def domain_db():
    connection = checker.load_target_schema()
    checker.seed_workspace(connection)
    yield connection
    connection.close()


def ready_resume(connection, profile_id=None, template_id=None):
    profile_id = profile_id or checker.create_profile(connection)
    template_id = template_id or checker.create_template(connection)
    resume_id = checker.create_resume(connection, profile_id, template_id)
    version_id = checker.create_version(connection, resume_id)
    connection.execute(
        "UPDATE resumes SET current_version_id = ? WHERE id = ?",
        (version_id, resume_id),
    )
    copy_id = checker.create_working_copy(
        connection, resume_id, version_id, template_id
    )
    return profile_id, template_id, resume_id, version_id, copy_id


def test_domain_document_and_schema_contracts():
    assert checker.validate() == []


def test_profile_clone_copies_fields_but_not_opportunities(domain_db):
    original = checker.create_profile(domain_db)
    checker.create_opportunity(domain_db, original)
    clone = checker.create_profile(domain_db, name="机器人工程师（简历副本）")
    assert domain_db.execute(
        "SELECT count(*) FROM job_opportunities WHERE requirement_profile_id = ?",
        (original,),
    ).fetchone()[0] == 1
    assert domain_db.execute(
        "SELECT count(*) FROM job_opportunities WHERE requirement_profile_id = ?",
        (clone,),
    ).fetchone()[0] == 0
    domain_db.execute(
        """
        INSERT INTO profile_audit_events(
            workspace_id, profile_id, actor_user_id, action,
            changed_fields_json, related_profile_ids_json
        ) VALUES (1, ?, 1, 'cloned', '[]', ?)
        """,
        (original, f"[{clone}]"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        domain_db.execute(
            "UPDATE profile_audit_events SET reason = 'changed' WHERE profile_id = ?",
            (original,),
        )


def test_one_active_resume_per_profile_and_restore_conflict(domain_db):
    profile_id = checker.create_profile(domain_db)
    template_id = checker.create_template(domain_db)
    first = checker.create_resume(domain_db, profile_id, template_id)
    with pytest.raises(sqlite3.IntegrityError):
        checker.create_resume(domain_db, profile_id, template_id)

    domain_db.execute("UPDATE resumes SET status = 'recycled' WHERE id = ?", (first,))
    second = checker.create_resume(domain_db, profile_id, template_id)
    with pytest.raises(sqlite3.IntegrityError):
        domain_db.execute("UPDATE resumes SET status = 'active' WHERE id = ?", (first,))
    domain_db.execute("UPDATE resumes SET status = 'archived' WHERE id = ?", (second,))
    domain_db.execute("UPDATE resumes SET status = 'active' WHERE id = ?", (first,))


def test_linked_resume_converts_once_and_keeps_origin(domain_db):
    profile_id = checker.create_profile(domain_db)
    template_id = checker.create_template(domain_db)
    draft_id = checker.create_draft(domain_db, profile_id, template_id)
    resume_id = checker.create_resume(
        domain_db, profile_id, template_id, origin_draft_id=draft_id
    )
    domain_db.execute(
        """
        UPDATE linked_resumes
           SET status = 'converted', converted_resume_id = ?
         WHERE id = ?
        """,
        (resume_id, draft_id),
    )
    with pytest.raises(sqlite3.IntegrityError):
        checker.create_resume(
            domain_db,
            profile_id,
            template_id,
            origin_draft_id=draft_id,
            status="archived",
        )


def test_profile_with_resume_history_cannot_be_purged(domain_db):
    profile_id, template_id, resume_id, _, _ = ready_resume(domain_db)
    domain_db.execute(
        "UPDATE resumes SET status = 'recycled' WHERE id = ?", (resume_id,)
    )
    domain_db.execute(
        "UPDATE requirement_profiles SET status = 'recycled' WHERE id = ?",
        (profile_id,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="formal Resume history"):
        domain_db.execute(
            "UPDATE requirement_profiles SET status = 'purged' WHERE id = ?",
            (profile_id,),
        )


def test_working_copy_supports_orthogonal_states(domain_db):
    _, _, _, _, copy_id = ready_resume(domain_db)
    domain_db.execute(
        """
        UPDATE resume_working_copies
           SET content_state = 'dirty',
               evidence_sync_state = 'pending',
               baseline_state = 'stale'
         WHERE id = ?
        """,
        (copy_id,),
    )
    assert domain_db.execute(
        """
        SELECT content_state, evidence_sync_state, baseline_state
          FROM resume_working_copies WHERE id = ?
        """,
        (copy_id,),
    ).fetchone() == ("dirty", "pending", "stale")
    with pytest.raises(sqlite3.IntegrityError):
        domain_db.execute(
            "UPDATE resume_working_copies SET content_state = 'unknown' WHERE id = ?",
            (copy_id,),
        )


def test_template_switch_does_not_create_version(domain_db):
    _, template_id, resume_id, version_id, copy_id = ready_resume(domain_db)
    replacement = checker.create_template(domain_db, "modern")
    before = domain_db.execute(
        "SELECT count(*), content_hash FROM resume_versions WHERE resume_id = ?",
        (resume_id,),
    ).fetchone()
    domain_db.execute(
        "UPDATE resumes SET template_id = ? WHERE id = ?",
        (replacement, resume_id),
    )
    domain_db.execute(
        "UPDATE resume_working_copies SET template_id = ? WHERE id = ?",
        (replacement, copy_id),
    )
    after = domain_db.execute(
        "SELECT count(*), content_hash FROM resume_versions WHERE resume_id = ?",
        (resume_id,),
    ).fetchone()
    assert after == before
    assert domain_db.execute(
        "SELECT template_id FROM resumes WHERE id = ?", (resume_id,)
    ).fetchone()[0] == replacement
    with pytest.raises(sqlite3.IntegrityError, match="versions are immutable"):
        domain_db.execute(
            "UPDATE resume_versions SET change_summary = 'changed' WHERE id = ?",
            (version_id,),
        )


def test_same_version_can_have_multiple_export_events(domain_db):
    _, template_id, resume_id, version_id, _ = ready_resume(domain_db)
    for suffix in ("b", "c"):
        domain_db.execute(
            """
            INSERT INTO export_events(
                workspace_id, resume_id, resume_version_id, template_id,
                format, content_hash, output_hash
            ) VALUES (1, ?, ?, ?, 'html', ?, ?)
            """,
            (resume_id, version_id, template_id, checker.HASH, suffix * 64),
        )
    assert domain_db.execute(
        "SELECT count(*) FROM export_events WHERE resume_version_id = ?",
        (version_id,),
    ).fetchone()[0] == 2
    other_profile = checker.create_profile(domain_db, name="另一个画像")
    other_resume = checker.create_resume(domain_db, other_profile, template_id)
    with pytest.raises(sqlite3.IntegrityError, match="another Resume"):
        domain_db.execute(
            """
            INSERT INTO export_events(
                workspace_id, resume_id, resume_version_id, template_id,
                format, content_hash, output_hash
            ) VALUES (1, ?, ?, ?, 'html', ?, ?)
            """,
            (other_resume, version_id, template_id, checker.HASH, checker.HASH),
        )


def test_pending_issue_requires_one_explicit_source(domain_db):
    with pytest.raises(sqlite3.IntegrityError):
        domain_db.execute(
            "INSERT INTO pending_issues(workspace_id, kind, message) "
            "VALUES (1, 'other', 'missing source')"
        )
    profile_id = checker.create_profile(domain_db)
    domain_db.execute(
        """
        INSERT INTO pending_issues(workspace_id, kind, profile_id, message)
        VALUES (1, 'profile_changed', ?, '画像已变化')
        """,
        (profile_id,),
    )
    checker.seed_workspace(domain_db, 2)
    other_profile = checker.create_profile(
        domain_db, workspace_id=2, name="另一个工作区画像"
    )
    with pytest.raises(sqlite3.IntegrityError):
        domain_db.execute(
            """
            INSERT INTO pending_issues(workspace_id, kind, profile_id, message)
            VALUES (1, 'profile_changed', ?, '跨工作区')
            """,
            (other_profile,),
        )
