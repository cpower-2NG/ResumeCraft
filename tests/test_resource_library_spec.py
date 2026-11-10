from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check_resource_library_spec.py"
SPEC = importlib.util.spec_from_file_location("resource_library_checker", CHECKER_PATH)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

SCHEMA_BY_CATEGORY = {
    "basics": 1,
    "education": 2,
    "experience": 3,
    "skill": 4,
    "achievement": 5,
}


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = checker.load_schema()
    connection.execute("INSERT INTO users(id, display_name) VALUES (1, 'tester')")
    connection.execute("INSERT INTO workspaces(id, owner_id, name) VALUES (1, 1, 'main')")
    yield connection
    connection.close()


def add_fact(
    db: sqlite3.Connection,
    category: str,
    business_key: str,
    *,
    workspace_id: int = 1,
    title: str = "fact",
    schema_version_id: int | None = None,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO fact_records(
            workspace_id, category_code, schema_version_id, title, business_key
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            category,
            schema_version_id or SCHEMA_BY_CATEGORY[category],
            title,
            business_key,
        ),
    )
    return int(cursor.lastrowid)


def add_basics(db: sqlite3.Connection, fact_id: int, name: str = "Person") -> None:
    db.execute(
        """
        INSERT INTO fact_basics_details(fact_id, workspace_id, name)
        VALUES (?, 1, ?)
        """,
        (fact_id, name),
    )


def add_education(db: sqlite3.Connection, fact_id: int) -> None:
    db.execute(
        """
        INSERT INTO fact_education_details(fact_id, workspace_id, school)
        VALUES (?, 1, 'School')
        """,
        (fact_id,),
    )


def add_experience(db: sqlite3.Connection, fact_id: int) -> None:
    db.execute(
        """
        INSERT INTO fact_experience_details(
            fact_id, workspace_id, experience_kind, work_summary
        ) VALUES (?, 1, 'project', 'work')
        """,
        (fact_id,),
    )


def test_schema_and_stable_id_contract():
    assert checker.validate() == []
    connection = checker.load_schema()
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM fact_field_definitions"
        ).fetchone()[0] == 46
        assert connection.execute(
            "SELECT count(*) FROM fact_schema_versions"
        ).fetchone()[0] == 5
        field_id = connection.execute(
            "SELECT id FROM fact_field_definitions LIMIT 1"
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="field definitions are immutable"):
            connection.execute(
                "UPDATE fact_field_definitions SET label = 'changed' WHERE id = ?",
                (field_id,),
            )
    finally:
        connection.close()


def test_basic_info_is_singleton_until_tombstone(db):
    first = add_fact(db, "basics", "primary")
    add_basics(db, first)
    with pytest.raises(sqlite3.IntegrityError):
        add_fact(db, "basics", "secondary")

    with pytest.raises(sqlite3.IntegrityError, match="invalid fact status transition"):
        db.execute("UPDATE fact_records SET status = 'purged' WHERE id = ?", (first,))
    db.execute("UPDATE fact_records SET status = 'recycled' WHERE id = ?", (first,))
    db.execute("UPDATE fact_records SET status = 'purged' WHERE id = ?", (first,))
    tombstone = db.execute(
        "SELECT title, business_key, status FROM fact_records WHERE id = ?", (first,)
    ).fetchone()
    assert tombstone == ("[purged]", None, "purged")
    assert db.execute(
        "SELECT count(*) FROM fact_basics_details WHERE fact_id = ?", (first,)
    ).fetchone()[0] == 0
    add_basics(db, add_fact(db, "basics", "primary"))


