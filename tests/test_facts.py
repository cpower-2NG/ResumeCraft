def test_fact_crud_structured_fields_and_audit(client):
    created = client.post(
        "/api/facts",
        json={
            "category": "experience",
            "title": "采集平台",
            "details": {"organization": "测试团队", "role": "后端工程师", "outcome": "吞吐提升"},
            "custom_fields": [{"key": "metric", "label": "指标", "value": "30%", "displayable": True}],
        },
    )
    assert created.status_code == 201
    fact = created.json()
    assert fact["details"]["organization"] == "测试团队"
    assert fact["custom_fields"][0]["value"] == "30%"

    updated = client.patch(
        f"/api/facts/{fact['id']}",
        json={
            "category": "experience",
            "title": "采集平台（更新）",
            "details": {"organization": "新团队", "role": "核心开发"},
            "custom_fields": [],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "采集平台（更新）"
    assert updated.json()["details"]["organization"] == "新团队"
    assert len(client.get(f"/api/facts/{fact['id']}/audits").json()) == 2


def test_fact_recycle_bin_lists_recycled_fact_and_restore(client):
    fact = client.post("/api/facts", json={"category": "skills", "title": "Python", "details": {"context": "API"}}).json()
    assert client.delete(f"/api/facts/{fact['id']}").json() == {"mode": "permanent"}

    referenced = client.post("/api/facts", json={"category": "experience", "title": "项目", "details": {"summary": "事实"}}).json()
    profile = client.post("/api/requirement-profiles", json={"name": "数据工程"}).json()
    linked = client.post(f"/api/linked-resumes?profile_id={profile['id']}").json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [referenced["id"]]}})
    client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert client.delete(f"/api/facts/{referenced['id']}").json() == {"mode": "recycled"}

    active = client.get("/api/facts").json()
    recycled = client.get("/api/facts?include_recycled=true").json()
    assert all(item["id"] != referenced["id"] for item in active)
    assert any(item["id"] == referenced["id"] and item["status"] == "recycled" for item in recycled)
    restored = client.post(f"/api/facts/{referenced['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"


def test_evidence_link_is_reachable_from_fact(client):
    fact = client.post("/api/facts", json={"category": "skills", "title": "Python"}).json()
    response = client.post("/api/evidence", json={"fact_id": fact["id"], "title": "作品链接", "url": "https://example.com", "note": "验证"})
    assert response.status_code == 201
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["title"] == "作品链接"


def test_evidence_can_be_recycled_and_restored(client):
    fact = client.post("/api/facts", json={"category": "skills", "title": "Python"}).json()
    evidence = client.post("/api/evidence", json={"fact_id": fact["id"], "title": "证书链接", "url": "https://example.com/cert"}).json()
    assert client.delete(f"/api/evidence/{evidence['id']}").json() == {"mode": "recycled"}
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["status"] == "recycled"
    restored = client.post(f"/api/evidence/{evidence['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
