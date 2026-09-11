from io import BytesIO

from tests.conftest import create_profile, create_resume


DETAILS = {
    "basics": {"name": "测试用户", "phone": "13800000000", "email": "test@example.com", "city": "深圳", "desired_city": "上海", "status": "在职"},
    "education": {"school": "测试大学", "major": "计算机", "degree": "本科", "period": "2018-2022", "achievement": "获得奖学金"},
    "experience": {"organization": "测试团队", "role": "工程师", "period": "2022-2024", "work": "完成项目", "outcome": "效率提升"},
    "skills": {"skill_category": "后端", "proficiency": "熟练", "context": "服务开发"},
    "awards": {"period": "2024", "issuer": "测试机构", "result": "一等奖", "note": "公开成果"},
    "links": {"link_type": "作品集", "url": "https://example.com", "label": "作品主页", "note": "项目链接"},
}


def create_fact(client, category, title=None, details=None):
    response = client.post(
        "/api/facts",
        json={"category": category, "title": title or category, "details": details or DETAILS[category]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_every_resume_section_has_editable_title_fields_and_body(client):
    facts = {category: create_fact(client, category) for category in DETAILS}
    profile = create_profile(client, "全字段验证")
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    selected = {category: [fact["id"]] for category, fact in facts.items()}
    selected["profile"] = [facts["basics"]["id"]]
    preview = client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": selected}).json()["preview"]
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]

    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    for section in content["sections"]:
        for block in section["blocks"]:
            block["title"] = f"已编辑-{section['id']}"
            block["content"] = f"已编辑正文-{section['id']}"
            for key in block.get("fields", {}):
                block["fields"][key] = f"已编辑字段-{key}"
    assert client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content}).status_code == 200
    saved = client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "全字段编辑"})
    assert saved.status_code == 200

    current = client.get(f"/api/resumes/{resume_id}").json()["current"]["content"]
    blocks = [block for section in current["sections"] for block in section["blocks"]]
    assert len(blocks) >= 8
    assert all(block["title"].startswith("已编辑-") for block in blocks)
    assert all(block["content"].startswith("已编辑正文-") for block in blocks)


def test_resume_source_warning_is_visible_then_resolved_after_save_and_refresh(client):
    fact = create_fact(client, "experience", "来源项目", {"summary": "旧事实"})
    profile = create_profile(client, "提醒验证")
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [fact["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]

    client.patch(f"/api/facts/{fact['id']}", json={"category": "experience", "title": "来源项目", "details": {"summary": "新事实"}})
    pending = client.get("/api/pending-items").json()
    assert len(pending) == 1 and pending[0]["resume_id"] == resume_id
    assert client.get(f"/api/resumes?include_recycled=true").json()[0]["warnings"] == 1

    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][4]["blocks"][0]["content"] = "已确认的新事实"
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    assert client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "处理来源提醒"}).status_code == 200
    assert client.get("/api/pending-items").json() == []
    assert client.get(f"/api/resumes/{resume_id}").json()["warnings"] == 0


