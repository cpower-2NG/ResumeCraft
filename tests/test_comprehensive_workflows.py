import base64
from io import BytesIO

from app import main as app_main
from tests.conftest import create_profile, create_resume


FIELDS = {
    "basics": {
        "name": "测试用户",
        "phone": "13800000000",
        "email": "test@example.com",
        "city": "深圳",
        "desired_city": "上海",
        "identity_status": "在职",
        "bio": "个人简介",
    },
    "education": {
        "school": "测试大学",
        "major": "计算机",
        "degree": "本科",
        "period_text": "2018-2022",
        "achievement": "获得奖学金",
    },
    "experience": {
        "experience_kind": "project",
        "organization": "测试团队",
        "role": "工程师",
        "period_text": "2022-2024",
        "work_summary": "完成项目",
        "result_summary": "效率提升",
    },
    "skill": {
        "proficiency": "熟练",
        "usage_context": "服务开发",
    },
    "achievement": {
        "achievement_kind": "honor",
        "period_text": "2024",
        "issuer": "测试机构",
        "result_text": "一等奖",
        "note": "公开成果",
    },
}


def create_fact(client, category_code, title=None, fields=None):
    response = client.post(
        "/api/facts",
        json={
            "category_code": category_code,
            "title": title or category_code,
            "fields": fields if fields is not None else FIELDS[category_code],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _linked(client, profile_id):
    response = client.post(
        "/api/linked-resumes", json={"profile_id": profile_id}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_every_resume_section_has_editable_fields_and_body(client):
    facts = {
        category: create_fact(client, category) for category in FIELDS
    }
    profile = create_profile(client, "全字段验证")
    linked = _linked(client, profile["id"])
    selected = {
        {"skill": "skills", "achievement": "awards"}.get(
            category, category
        ): [fact["id"]]
        for category, fact in facts.items()
    }
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": selected},
    )
    resume_id = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()["resume_id"]
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content"
    ]
    next(
        section for section in content["sections"] if section["id"] == "links"
    )["blocks"] = [
        {
            "id": "manual-portfolio",
            "type": "manual",
            "title": "作品集",
            "content": "手动维护的展示链接",
            "fields": {},
            "field_labels": {},
            "display_fields": [],
            "source_refs": [],
            "origin": "manual",
        }
    ]
    for section in content["sections"]:
        for block in section["blocks"]:
            block["title"] = f"已编辑-{section['id']}"
            block["content"] = f"已编辑正文-{section['id']}"
            for key in block.get("fields", {}):
                block["fields"][key] = f"已编辑字段-{key}"
    assert client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    ).status_code == 200
    assert client.post(
        f"/api/resumes/{resume_id}/save",
        json={"change_summary": "全字段编辑"},
    ).status_code == 200
    current = client.get(f"/api/resumes/{resume_id}").json()["current"][
        "content"
    ]
    blocks = [
        block
        for section in current["sections"]
        for block in section["blocks"]
    ]
    assert len(blocks) >= 8
    assert all(block["title"].startswith("已编辑-") for block in blocks)
    assert all(block["content"].startswith("已编辑正文-") for block in blocks)


def test_source_warning_is_visible_then_resolved_after_save(client):
    fact = create_fact(
        client,
        "experience",
        "来源项目",
        {"experience_kind": "project", "work_summary": "旧事实"},
    )
    profile = create_profile(client, "提醒验证")
    linked = _linked(client, profile["id"])
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [fact["id"]]}},
    )
    resume_id = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()["resume_id"]
    client.patch(
        f"/api/facts/{fact['id']}",
        json={"title": "来源项目", "fields": {"work_summary": "新事实"}},
    )
    pending = client.get("/api/pending-issues").json()
    assert len(pending) == 1 and pending[0]["resume_id"] == resume_id
    assert client.get(f"/api/resumes/{resume_id}").json()["warnings"] == 1
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content"
    ]
    content["sections"][4]["blocks"][0]["content"] = "已确认的新事实"
    client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    )
    client.post(
        f"/api/resumes/{resume_id}/save",
        json={"change_summary": "处理来源提醒"},
    )
    assert client.get("/api/pending-issues").json() == []
    assert client.get(f"/api/resumes/{resume_id}").json()["warnings"] == 0


