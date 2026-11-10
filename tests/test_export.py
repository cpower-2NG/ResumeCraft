def test_export_is_fixed_a4_and_paginates_long_formal_content(client):
    fact = client.post(
        "/api/facts",
        json={
            "category_code": "experience",
            "title": "长项目",
            "fields": {"work_summary": "事实"},
        },
    ).json()
    profile = client.post("/api/requirement-profiles", json={"name": "工程师"}).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    client.patch(f"/api/linked-resumes/{linked['id']}", json={"selection": {"experience": [fact["id"]]}})
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    content["sections"][4]["blocks"][0]["content"] = "长内容。" * 800
    client.patch(f"/api/resumes/{resume_id}/working-copy", json={"content": content})
    client.post(f"/api/resumes/{resume_id}/save", json={"change_summary": "导出验证"})
    export = client.post(f"/api/resumes/{resume_id}/versions/2/export?force=true")
    assert export.status_code == 200
    assert "@page" in export.text and "size: A4" in export.text and "width:210mm" in export.text
    assert export.text.count('class="page"') >= 2


def test_export_with_link_block_renders_anchor(client):
    profile = client.post("/api/requirement-profiles", json={"name": "作品集岗位"}).json()
    linked = client.post(
        "/api/linked-resumes", json={"profile_id": profile["id"]}
    ).json()
    resume_id = client.post(f"/api/linked-resumes/{linked['id']}/convert").json()["resume_id"]
    content = client.get(f"/api/resumes/{resume_id}").json()["working_copy"]["content"]
    links = next(section for section in content["sections"] if section["id"] == "links")
    links["blocks"] = [
        {
            "id": "manual-portfolio",
            "type": "manual",
            "title": "个人作品集",
            "content": "[example.com/portfolio](https://example.com/portfolio)",
            "fields": {},
            "field_labels": {},
            "display_fields": [],
            "source_refs": [],
            "origin": "manual",
        }
    ]
    assert client.patch(
        f"/api/resumes/{resume_id}/working-copy", json={"content": content}
    ).status_code == 200
    saved = client.post(
        f"/api/resumes/{resume_id}/save", json={"change_summary": "添加作品集链接"}
    )
    assert saved.status_code == 200
    export = client.post(f"/api/resumes/{resume_id}/versions/2/export?force=true")
    assert export.status_code == 200, export.text
    assert '<a href="https://example.com/portfolio">' in export.text
    assert export.text.count("链接与作品集") == 1


def test_render_markdown_keeps_line_breaks():
    """正文里的换行必须渲染成 <br>：此前按 “\\n” 分段后又用空串拼接，把用户
    自己分好的行黏成了一行（预览用 <br/> 拼接，两端因此显示不一致）。"""
    from app.services import render_markdown

    html = render_markdown("GPA 3.7/4.5；专业排名 9/153\n具身智能系统概论、ROS 系统与编程")
    assert "GPA 3.7/4.5；专业排名 9/153<br>具身智能系统概论" in html
    # 列表项仍然成组渲染，不额外插入 <br>。
    assert render_markdown("- 第一项\n- 第二项") == "<ul><li>第一项</li><li>第二项</li></ul>"
    # 行尾换行不产生多余的空行。
    assert render_markdown("单行内容\n") == "单行内容<br>"
    assert render_markdown("**加粗**与*斜体*") == "<strong>加粗</strong>与<em>斜体</em>"
