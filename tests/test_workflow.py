from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.workbench_database import get_db
from app.workbench_models import ResumeTemplate, TemplateVersion, User, Workspace
from app.workbench_database import WorkbenchBase


def make_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    WorkbenchBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        user = User(display_name="Test user")
        db.add(user); db.flush(); workspace = Workspace(owner_id=user.id, name="Test workspace"); db.add(workspace); db.flush()
        template = ResumeTemplate(workspace_id=workspace.id, name="Classic", slug="classic", description="Test template")
        db.add(template); db.flush(); db.add(TemplateVersion(template_id=template.id, version_number=1, content="<html></html>", checksum="test")); db.commit()
    def override():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_conversion_save_restore_and_source_alert():
    client = make_client()
    fact = client.post("/api/facts", json={"category":"experience","title":"项目 A","content":{"summary":"实现了采集流程"}}).json()
    profile = client.post("/api/requirement-profiles", json={"name":"数据工程师","role_direction":"数据工程","core_requirements":["Python"],"resume_strategy":"突出工程实践"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection":{"experience":[fact['id']]}})
    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()
    resume_id = converted["resume_id"]
    assert client.get(f"/api/resumes/{resume_id}/versions").json()[0]["version_number"] == 1
    working = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    working["sections"][4]["blocks"][0]["content"] = "已润色的工程实践"
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content":working})
    saved = client.post(f"/api/resumes/{resume_id}/save", json={"change_summary":"润色项目描述"}).json()
    assert saved["version_number"] == 2
    client.post(f"/api/resumes/{resume_id}/versions/1/restore")
    restored = client.get(f"/api/resumes/{resume_id}").json()
    assert restored["working_copy"]["dirty"] is True
    client.patch(f"/api/facts/{fact['id']}", json={"category":"experience","title":"项目 A","content":{"summary":"更新后的事实"}})
    pending = client.get("/api/pending-items").json()[0]
    assert pending["resume_id"] == resume_id
    assert pending["affected"] == [{"section_id": "experience", "block_id": f"fact-{fact['id']}"}]
    assert client.delete(f"/api/facts/{fact['id']}").json()["mode"] == "recycled"
    app.dependency_overrides.clear()


def test_evidence_and_unreferenced_fact_deletion():
    client = make_client()
    fact = client.post("/api/facts", json={"category":"skills", "title":"Python", "content":{"summary":"数据处理"}}).json()
    evidence = client.post("/api/evidence", json={"fact_id":fact["id"], "title":"作品链接", "url":"https://example.com/project", "note":"验证材料"})
    assert evidence.status_code == 201
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["title"] == "作品链接"
    assert client.delete(f"/api/facts/{fact['id']}").json()["mode"] == "permanent"
    assert client.get(f"/api/facts/{fact['id']}").status_code == 404
    app.dependency_overrides.clear()


def test_structured_fact_details_empty_linked_page_and_html_export():
    client = make_client()
    personal = client.post("/api/facts", json={
        "category": "basics", "title": "个人主档",
        "details": {"name": "许榕鑫", "hometown": "广东", "bio": "专注机器人数据实践"},
    }).json()
    assert personal["details"]["hometown"] == "广东"
    assert client.get("/api/fact-schemas/basics").json()[0]["key"] == "name"

    profile = client.post("/api/requirement-profiles", json={"name": "机器人数据"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    preview = client.get(f"/api/linked-resumes/{linked['id']}").json()["preview"]
    assert [section["id"] for section in preview["sections"] if section["blocks"]] == ["target"]
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"profile": [personal["id"]]}})
    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()
    export = client.post(f"/api/resumes/{converted['resume_id']}/versions/1/export")
    assert export.status_code == 200
    assert "@page" in export.text and "size: A4" in export.text and "width:210mm" in export.text
    assert "专注机器人数据实践" in export.text
    app.dependency_overrides.clear()


def test_fact_details_can_be_updated_and_export_renders_fields_and_long_text():
    client = make_client()
    created = client.post("/api/facts", json={
        "category": "experience", "title": "长内容项目",
        "details": {"organization": "测试组织", "role": "工程实习", "challenge": "原始挑战", "solution": "原始方案"},
        "custom_fields": [{"key": "metric", "label": "指标", "value": "99%", "displayable": True}],
    }).json()
    updated = client.patch(f"/api/facts/{created['id']}", json={
        "category": "experience", "title": "已编辑项目",
        "details": {"organization": "新组织", "role": "核心开发", "challenge": "已编辑挑战", "solution": "已编辑方案"},
        "custom_fields": [{"key": "metric", "label": "指标", "value": "100%", "displayable": True}],
    })
    assert updated.status_code == 200
    assert updated.json()["title"] == "已编辑项目"
    assert updated.json()["details"]["organization"] == "新组织"
    assert updated.json()["custom_fields"][0]["value"] == "100%"

    profile = client.post("/api/requirement-profiles", json={"name": "长内容验证"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [created["id"]]}})
    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()
    content = client.get(f"/api/resumes/{converted['resume_id']}").json()["working_copy"]["content"]
    content["sections"][4]["blocks"][0]["content"] = "中文长段落。" * 800
    client.patch(f"/api/resumes/{converted['resume_id']}/working-copy", json={"content": content})
    client.post(f"/api/resumes/{converted['resume_id']}/save", json={"change_summary": "长内容验证"})
    export = client.post(f"/api/resumes/{converted['resume_id']}/versions/2/export")
    assert export.status_code == 200
    assert export.text.count('class="page"') >= 2
    assert "新组织" in export.text and "100%" in export.text
    app.dependency_overrides.clear()