def test_navigation_data_home_profiles_resumes_and_recycle_bin(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/overview").json()["stats"]["resumes"] == 0
    profile = create_profile(client, "导航验证")
    assert client.get("/api/requirement-profiles").json()[0]["id"] == profile["id"]
    _, resume_id = create_resume(client, profile)
    overview = client.get("/api/overview").json()
    assert overview["stats"]["profiles"] == 1
    assert overview["stats"]["resumes"] == 1
    assert overview["recent_resumes"][0]["id"] == resume_id
    assert client.delete(f"/api/resumes/{resume_id}").json()["status"] == "recycled"
    assert client.get("/api/resumes").json() == []
    assert client.get("/api/resumes?status=recycled").json()[0]["id"] == resume_id
    assert client.post(f"/api/resumes/{resume_id}/restore").json()["status"] == "active"


def test_dangerous_actions_return_target_state_and_are_reversible(client):
    unused = create_fact(client, "skill", "未引用资料")
    assert client.delete(f"/api/facts/{unused['id']}").json()["status"] == "recycled"
    assert client.post(f"/api/facts/{unused['id']}/restore").json()["status"] == "active"
    referenced = create_fact(client, "experience", "引用资料")
    profile = create_profile(client, "危险操作验证")
    linked = _linked(client, profile["id"])
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [referenced["id"]]}},
    )
    resume_id = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()["resume_id"]
    assert client.delete(f"/api/facts/{referenced['id']}").json()["status"] == "recycled"
    assert client.post(f"/api/facts/{referenced['id']}/restore").json()["status"] == "active"
    assert client.delete(f"/api/resumes/{resume_id}").json()["status"] == "recycled"
    assert client.post(f"/api/resumes/{resume_id}/restore").json()["status"] == "active"


def test_pending_issues_hide_recycled_resume_warnings(client):
    fact = create_fact(client, "experience", "来源项目", {"work_summary": "旧内容"})
    profile = create_profile(client, "待处理过滤")
    linked = _linked(client, profile["id"])
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [fact["id"]]}},
    )
    resume_id = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()["resume_id"]
    client.patch(
        f"/api/facts/{fact['id']}",
        json={"title": fact["title"], "fields": {"work_summary": "新内容"}},
    )
    assert len(client.get("/api/pending-issues").json()) == 1
    client.delete(f"/api/resumes/{resume_id}")
    assert client.get("/api/pending-issues").json() == []


def test_schema_endpoint_and_all_categories(client):
    for category in FIELDS:
        schema = client.get(f"/api/fact-schemas/{category}")
        assert schema.status_code == 200
        body = schema.json()
        assert body["category_code"] == category
        assert body["schema_version_id"]
        assert body["fields"]
    assert client.get("/api/fact-schemas/not-a-category").status_code == 422


def test_profile_audit_and_opportunity_routes(client):
    profile = create_profile(client, "画像审计")
    second = client.post(
        "/api/requirement-profiles",
        json={"name": "另一个画像", "role_direction": "其他"},
    ).json()
    client.patch(
        f"/api/requirement-profiles/{second['id']}",
        json={
            "name": profile["name"],
            "role_direction": profile["role_direction"],
            "core_requirements": profile["core_requirements"],
            "resume_strategy": profile["resume_strategy"],
        },
    )
    audit = client.get(
        f"/api/requirement-profiles/{second['id']}/audits"
    ).json()
    assert audit[0]["action"] == "updated"
    opportunity = client.post(
        "/api/opportunities",
        json={
            "requirement_profile_id": profile["id"],
            "company": "测试公司",
            "title": "目标岗位",
        },
    )
    assert opportunity.status_code == 201
    assert client.get(f"/api/opportunities?profile_id={profile['id']}").json()[0][
        "title"
    ] == "目标岗位"


