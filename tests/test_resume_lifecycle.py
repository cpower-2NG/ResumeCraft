from tests.conftest import create_profile, create_resume


def test_conversion_creates_v1_save_creates_v2_and_restore_creates_dirty_copy(client):
    profile, resume_id = create_resume(client)
    assert client.get(f"/api/resumes/{resume_id}/versions").json()[0]["version_number"] == 1
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][0]["blocks"].append({"id": "user-block", "title": "目标", "content": "后端开发", "source_refs": [], "origin": "user"})
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    assert client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "用户润色"}).json()["version_number"] == 2
    assert client.post(f"/api/resumes/{resume_id}/versions/1/restore").json()["dirty"] is True


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
    assert client.delete(f"/api/resumes/{old_resume_id}").json() == {"mode": "recycled"}
    assert client.get("/api/resumes").json() == []
    recycled = client.get("/api/resumes?include_recycled=true")
    assert recycled.status_code == 200
    assert recycled.json()[0]["id"] == old_resume_id

    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}")
    assert linked.status_code == 201
    recreated = client.post(f"/api/linked-resumes/{linked.json()['id']}/convert")
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["resume_id"] != old_resume_id

    restored = client.post(f"/api/resumes/{old_resume_id}/restore")
    assert restored.status_code == 200
    assert len(client.get("/api/resumes").json()) == 2


def test_forked_identity_is_viewable_and_saves_v1(client):
    _, resume_id = create_resume(client)
    forked = client.post(f"/api/resumes/{resume_id}/fork")
    assert forked.status_code == 201, forked.text
    new_id = forked.json()["resume_id"]

    detail = client.get(f"/api/resumes/{new_id}")
    assert detail.status_code == 200, detail.text
    data = detail.json()
    # A forked identity has no formal version yet; the detail must still be readable.
    assert data["current"] is None
    assert data["current_version"] is None
    assert data["working_copy"]["dirty"] is True
    assert client.get(f"/api/resumes/{new_id}/versions").json() == []

    saved = client.post(f"/api/resumes/{new_id}/save", json={"change_summary": "新身份首次保存"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version_number"] == 1
    assert saved.json()["reason"] == "identity_copy"
    assert client.get(f"/api/resumes/{new_id}").json()["current_version"] == 1
