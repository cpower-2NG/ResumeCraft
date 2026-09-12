def test_export_is_fixed_a4_and_paginates_long_formal_content(client):
    fact = client.post("/api/facts", json={"category": "experience", "title": "长项目", "details": {"summary": "事实"}}).json()
    profile = client.post("/api/requirement-profiles", json={"name": "工程师"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [fact["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][4]["blocks"][0]["content"] = "长内容。" * 800
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "导出验证"})
    export = client.post(f"/api/resumes/{resume_id}/versions/2/export")
    assert export.status_code == 200
    assert "@page" in export.text and "size: A4" in export.text and "width:210mm" in export.text
    assert export.text.count('class="page"') >= 2


def test_export_with_link_block_renders_anchor(client):
    fact = client.post(
        "/api/facts",
        json={"category": "links", "title": "个人作品集", "details": {"link_type": "作品集", "url": "https://example.com/portfolio", "label": "example.com/portfolio"}},
    ).json()
    profile = client.post("/api/requirement-profiles", json={"name": "作品集岗位"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"links": [fact["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    export = client.post(f"/api/resumes/{resume_id}/versions/1/export")
    assert export.status_code == 200, export.text
    assert '<a href="https://example.com/portfolio">' in export.text
    assert export.text.count("链接与作品集") == 1
