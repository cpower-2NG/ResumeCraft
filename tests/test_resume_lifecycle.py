from tests.conftest import create_profile, create_resume


def test_conversion_creates_v1_save_creates_v2_and_restore_creates_dirty_copy(client):
    profile, resume_id = create_resume(client)
    assert client.get(f"/api/resumes/{resume_id}/versions").json()[0]["version_number"] == 1
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][0]["blocks"].append({"id": "user-block", "title": "目标", "content": "后端开发", "source_refs": [], "origin": "user"})
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    assert client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "用户润色"}).json()["version_number"] == 2
    assert client.post(f"/api/resumes/{resume_id}/versions/1/restore").json()["content_state"] == "dirty"


def test_formal_resume_contains_editable_job_target(client):
    profile, resume_id = create_resume(client, create_profile(client, "机器人数据工程师"))
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    target = next(section for section in content["sections"] if section["id"] == "target")
    assert target["blocks"][0]["fields"]["role_direction"] == "后端工程"
    assert target["blocks"][0]["fields"]["core_requirements"] == "Python、SQL"

    block = target["blocks"][0]
    block["fields"]["role_direction"] = "机器人数据工程"
    block["content"] = "突出采集流程、数据质量和自动化实践"
    assert client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content}).status_code == 200
    assert client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "编辑求职目标"}).status_code == 200
    saved = client.get(f"/api/resumes/{resume_id}").json()["current"]["content"]
    saved_target = next(section for section in saved["sections"] if section["id"] == "target")
    assert saved_target["blocks"][0]["fields"]["role_direction"] == "机器人数据工程"


def test_deleted_resume_is_visible_in_recycle_bin_and_same_profile_can_create_new_resume(client):
    profile, old_resume_id = create_resume(client, create_profile(client, "后端工程师"))
    assert client.delete(f"/api/resumes/{old_resume_id}").json()["status"] == "recycled"
    assert client.get("/api/resumes").json() == []
    recycled = client.get("/api/resumes?status=recycled")
    assert recycled.status_code == 200
    assert recycled.json()[0]["id"] == old_resume_id

    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    )
    assert linked.status_code == 201
    recreated = client.post(f"/api/linked-resumes/{linked.json()['id']}/convert")
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["resume_id"] != old_resume_id

    restored = client.post(f"/api/resumes/{old_resume_id}/restore")
    assert restored.status_code == 409
    client.delete(f"/api/resumes/{recreated.json()['resume_id']}")
    assert client.post(f"/api/resumes/{old_resume_id}/restore").status_code == 200


def test_resume_profile_edit_copies_profile_without_opportunities(client):
    profile, resume_id = create_resume(client)
    client.post(
        "/api/opportunities",
        json={
            "requirement_profile_id": profile["id"],
            "company": "原公司",
            "title": "原岗位",
        },
    )
    changed = client.patch(
        f"/api/resumes/{resume_id}/profile",
        json={"role_direction": "机器人工程", "core_requirements": ["ROS2"]},
    )
    assert changed.status_code == 200, changed.text
    copied = changed.json()["profile"]
    assert copied["id"] != profile["id"]
    assert copied["role_direction"] == "机器人工程"
    original = client.get(f"/api/requirement-profiles/{profile['id']}").json()
    assert original["role_direction"] != "机器人工程"
    assert client.get(
        f"/api/opportunities?profile_id={copied['id']}"
    ).json() == []
