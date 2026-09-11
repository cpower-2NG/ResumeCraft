def test_profile_crud_and_opportunity_grouping(client):
    profile = client.post(
        "/api/requirement-profiles",
        json={"name": "后端工程师", "role_direction": "后端", "core_requirements": ["Python"]},
    ).json()
    assert profile["identity_key"]
    updated = client.patch(
        f"/api/requirement-profiles/{profile['id']}",
        json={"name": "后端工程师", "role_direction": "后端", "core_requirements": ["Python", "SQL"], "resume_strategy": "突出工程实践"},
    )
    assert updated.status_code == 200
    opportunity = client.post(
        f"/api/requirement-profiles/{profile['id']}/opportunities",
        json={"company": "甲公司", "title": "后端开发", "url": "https://example.com/job"},
    )
    assert opportunity.status_code == 201
    assert client.get(f"/api/requirement-profiles/{profile['id']}/opportunities").json()[0]["company"] == "甲公司"


def test_profile_recycle_bin_is_reversible_when_it_owns_a_resume(client):
    profile = client.post("/api/requirement-profiles", json={"name": "平台工程师"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert client.delete(f"/api/requirement-profiles/{profile['id']}").json() == {"mode": "recycled"}
    assert client.get("/api/requirement-profiles").json() == []
    recycled = client.get("/api/requirement-profiles?include_recycled=true").json()
    assert recycled[0]["status"] == "recycled"
    assert client.post(f"/api/requirement-profiles/{profile['id']}/restore").json()["status"] == "active"


def test_profile_list_exposes_active_formal_resume(client):
    profile = client.post("/api/requirement-profiles", json={"name": "平台工程师"}).json()
    assert client.get("/api/requirement-profiles").json()[0].get("active_resume_id") is None
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    listed = client.get("/api/requirement-profiles").json()[0]
    assert listed["active_resume_id"] == resume_id