def test_working_copy_states_and_versions_are_linear(client):
    _, resume_id = create_resume(client)
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content"
    ]
    content["sections"][0]["blocks"].append(
        {
            "id": "manual",
            "title": "手工块",
            "content": "内容",
            "source_refs": [],
            "origin": "user",
        }
    )
    changed = client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    ).json()
    assert changed["content_state"] == "dirty"
    client.post(
        f"/api/resumes/{resume_id}/save", json={"change_summary": "第一次保存"}
    )
    assert client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content_state"
    ] == "clean"


def test_version_restore_preserves_history(client):
    _, resume_id = create_resume(client)
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"][
        "content"
    ]
    content["sections"][0]["blocks"].append(
        {
            "id": "v2",
            "title": "第二版",
            "content": "修改",
            "source_refs": [],
            "origin": "user",
        }
    )
    client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    )
    client.post(
        f"/api/resumes/{resume_id}/save", json={"change_summary": "第二版"}
    )
    restored = client.post(f"/api/resumes/{resume_id}/versions/1/restore").json()
    assert restored["content_state"] == "dirty"
    assert restored["pending_reason"] == "rollback"
    versions = client.get(f"/api/resumes/{resume_id}/versions").json()
    assert [item["version_number"] for item in versions] == [2, 1]
    client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "回退"})
    assert client.get(f"/api/resumes/{resume_id}/versions").json()[0]["reason"] == "rollback"


def test_evidence_validation_and_archive_flow(client):
    fact = create_fact(client, "skill", "证据验证")
    assert client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "错误链接",
            "url": "ftp://example.com",
        },
    ).status_code == 422
    created = client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "有效链接",
            "url": "https://example.com",
        },
    )
    evidence_id = created.json()["id"]
    assert client.delete(f"/api/evidence/{evidence_id}").json()["status"] == "archived"
    bad_file = client.post(
        "/api/evidence/upload",
        data={"fact_id": str(fact["id"]), "title": "错误文件"},
        files={"file": ("resume.txt", BytesIO(b"bad"), "text/plain")},
    )
    assert bad_file.status_code == 422


def test_uploaded_evidence_preview(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_main, "ATTACHMENTS_DIR", tmp_path / "attachments")
    fact = create_fact(client, "achievement", "有证书的成果")
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n0sAAAAASUVORK5CYII="
    )
    uploaded = client.post(
        "/api/evidence/upload",
        data={"fact_id": str(fact["id"]), "title": "证书预览"},
        files={"file": ("certificate.png", image, "image/png")},
    )
    assert uploaded.status_code == 201
    evidence = uploaded.json()
    preview = client.get(evidence["preview_url"])
    assert preview.status_code == 200
    assert preview.content == image
    assert preview.headers["content-disposition"].startswith("inline")


def test_missing_resources_and_invalid_payloads(client):
    assert client.get("/api/facts/999").status_code == 404
    assert client.patch("/api/facts/999", json={"title": "不存在"}).status_code == 404
    assert client.get("/api/resumes/999").status_code == 404
    assert client.post("/api/resumes/999/save").status_code == 404
    assert client.post("/api/linked-resumes/999/convert").status_code == 404
    assert client.post("/api/requirement-profiles", json={"name": ""}).status_code == 422


def test_template_switch_never_drties_working_copy(client):
    _, resume_id = create_resume(client)
    current = client.get(f"/api/resumes/{resume_id}").json()["template"]["id"]
    same = client.patch(
        f"/api/resumes/{resume_id}/template", json={"template_id": current}
    )
    assert same.status_code == 200
    assert same.json()["content_state"] == "clean"
    templates = client.get("/api/templates").json()
    other = next(item for item in templates if item["id"] != current)
    before = client.get(f"/api/resumes/{resume_id}/versions").json()
    switched = client.patch(
        f"/api/resumes/{resume_id}/template",
        json={"template_id": other["id"]},
    )
    assert switched.status_code == 200
    assert client.get(f"/api/resumes/{resume_id}/versions").json() == before
    assert client.get(f"/api/resumes/{resume_id}").json()["template"]["id"] == other["id"]
