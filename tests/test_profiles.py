def test_profile_crud_and_opportunity_grouping(client):
    profile = client.post(
        "/api/requirement-profiles",
        json={"name": "后端工程师", "role_direction": "后端", "core_requirements": ["Python"]},
    ).json()
    assert "identity_key" not in profile
    updated = client.patch(
        f"/api/requirement-profiles/{profile['id']}",
        json={"name": "后端工程师", "role_direction": "后端", "core_requirements": ["Python", "SQL"], "resume_strategy": "突出工程实践"},
    )
    assert updated.status_code == 200
    opportunity = client.post(
        "/api/opportunities",
        json={
            "requirement_profile_id": profile["id"],
            "company": "甲公司",
            "title": "后端开发",
            "url": "https://example.com/job",
        },
    )
    assert opportunity.status_code == 201
    assert client.get(f"/api/opportunities?profile_id={profile['id']}").json()[0]["company"] == "甲公司"


def test_profile_recycle_bin_is_reversible_when_it_owns_a_resume(client):
    profile = client.post("/api/requirement-profiles", json={"name": "平台工程师"}).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert client.delete(f"/api/requirement-profiles/{profile['id']}").json()["status"] == "recycled"
    assert client.get("/api/requirement-profiles").json() == []
    recycled = client.get("/api/requirement-profiles?status=recycled").json()
    assert recycled[0]["status"] == "recycled"
    assert client.post(f"/api/requirement-profiles/{profile['id']}/restore").json()["status"] == "active"


def test_profile_list_exposes_active_formal_resume(client):
    profile = client.post("/api/requirement-profiles", json={"name": "平台工程师"}).json()
    assert client.get("/api/requirement-profiles").json()[0].get("active_resume_id") is None
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    listed = client.get("/api/requirement-profiles").json()[0]
    assert listed["active_resume_id"] == resume_id
