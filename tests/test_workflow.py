from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.services import ensure_fact_catalog
from app.workbench_database import WorkbenchBase, get_db
from app.workbench_models import Template, TemplatePreference, User, Workspace


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    WorkbenchBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as db:
        ensure_fact_catalog(db)
        user = User(display_name="Test user")
        db.add(user)
        db.flush()
        workspace = Workspace(owner_id=user.id, name="Test workspace")
        db.add(workspace)
        db.flush()
        template = Template(
            template_key="classic",
            display_name="Classic",
            description="Test template",
            renderer_key="classic",
        )
        db.add(template)
        db.flush()
        db.add(
            TemplatePreference(
                workspace_id=workspace.id,
                default_template_id=template.id,
            )
        )
        db.commit()

    def override():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def _fact(client, category_code, title, fields):
    return client.post(
        "/api/facts",
        json={
            "category_code": category_code,
            "title": title,
            "fields": fields,
        },
    ).json()


def test_conversion_save_restore_and_source_alert():
    client = make_client()
    fact = _fact(
        client,
        "experience",
        "项目 A",
        {"experience_kind": "project", "work_summary": "实现了采集流程"},
    )
    profile = client.post(
        "/api/requirement-profiles",
        json={
            "name": "数据工程师",
            "role_direction": "数据工程",
            "core_requirements": ["Python"],
            "resume_strategy": "突出工程实践",
        },
    ).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [fact["id"]]}},
    )
    converted = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()
    resume_id = converted["resume_id"]
    assert client.get(f"/api/resumes/{resume_id}/versions").json()[0][
        "version_number"
    ] == 1
    working = client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content"
    ]
    working["sections"][4]["blocks"][0]["content"] = "已润色的工程实践"
    client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": working}
    )
    saved = client.post(
        f"/api/resumes/{resume_id}/save",
        json={"change_summary": "润色项目描述"},
    ).json()
    assert saved["version_number"] == 2
    client.post(f"/api/resumes/{resume_id}/versions/1/restore")
    restored = client.get(f"/api/resumes/{resume_id}").json()
    assert restored["working_copy"]["content_state"] == "dirty"
    client.patch(
        f"/api/facts/{fact['id']}",
        json={"title": "项目 A", "fields": {"work_summary": "更新后的事实"}},
    )
    pending = client.get("/api/pending-issues").json()[0]
    assert pending["resume_id"] == resume_id
    assert pending["section_code"] == "experience"
    assert pending["block_key"] == f"fact-{fact['id']}"
    assert pending["source"]["fact"]["fields"]["work_summary"] == "更新后的事实"
    assert client.delete(f"/api/facts/{fact['id']}").json()["status"] == "recycled"
    app.dependency_overrides.clear()


def test_evidence_and_unreferenced_fact_deletion():
    client = make_client()
    fact = _fact(
        client,
        "skill",
        "Python",
        {"usage_context": "数据处理"},
    )
    evidence = client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "作品链接",
            "url": "https://example.com/project",
            "note": "验证材料",
        },
    )
    assert evidence.status_code == 201
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0][
        "title"
    ] == "作品链接"
    assert client.delete(f"/api/facts/{fact['id']}").json()["status"] == "recycled"
    assert client.get(f"/api/facts/{fact['id']}").json()["status"] == "recycled"
    app.dependency_overrides.clear()


def test_empty_linked_page_and_html_export():
    client = make_client()
    personal = _fact(
        client,
        "basics",
        "个人主档",
        {
            "name": "测试用户",
            "hometown": "示例省",
            "bio": "专注机器人数据实践",
        },
    )
    assert personal["fields"]["hometown"] == "示例省"
    schema = client.get("/api/fact-schemas/basics").json()
    assert schema["fields"][0]["key"] == "name"

    profile = client.post(
        "/api/requirement-profiles", json={"name": "机器人数据"}
    ).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    preview = client.get(f"/api/linked-resumes/{linked['id']}").json()[
        "preview"
    ]
    assert [
        section["id"] for section in preview["sections"] if section["blocks"]
    ] == ["target", "profile"]
    converted = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()
    export = client.post(
        f"/api/resumes/{converted['resume_id']}/versions/1/export?force=true"
    )
    assert export.status_code == 200
    assert "@page" in export.text and "size: A4" in export.text
    assert "专注机器人数据实践" in export.text
    app.dependency_overrides.clear()


def test_target_fields_render_in_export():
    client = make_client()
    created = _fact(
        client,
        "experience",
        "长内容项目",
        {
            "experience_kind": "work_internship",
            "organization": "测试组织",
            "role": "工程实习",
            "challenge": "原始挑战",
            "solution": "原始方案",
            "result_summary": "效率提升 100%",
        },
    )
    updated = client.patch(
        f"/api/facts/{created['id']}",
        json={
            "title": "已编辑项目",
            "fields": {
                "experience_kind": "work_internship",
                "organization": "新组织",
                "role": "核心开发",
                "challenge": "已编辑挑战",
                "solution": "已编辑方案",
                "result_summary": "效率提升 100%",
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["fields"]["organization"] == "新组织"

    profile = client.post(
        "/api/requirement-profiles", json={"name": "长内容验证"}
    ).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [created["id"]]}},
    )
    converted = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()
    content = client.get(f"/api/resumes/{converted['resume_id']}").json()[
        "working_copy"
    ]["content"]
    content["sections"][4]["blocks"][0]["content"] = "中文长段落。" * 800
    client.patch(
        f"/api/resumes/{converted['resume_id']}/working-copy",
        json={"content": content},
    )
    client.post(
        f"/api/resumes/{converted['resume_id']}/save",
        json={"change_summary": "长内容验证"},
    )
    export = client.post(
        f"/api/resumes/{converted['resume_id']}/versions/2/export?force=true"
    )
    assert export.status_code == 200
    assert export.text.count('class="page"') >= 2
    assert "新组织" in export.text and "100%" in export.text
    app.dependency_overrides.clear()
