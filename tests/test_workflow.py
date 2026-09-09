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