def test_category_immutable_detail_type_and_business_key_are_enforced(db):
    education = add_fact(db, "education", "school|bachelor")
    add_education(db, education)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO fact_basics_details(fact_id, workspace_id) VALUES (?, 1)",
            (education,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE fact_records SET category_code = 'experience' WHERE id = ?",
            (education,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        add_fact(db, "education", "school|bachelor")


def test_achievement_parent_must_be_experience(db):
    education = add_fact(db, "education", "education")
    add_education(db, education)
    achievement = add_fact(db, "achievement", "award")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO fact_achievement_details(
                fact_id, workspace_id, achievement_kind, result_text, experience_fact_id
            ) VALUES (?, 1, 'honor', 'first prize', ?)
            """,
            (achievement, education),
        )
    experience = add_fact(db, "experience", "competition")
    add_experience(db, experience)
    db.execute(
        """
        INSERT INTO fact_achievement_details(
            fact_id, workspace_id, achievement_kind, result_text, experience_fact_id
        ) VALUES (?, 1, 'honor', 'first prize', ?)
        """,
        (achievement, experience),
    )
    db.execute("UPDATE fact_records SET status = 'recycled' WHERE id = ?", (experience,))
    with pytest.raises(sqlite3.IntegrityError, match="parent experience"):
        db.execute("UPDATE fact_records SET status = 'purged' WHERE id = ?", (experience,))


def test_cross_workspace_fact_evidence_link_is_rejected(db):
    db.execute("INSERT INTO users(id, display_name) VALUES (2, 'other')")
    db.execute("INSERT INTO workspaces(id, owner_id, name) VALUES (2, 2, 'other')")
    fact_id = add_fact(db, "experience", "project")
    add_experience(db, fact_id)
    evidence_id = db.execute(
        """
        INSERT INTO evidence(workspace_id, kind, title, note)
        VALUES (2, 'note', 'proof', 'body')
        """
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO fact_evidence(workspace_id, fact_id, evidence_id)
            VALUES (1, ?, ?)
            """,
            (fact_id, evidence_id),
        )


def test_evidence_payload_and_audits_are_append_only(db):
    evidence_id = db.execute(
        """
        INSERT INTO evidence(workspace_id, kind, title, note)
        VALUES (1, 'note', 'proof', 'body')
        """
    ).lastrowid
    db.execute("UPDATE evidence SET title = 'renamed proof' WHERE id = ?", (evidence_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE evidence SET note = 'changed' WHERE id = ?", (evidence_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))

    fact_id = add_fact(db, "experience", "audit")
    add_experience(db, fact_id)
    audit_id = db.execute(
        """
        INSERT INTO fact_audit_events(
            workspace_id, fact_id, actor_user_id, action, changed_fields,
            before_values, after_values
        ) VALUES (1, ?, 1, 'updated', '["title"]', '{}', '{"title":"fact"}')
        """,
        (fact_id,),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE fact_audit_events SET reason = 'changed' WHERE id = ?", (audit_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM fact_audit_events WHERE id = ?", (audit_id,))


def test_profile_photo_requires_image_and_allows_one_active(db):
    basics = add_fact(db, "basics", "primary")
    add_basics(db, basics)
    image_id = db.execute(
        """
        INSERT INTO evidence(
            workspace_id, kind, title, storage_key, filename,
            mime_type, size_bytes, checksum
        ) VALUES (1, 'file', 'photo', 'photo.png', 'photo.png',
                  'image/png', 10, ?)
        """,
        ("a" * 64,),
    ).lastrowid
    note_id = db.execute(
        """
        INSERT INTO evidence(workspace_id, kind, title, note)
        VALUES (1, 'note', 'note', 'body')
        """
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="image file"):
        db.execute(
            """
            INSERT INTO profile_photos(
                workspace_id, basics_fact_id, evidence_id
            ) VALUES (1, ?, ?)
            """,
            (basics, note_id),
        )
    first = db.execute(
        """
        INSERT INTO profile_photos(workspace_id, basics_fact_id, evidence_id)
        VALUES (1, ?, ?)
        """,
        (basics, image_id),
    ).lastrowid
    second_image = db.execute(
        """
        INSERT INTO evidence(
            workspace_id, kind, title, storage_key, filename,
            mime_type, size_bytes, checksum
        ) VALUES (1, 'file', 'photo 2', 'photo2.jpg', 'photo2.jpg',
                  'image/jpeg', 10, ?)
        """,
        ("b" * 64,),
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO profile_photos(workspace_id, basics_fact_id, evidence_id)
            VALUES (1, ?, ?)
            """,
            (basics, second_image),
        )
    db.execute("UPDATE profile_photos SET status='archived' WHERE id=?", (first,))
    db.execute(
        """
        INSERT INTO profile_photos(workspace_id, basics_fact_id, evidence_id)
        VALUES (1, ?, ?)
        """,
        (basics, second_image),
    )


def test_referenced_fact_cannot_be_purged(db):
    fact_id = add_fact(db, "experience", "referenced")
    add_experience(db, fact_id)
    resume_id = db.execute(
        "INSERT INTO resumes(workspace_id, display_name) VALUES (1, 'resume')"
    ).lastrowid
    version_id = db.execute(
        """
        INSERT INTO resume_versions(
            workspace_id, resume_id, version_number, content_hash
        ) VALUES (1, ?, 1, 'hash')
        """,
        (resume_id,),
    ).lastrowid
    db.execute(
        """
        INSERT INTO resume_fact_uses(
            workspace_id, resume_id, fact_id, section_code, block_key
        ) VALUES (1, ?, ?, 'experience', 'block')
        """,
        (resume_id, fact_id),
    )
    db.execute(
        """
        INSERT INTO resume_version_fact_snapshots(
            workspace_id, resume_version_id, fact_id, section_code, block_key
        ) VALUES (1, ?, ?, 'experience', 'block')
        """,
        (version_id, fact_id),
    )
    db.execute("UPDATE fact_records SET status = 'recycled' WHERE id = ?", (fact_id,))
    with pytest.raises(sqlite3.IntegrityError, match="referenced fact"):
        db.execute("UPDATE fact_records SET status = 'purged' WHERE id = ?", (fact_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE resume_version_fact_snapshots SET block_key = 'other' WHERE fact_id = ?",
            (fact_id,),
        )


def test_extension_values_require_registered_matching_type(db):
    draft_schema_id = db.execute(
        """
        INSERT INTO fact_schema_versions(category_code, version_number, status)
        VALUES ('basics', 2, 'draft')
        """
    ).lastrowid
    field_id = db.execute(
        """
        INSERT INTO fact_field_definitions(
            category_code, schema_version_id, field_key, label, value_type,
            requirement_level, is_extension, storage_table, storage_column
        ) VALUES ('basics', ?, 'pronouns', '代称', 'text', 'optional', 1,
                  'fact_extension_values', 'text_value')
        """,
        (draft_schema_id,),
    ).lastrowid
    fact_id = add_fact(
        db, "basics", "primary", schema_version_id=draft_schema_id
    )
    add_basics(db, fact_id)
    db.execute(
        """
        INSERT INTO fact_extension_values(
            workspace_id, fact_id, category_code, schema_version_id,
            field_definition_id, text_value
        ) VALUES (1, ?, 'basics', ?, ?, 'they/them')
        """,
        (fact_id, draft_schema_id, field_id),
    )
    with pytest.raises(sqlite3.IntegrityError, match="value type mismatch"):
        db.execute(
            """
            INSERT INTO fact_extension_values(
                workspace_id, fact_id, category_code, schema_version_id,
                field_definition_id, numeric_value
            ) VALUES (1, ?, 'basics', ?, ?, 1)
            """,
            (fact_id, draft_schema_id, field_id),
        )
    with pytest.raises(sqlite3.IntegrityError, match="value type mismatch"):
        db.execute(
            """
            UPDATE fact_extension_values
               SET text_value = NULL, numeric_value = 1
             WHERE fact_id = ? AND field_definition_id = ?
            """,
            (fact_id, field_id),
        )


def test_tag_name_and_alias_share_namespace(db):
    tag_id = db.execute(
        """
        INSERT INTO tags(workspace_id, display_name, normalized_name)
        VALUES (1, 'Python', 'python')
        """
    ).lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="tag alias collides"):
        db.execute(
            """
            INSERT INTO tag_aliases(workspace_id, tag_id, alias, normalized_alias)
            VALUES (1, ?, 'python', 'python')
            """,
            (tag_id,),
        )
    fact_id = add_fact(db, "experience", "tagged")
    add_experience(db, fact_id)
    db.execute("UPDATE tags SET status = 'archived' WHERE id = ?", (tag_id,))
    with pytest.raises(sqlite3.IntegrityError, match="active tag"):
        db.execute(
            "INSERT INTO fact_tags(workspace_id, fact_id, tag_id) VALUES (1, ?, ?)",
            (fact_id, tag_id),
        )


def test_audit_document_covers_snapshot_without_contact_data():
    text = checker.AUDIT_PATH.read_text(encoding="utf-8")
    data_ids = {value for value in checker.ids_in(text) if value.startswith("RL-DAT-")}
    assert data_ids == {f"RL-DAT-{number:03d}" for number in range(1, 27)}
    assert checker.check_audit_privacy() == []
    assert checker.check_source_snapshot() == []
    assert checker.SNAPSHOT_HASH in text


def test_chinese_diagrams_use_explicit_counts_and_include_required_fields():
    assert checker.check_chinese_diagrams() == []
    text = checker.DIAGRAM_PATH.read_text(encoding="utf-8")
    assert "1 : 0..1" in text
    assert "0..N : 0..N" in text
    assert "classDiagram" in text
