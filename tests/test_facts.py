from app.workbench_models import FactFieldDefinition, FactSchemaVersion


def test_fact_crud_target_fields_and_audit(client):
    created = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "采集平台",
            "fields": {
                "experience_kind": "project",
                "organization": "测试团队",
                "role": "后端工程师",
                "result_summary": "吞吐提升",
            },
            "tags": ["机器人"],
            "skill_ids": [],
        },
    )
    assert created.status_code == 201
    fact = created.json()
    assert fact["category_code"] == "experience"
    assert fact["schema_version_id"]
    assert fact["business_key"]
    assert fact["fields"]["organization"] == "测试团队"
    assert "details" not in fact
    assert fact["tags"] == ["机器人"]

    updated = client.patch(
        f"/api/facts/{fact['id']}",
        json={
            "title": "采集平台（更新）",
            "fields": {
                "experience_kind": "project",
                "organization": "新团队",
                "role": "核心开发",
            },
            "tags": ["机器人"],
            "skill_ids": [],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "采集平台（更新）"
    assert updated.json()["fields"]["organization"] == "新团队"
    assert len(client.get(f"/api/facts/{fact['id']}/audits").json()) == 2


def test_fact_recycle_bin_lists_recycled_fact_and_restore(client):
    fact = client.post(
        "/api/facts",
        json={
            "category_code": "skill",
            "title": "Python",
            "fields": {"usage_context": "API"},
        },
    ).json()
    assert client.delete(f"/api/facts/{fact['id']}").json()["status"] == "recycled"

    referenced = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "项目",
            "fields": {"work_summary": "事实"},
        },
    ).json()
    profile = client.post(
        "/api/requirement-profiles", json={"name": "数据工程"}
    ).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [referenced["id"]]}},
    )
    client.post(f"/api/linked-resumes/{linked['id']}/convert")
    assert client.delete(f"/api/facts/{referenced['id']}").json()["status"] == "recycled"

    active = client.get("/api/facts").json()
    recycled = client.get("/api/facts?status=recycled").json()
    assert all(item["id"] != referenced["id"] for item in active)
    assert any(item["id"] == referenced["id"] for item in recycled)
    restored = client.post(f"/api/facts/{referenced['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"


def test_evidence_link_is_reachable_from_fact(client):
    fact = client.post(
        "/api/facts", json={"category_code": "skill", "title": "Python"}
    ).json()
    response = client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "作品链接",
            "url": "https://example.com",
            "note": "验证",
        },
    )
    assert response.status_code == 201
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["title"] == "作品链接"
    audits = client.get(f"/api/evidence/{response.json()['id']}/audits").json()
    assert audits[0]["action"] == "created"


def test_evidence_can_be_archived_and_restored(client):
    fact = client.post(
        "/api/facts", json={"category_code": "skill", "title": "Python"}
    ).json()
    evidence = client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "证书链接",
            "url": "https://example.com/cert",
        },
    ).json()
    assert client.delete(f"/api/evidence/{evidence['id']}").json()["status"] == "archived"
    assert client.get(f"/api/facts/{fact['id']}/evidence").json()[0]["status"] == "archived"
    restored = client.post(f"/api/evidence/{evidence['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
def test_registered_extension_field_round_trips(client, session_factory):
    with session_factory() as db:
        schema = FactSchemaVersion(
            category_code="education",
            version_number=2,
            status="draft",
            note="extension test",
        )
        db.add(schema)
        db.flush()
        db.add(
            FactFieldDefinition(
                category_code="education",
                schema_version_id=schema.id,
                field_key="pronouns",
                label="代称",
                value_type="text",
                requirement_level="optional",
                is_extension=1,
                storage_table="fact_extension_values",
                storage_column="text_value",
                sort_order=200,
            )
        )
        db.commit()
        schema_id = schema.id

    created = client.post(
        "/api/facts",
        json={
            "category_code": "education",
            "schema_version_id": schema_id,
            "title": "扩展字段教育经历",
            "fields": {"school": "测试大学", "pronouns": "they/them"},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["fields"]["pronouns"] == "they/them"
    updated = client.patch(
        f"/api/facts/{created.json()['id']}",
        json={"fields": {"school": "测试大学", "pronouns": "she/her"}},
    )
    assert updated.status_code == 200
    assert updated.json()["fields"]["pronouns"] == "she/her"
