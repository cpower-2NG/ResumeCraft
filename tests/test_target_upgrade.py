from tests.conftest import create_profile, create_resume


def _resume_with_evidence(client):
    fact = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "证据同步项目",
            "fields": {"work_summary": "完成数据采集"},
        },
    ).json()
    evidence = client.post(
        "/api/evidence",
        json={
            "kind": "link",
            "fact_id": fact["id"],
            "title": "项目证明",
            "url": "https://example.com/proof",
        },
    ).json()
    profile = create_profile(client, "证据同步岗位")
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(
        f"/api/linked-resumes/{linked['id']}",
        json={"selection": {"experience": [fact["id"]]}},
    )
    resume_id = client.post(
        f"/api/linked-resumes/{linked['id']}/convert"
    ).json()["resume_id"]
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    experience = next(section for section in content["sections"] if section["id"] == "experience")
    experience["blocks"][0]["evidence_refs"] = [evidence["id"]]
    experience["blocks"][0]["evidence_display"] = "attachment"
    assert client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    ).status_code == 200
    assert client.post(
        f"/api/resumes/{resume_id}/save", json={"change_summary": "引用证据"}
    ).status_code == 200
    return resume_id, evidence


def test_target_resume_payload_has_no_identity_key(client):
    profile, resume_id = create_resume(client)
    assert "identity_key" not in profile
    resume = client.get(f"/api/resumes/{resume_id}").json()
    assert "identity_key" not in resume
    assert resume["content_state"] == "clean"
    assert resume["evidence_sync_state"] == "clean"
    assert resume["baseline_state"] == "current"
    assert resume["template"]["status"] == "available"


def test_template_switch_changes_visual_without_new_version(client):
    _, resume_id = create_resume(client)
    before = client.get(f"/api/resumes/{resume_id}/versions").json()
    templates = client.get("/api/templates").json()
    current = client.get(f"/api/resumes/{resume_id}").json()["template"]["id"]
    replacement = next(item for item in templates if item["id"] != current)

    response = client.patch(
        f"/api/resumes/{resume_id}/template",
        json={"template_id": replacement["id"]},
    )
    assert response.status_code == 200
    assert response.json()["content_state"] == "clean"
    after = client.get(f"/api/resumes/{resume_id}/versions").json()
    assert after == before
    assert after[0]["content_hash"] == before[0]["content_hash"]
    assert (
        client.get(f"/api/resumes/{resume_id}").json()["template"]["id"]
        == replacement["id"]
    )


def test_evidence_change_creates_evidence_sync_without_taking_dirty_body(client):
    resume_id, evidence = _resume_with_evidence(client)
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    experience = next(
        section for section in content["sections"] if section["id"] == "experience"
    )
    experience["blocks"][0]["content"] = "尚未保存的正文"
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})

    changed = client.patch(
        f"/api/evidence/{evidence['id']}",
        json={"title": "更新后的项目证明"},
    )
    assert changed.status_code == 200
    resume = client.get(f"/api/resumes/{resume_id}").json()
    versions = client.get(f"/api/resumes/{resume_id}/versions").json()
    assert versions[0]["reason"] == "evidence_sync"
    assert versions[0]["version_number"] == 3
    target = next(
        section
        for section in versions[0]["content"]["sections"]
        if section["id"] == "experience"
    )
    assert target["blocks"][0]["content"] != "尚未保存的正文"
    assert resume["content_state"] == "dirty"
    assert resume["evidence_sync_state"] == "pending"
    assert next(
        section
        for section in resume["working_copy"]["content"]["sections"]
        if section["id"] == "experience"
    )["blocks"][0]["content"] == "尚未保存的正文"


def test_export_appends_events_and_records_current_template(client):
    _, resume_id = create_resume(client)
    blocked = client.post(f"/api/resumes/{resume_id}/versions/1/export")
    assert blocked.status_code == 409
    first = client.post(f"/api/resumes/{resume_id}/versions/1/export?force=true")
    second = client.post(f"/api/resumes/{resume_id}/versions/1/export?force=true")
    assert first.status_code == 200 and second.status_code == 200
    events = client.get("/api/export-events").json()
    matching = [item for item in events if item["resume_id"] == resume_id]
    assert len(matching) == 2
    assert matching[0]["content_hash"] == matching[1]["content_hash"]
    assert matching[0]["template_id"] == client.get(
        f"/api/resumes/{resume_id}"
    ).json()["template"]["id"]


def test_profile_copy_is_audited_and_never_copies_opportunities(client):
    profile, resume_id = create_resume(client)
    client.post(
        "/api/opportunities",
        json={
            "requirement_profile_id": profile["id"],
            "company": "甲公司",
            "title": "原岗位",
        },
    )
    copied = client.patch(
        f"/api/resumes/{resume_id}/profile",
        json={"role_direction": "机器人工程", "core_requirements": ["ROS2"]},
    ).json()["profile"]
    assert copied["id"] != profile["id"]
    assert client.get(
        f"/api/opportunities?profile_id={copied['id']}"
    ).json() == []
    original_audit = client.get(
        f"/api/requirement-profiles/{profile['id']}/audits"
    ).json()
    clone_audit = client.get(
        f"/api/requirement-profiles/{copied['id']}/audits"
    ).json()
    assert original_audit[0]["action"] == "cloned"
    assert clone_audit[0]["action"] == "created"


def test_fact_delete_is_recoverable_and_purge_is_confirmed(client):
    fact = client.post(
        "/api/facts", json={"category_code": "skill", "title": "临时技能"}
    ).json()
    assert client.delete(f"/api/facts/{fact['id']}").json()["status"] == "recycled"
    assert client.delete(f"/api/facts/{fact['id']}/purge").status_code == 422
    purged = client.delete(f"/api/facts/{fact['id']}/purge?confirm=true")
    assert purged.status_code == 200
    assert purged.json()["status"] == "purged"
    stored = client.get(f"/api/facts/{fact['id']}").json()
    assert stored["status"] == "purged"
    assert stored["title"] == "[purged]"