def test_navigation_data_for_home_profiles_resumes_and_recycle_bin(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    empty = client.get("/api/overview").json()
    assert empty["stats"]["resumes"] == 0
    profile = create_profile(client, "导航验证")
    assert client.get("/api/requirement-profiles").json()[0]["id"] == profile["id"]
    _, resume_id = create_resume(client, profile)
    overview = client.get("/api/overview").json()
    assert overview["stats"]["profiles"] == 1 and overview["stats"]["resumes"] == 1
    assert overview["recent_resumes"][0]["id"] == resume_id
    assert client.get("/api/resumes").json()[0]["id"] == resume_id
    assert client.delete(f"/api/resumes/{resume_id}").json() == {"mode": "recycled"}
    assert client.get("/api/resumes").json() == []
    assert client.get("/api/resumes?include_recycled=true").json()[0]["status"] == "recycled"
    assert client.post(f"/api/resumes/{resume_id}/restore").json()["status"] == "active"
    assert client.get("/api/resumes").json()[0]["id"] == resume_id


def test_dangerous_actions_return_explicit_state_and_are_reversible(client):
    unused = create_fact(client, "skills", "未引用资料")
    assert client.delete(f"/api/facts/{unused['id']}").json() == {"mode": "permanent"}
    assert client.get(f"/api/facts/{unused['id']}").status_code == 404

    referenced = create_fact(client, "experience", "引用资料")
    profile = create_profile(client, "危险操作验证")
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [referenced["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    assert client.delete(f"/api/facts/{referenced['id']}").json() == {"mode": "recycled"}
    assert client.get(f"/api/facts/{referenced['id']}").json()["status"] == "recycled"
    assert client.post(f"/api/facts/{referenced['id']}/restore").json()["status"] == "active"
    assert client.delete(f"/api/resumes/{resume_id}").json() == {"mode": "recycled"}
    assert client.post(f"/api/resumes/{resume_id}/restore").json()["status"] == "active"


def test_fact_schema_and_all_categories_can_be_loaded_for_edit_forms(client):
    expected = set(DETAILS)
    assert set(client.get("/api/fact-schemas/basics").json()[0]) >= {"key", "label", "type", "required"}
    for category in expected:
        schema = client.get(f"/api/fact-schemas/{category}")
        assert schema.status_code == 200
        assert schema.json()
    assert client.get("/api/fact-schemas/not-a-category").status_code == 404


def test_profile_edit_duplicate_identity_and_opportunity_routes(client):
    first = create_profile(client, "重复画像")
    second = client.post("/api/requirement-profiles", json={"name": "另一个画像", "role_direction": "其他"}).json()
    conflict = client.patch(
        f"/api/requirement-profiles/{second['id']}",
        json={"name": first["name"], "role_direction": first["role_direction"], "core_requirements": first["core_requirements"], "resume_strategy": first["resume_strategy"]},
    )
    assert conflict.status_code == 409
    opportunity = client.post(f"/api/requirement-profiles/{first['id']}/opportunities", json={"company": "测试公司", "title": "目标岗位"})
    assert opportunity.status_code == 201
    assert client.get(f"/api/requirement-profiles/{first['id']}/opportunities").json()[0]["title"] == "目标岗位"
    assert client.get("/api/requirement-profiles/999/opportunities").status_code == 404


def test_duplicate_active_resume_is_rejected_but_recycled_resume_can_be_recreated(client):
    profile = create_profile(client, "重复转换")
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    first = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert first.status_code == 201
    duplicate = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert duplicate.status_code == 409
    client.delete(f"/api/resumes/{first.json()['resume_id']}")
    recreated = client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert recreated.status_code == 201
    assert recreated.json()["resume_id"] != first.json()["resume_id"]


def test_working_copy_save_is_dirty_then_clean_and_versions_are_linear(client):
    _, resume_id = create_resume(client)
    detail = client.get(f"/api/resumes/{resume_id}").json()
    content = detail["working_copy"]["content"]
    content["sections"][0]["blocks"].append({"id": "manual", "title": "手工块", "content": "内容", "source_refs": [], "origin": "user"})
    assert client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content}).json()["dirty"] is True
    assert client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "第一次保存"}).status_code == 200
    assert client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["dirty"] is False

    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][0]["blocks"][0]["content"] = "并发草稿"
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    second = client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "第二次保存"})
    assert second.status_code == 200
    assert second.json()["version_number"] == 3
    assert client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["dirty"] is False


def test_version_restore_does_not_overwrite_immutable_history(client):
    _, resume_id = create_resume(client)
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][0]["blocks"].append({"id": "v2", "title": "第二版", "content": "修改", "source_refs": [], "origin": "user"})
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "第二版"})
    assert client.post(f"/api/resumes/{resume_id}/versions/1/restore").json() == {"restored_version": 1, "dirty": True}
    versions = client.get(f"/api/resumes/{resume_id}/versions").json()
    assert [item["version_number"] for item in versions] == [2, 1]
    assert client.post(f"/api/resumes/{resume_id}/versions/999/restore").status_code == 404


def test_evidence_validation_and_archive_flow(client):
    fact = create_fact(client, "skills", "证据验证")
    assert client.post("/api/evidence", json={"fact_id": fact["id"], "title": "错误链接", "url": "ftp://example.com"}).status_code == 422
    created = client.post("/api/evidence", json={"fact_id": fact["id"], "title": "有效链接", "url": "https://example.com"})
    assert created.status_code == 201
    evidence_id = created.json()["id"]
    assert client.delete(f"/api/evidence/{evidence_id}").json() == {"mode": "recycled"}
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["status"] == "recycled"
    bad_file = client.post("/api/evidence/upload", data={"fact_id": str(fact["id"]), "title": "错误文件"}, files={"file": ("resume.txt", BytesIO(b"bad"), "text/plain")})
    assert bad_file.status_code == 422


def test_missing_resources_and_invalid_payloads_are_reported(client):
    assert client.get("/api/facts/999").status_code == 404
    assert client.patch("/api/facts/999", json={"category": "skills", "title": "不存在"}).status_code == 404
    assert client.get("/api/resumes/999").status_code == 404
    assert client.post("/api/resumes/999/save", json={"change_summary": "不存在"}).status_code == 404
    assert client.post("/api/linked-resumes/999/convert").status_code == 404
    assert client.post("/api/requirement-profiles", json={"name": ""}).status_code == 201
    assert client.post("/api/evidence", json={"fact_id": 999, "title": "证据", "url": "https://example.com"}).status_code == 404
