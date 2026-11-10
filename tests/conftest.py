import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.workbench_database import WorkbenchBase, get_db
from app.services import ensure_fact_catalog
from app.workbench_models import Template, TemplatePreference, User, Workspace


def _enable_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", _enable_foreign_keys)
    WorkbenchBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        user = User(display_name="Test user")
        db.add(user)
        db.flush()
        workspace = Workspace(owner_id=user.id, name="Test workspace")
        db.add(workspace)
        db.flush()
        ensure_fact_catalog(db)
        template = Template(
            template_key="classic",
            display_name="Classic",
            description="Test template",
            renderer_key="classic",
            status="available",
        )
        db.add(template)
        db.flush()
        focus = Template(
            template_key="focus",
            display_name="Focus",
            description="Sidebar template in navy",
            renderer_key="focus",
            status="available",
        )
        db.add(focus)
        db.flush()
        db.add(
            TemplatePreference(
                workspace_id=workspace.id,
                default_template_id=template.id,
                last_selected_template_id=template.id,
            )
        )
        db.commit()
    try:
        yield Session
    finally:
        engine.dispose()


@pytest.fixture
def client(session_factory):
    Session = session_factory
    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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
    linked = client.post(
        "/api/linked-resumes",
        json={"profile_id": profile["id"]},
    ).json()
    converted = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert converted.status_code == 201, converted.text
    return profile, converted.json()["resume_id"]
