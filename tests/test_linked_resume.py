def test_linked_resume_starts_empty_and_only_selected_facts_enter_preview(client):
    fact = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "采集项目",
            "fields": {"context_summary": "建立采集流程"},
        },
    ).json()
    profile = client.post("/api/requirement-profiles", json={"name": "数据工程师"}).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    preview = client.get(f"/api/linked-resumes/{linked['id']}").json()["preview"]
    assert [section["id"] for section in preview["sections"] if section["blocks"]] == ["target"]

    updated = client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [fact["id"]]}})
    blocks = next(section["blocks"] for section in updated.json()["preview"]["sections"] if section["id"] == "experience")
    assert blocks[0]["source_refs"] == [fact["id"]]
    assert "建立采集流程" in blocks[0]["content"]


def test_fact_update_changes_linked_preview_but_not_formal_version(client):
    fact = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "项目",
            "fields": {"context_summary": "原始事实"},
        },
    ).json()
    profile = client.post("/api/requirement-profiles", json={"name": "工程师"}).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [fact["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    client.patch(
        f"/api/facts/{fact['id']}",
        json={"title": "项目", "fields": {"context_summary": "更新事实"}},
    )
    assert client.get(f"/api/linked-resumes/{linked['id']}").json()["preview"]["sections"][4]["blocks"][0]["content"] == "- 更新事实"
    current = client.get(f"/api/resumes/{resume_id}").json()["current"]["content"]
    experience = next(section for section in current["sections"] if section["id"] == "experience")
    assert "原始事实" in experience["blocks"][0]["content"]
