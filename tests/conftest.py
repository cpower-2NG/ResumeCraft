import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.workbench_database import WorkbenchBase, get_db
from app.workbench_models import ResumeTemplate, TemplateVersion, User, Workspace


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    WorkbenchBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        user = User(display_name="Test user")
        db.add(user)
        db.flush()
        workspace = Workspace(owner_id=user.id, name="Test workspace")
        db.add(workspace)
        db.flush()
        template = ResumeTemplate(workspace_id=workspace.id, name="Classic", slug="classic", description="Test template")
        db.add(template)
        db.flush()
        db.add(TemplateVersion(template_id=template.id, version_number=1, content="<html></html>", checksum="test"))
        db.commit()

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_profile(client, name="后端工程师"):
    return client.post(
        "/api/requirement-profiles",
        json={
            "name": name,
            "role_direction": "后端工程",
            "core_requirements": ["Python", "SQL"],
            "resume_strategy": "突出工程实践",
        },
    ).json()


def create_resume(client, profile=None):
    profile = profile or create_profile(client)
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert converted.status_code == 201, converted.text
    return profile, converted.json()["resume_id"]
