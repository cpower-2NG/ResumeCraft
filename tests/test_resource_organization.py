import base64
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app import main as app_main
from app.workbench_database import WorkbenchBase
from app.workbench_models import FactAchievementDetail
from tests.conftest import create_profile


def test_clean_database_migrates_to_target_resource_schema(tmp_path: Path):
    database = tmp_path / "clean.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "head")

    connection = sqlite3.connect(database)
    try:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0] == "0018_profile_photos"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(fact_records)")
        }
        assert {"category_code", "schema_version_id", "business_key"} <= columns
        assert "category" not in columns
        assert "content" not in columns
        assert connection.execute(
            "SELECT count(*) FROM fact_categories"
        ).fetchone()[0] == 5
        assert connection.execute(
            "SELECT count(*) FROM fact_field_definitions"
        ).fetchone()[0] == 46
        assert connection.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='table' AND name='link_fact_details'"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def _fact(client, category_code, title, fields=None, **extra):
    response = client.post(
        "/api/facts",
        json={
            "category_code": category_code,
            "title": title,
            "fields": fields or {},
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_basics_is_singleton_and_resume_presentation_reads_basics(client):
    basics = _fact(
        client,
        "basics",
        "个人档案",
        {
            "name": "测试用户",
            "city": "深圳",
            "desired_city": "深圳",
            "availability": "每周五天",
            "bio": "面向具身智能的数据工程表达",
        },
    )
    assert basics["category_code"] == "basics"
    assert basics["fields"]["city"] == "深圳"
    duplicate = client.post(
        "/api/facts",
        json={
            "category_code": "basics",
            "title": "第二份档案",
            "fields": {"name": "另一人"},
        },
    )
    assert duplicate.status_code == 409

    profile = create_profile(client, "数据采集岗位")
    assert "personal_summary" not in profile
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    preview = client.get(f"/api/linked-resumes/{linked['id']}").json()["preview"]
    summary = next(
        section for section in preview["sections"] if section["id"] == "profile"
    )
    target = next(
        section for section in preview["sections"] if section["id"] == "target"
    )
    assert summary["blocks"][0]["content"] == "面向具身智能的数据工程表达"
    assert target["blocks"][0]["fields"]["desired_city"] == "深圳"
    assert target["blocks"][0]["fields"]["availability"] == "每周五天"


def test_experience_links_skills_groups_and_tags(client):
    skill = _fact(
        client,
        "skill",
        "ROS2",
        {"proficiency": "熟练", "usage_context": "机器人项目"},
    )
    assert skill["skill_group"]["display_name"] == "其他"
    experience = _fact(
        client,
        "experience",
        "机器人项目",
        {
            "experience_kind": "project",
            "organization": "实验室",
            "work_summary": "完成 ROS2 数据采集",
        },
        skill_ids=[skill["id"]],
        tags=["具身智能", "数据采集"],
    )
    assert experience["skill_ids"] == [skill["id"]]
    assert experience["linked_skills"] == [{"id": skill["id"], "title": "ROS2"}]
    assert experience["tags"] == ["具身智能", "数据采集"]
    tagged = client.get(
        "/api/facts?category_code=experience&tag=具身智能"
    ).json()
    assert [item["id"] for item in tagged] == [experience["id"]]

    changed = client.patch(
        f"/api/facts/{experience['id']}",
        json={
            "fields": {
                "achievement_kind": "honor",
                "result_text": "一等奖",
            }
        },
    )
    assert changed.status_code == 422


def test_achievement_parent_must_be_an_experience(client, session_factory):
    skill = _fact(client, "skill", "Python")
    invalid = client.post(
        "/api/facts",
        json={
            "category_code": "achievement",
            "title": "错误归属",
            "fields": {
                "achievement_kind": "honor",
                "experience_fact_id": skill["id"],
                "result_text": "一等奖",
            },
        },
    )
    assert invalid.status_code == 422

    experience = _fact(
        client,
        "experience",
        "竞赛项目",
        {"experience_kind": "competition", "work_summary": "完成比赛"},
    )
    achievement = _fact(
        client,
        "achievement",
        "竞赛一等奖",
        {
            "achievement_kind": "honor",
            "experience_fact_id": experience["id"],
            "issuer": "赛事主办方",
            "result_text": "一等奖",
        },
    )
    assert achievement["fields"]["experience_fact_id"] == experience["id"]
    with session_factory() as db:
        detail = db.get(FactAchievementDetail, achievement["id"])
        assert detail.experience_fact_id == experience["id"]


def test_schema_endpoint_exposes_controlled_definitions(client):
    schema = client.get("/api/fact-schemas/experience").json()
    assert schema["category_code"] == "experience"
    assert schema["schema_version_id"]
    fields = {item["key"]: item for item in schema["fields"]}
    assert fields["experience_kind"]["requirement_level"] == "required_for_output"
    assert {item["value"] for item in fields["experience_kind"]["options"]} >= {
        "project",
        "competition",
        "research",
    }
    assert "link_fact_details" not in WorkbenchBase.metadata.tables
    assert "fact_records" in WorkbenchBase.metadata.tables


def test_profile_photo_upload_replace_restore_and_remove(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr(app_main, "ATTACHMENTS_DIR", tmp_path / "attachments")
    basics = _fact(client, "basics", "个人档案", {"name": "测试用户"})
    first_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n0sAAAAASUVORK5CYII="
    )
    second_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    first = client.post(
        f"/api/facts/{basics['id']}/profile-photo",
        files={"file": ("photo-one.png", first_image, "image/png")},
    )
    assert first.status_code == 201, first.text
    first_photo = first.json()
    assert first_photo["status"] == "active"
    assert first_photo["evidence"]["preview_url"].endswith("/file")
    state = client.get(f"/api/facts/{basics['id']}/profile-photo").json()
    assert state["current"]["id"] == first_photo["id"]
    assert state["history"] == []
    assert client.get(f"/api/facts/{basics['id']}/evidence").json() == []

    second = client.post(
        f"/api/facts/{basics['id']}/profile-photo",
        files={"file": ("photo-two.png", second_image, "image/png")},
    )
    assert second.status_code == 201, second.text
    second_photo = second.json()
    state = client.get(f"/api/facts/{basics['id']}/profile-photo").json()
    assert state["current"]["id"] == second_photo["id"]
    assert [item["id"] for item in state["history"]] == [first_photo["id"]]

    restored = client.post(f"/api/profile-photos/{first_photo['id']}/restore")
    assert restored.status_code == 200
    state = client.get(f"/api/facts/{basics['id']}/profile-photo").json()
    assert state["current"]["id"] == first_photo["id"]
    assert [item["id"] for item in state["history"]] == [second_photo["id"]]

    removed = client.delete(f"/api/profile-photos/{first_photo['id']}")
    assert removed.status_code == 200
    assert removed.json()["status"] == "archived"
    assert (
        client.get(f"/api/facts/{basics['id']}/profile-photo").json()["current"]
        is None
    )


def test_profile_photo_rejects_fake_image(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_main, "ATTACHMENTS_DIR", tmp_path / "attachments")
    basics = _fact(client, "basics", "个人档案", {"name": "测试用户"})
    response = client.post(
        f"/api/facts/{basics['id']}/profile-photo",
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert response.status_code == 422


def test_profile_photo_flows_into_resume_content_and_self_contained_export(
    client, tmp_path, monkeypatch
):
    monkeypatch.setattr(app_main, "ATTACHMENTS_DIR", tmp_path / "attachments")
    basics = _fact(client, "basics", "个人档案", {"name": "测试用户"})
    first_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n0sAAAAASUVORK5CYII="
    )
    second_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    first = client.post(
        f"/api/facts/{basics['id']}/profile-photo",
        files={"file": ("portrait-one.png", first_image, "image/png")},
    ).json()

    profile = create_profile(client, "照片岗位")
    linked = client.post(
        "/api/linked-resumes",
        json={
            "profile_id": profile["id"],
            "selection": {"basics": [basics["id"]]},
        },
    ).json()
    preview = client.get(f"/api/linked-resumes/{linked['id']}").json()["preview"]
    basic_block = next(
        section for section in preview["sections"] if section["id"] == "basics"
    )["blocks"][0]
    assert basic_block["photo"]["photo_id"] == first["id"]
    assert basic_block["photo"]["evidence_id"] == first["evidence_id"]
    assert basic_block["photo"]["preview_url"].endswith("/file")

    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert converted.status_code == 201, converted.text
    resume_id = converted.json()["resume_id"]
    resume = client.get(f"/api/resumes/{resume_id}").json()
    saved_photo = next(
        section for section in resume["working_copy"]["content"]["sections"]
        if section["id"] == "basics"
    )["blocks"][0]["photo"]
    assert saved_photo["evidence_id"] == first["evidence_id"]

    exported = client.post(
        f"/api/resumes/{resume_id}/versions/1/export?force=true"
    )
    assert exported.status_code == 200, exported.text
    assert "data:image/png;base64," in exported.text
    assert 'class="resume-photo ' in exported.text

    client.post(
        f"/api/facts/{basics['id']}/profile-photo",
        files={"file": ("portrait-two.png", second_image, "image/png")},
    )
    resume = client.get(f"/api/resumes/{resume_id}").json()
    changed = next(
        section for section in resume["working_copy"]["content"]["sections"]
        if section["id"] == "basics"
    )["blocks"][0]["photo"]
    assert changed["evidence_id"] != first["evidence_id"]
    assert resume["working_copy"]["content_state"] == "dirty"

    client.delete(f"/api/profile-photos/{changed['photo_id']}")
    resume = client.get(f"/api/resumes/{resume_id}").json()
    removed = next(
        section for section in resume["working_copy"]["content"]["sections"]
        if section["id"] == "basics"
    )["blocks"][0]
    assert "photo" not in removed
