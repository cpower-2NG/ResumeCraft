"""格式升级回归：字段兜底回收、导出体检、组稿策展、意向横带、成果表格、技能分组、紧凑档。

这些能力共同回应一次版式评审（对照三份 AI 生成的参考简历）发现的四类问题：
条目时间丢失、联系方式缺失无提示、meta 行噪音、短内容被挤到近乎空白的第二页。
夹具 real_flattened_resume.json 是真实工作区里字段被压平的正式简历——历史迁移或
外部写入都可能产出这种块，渲染器完全依赖 fields，没有兜底时时间/单位/角色全部消失。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import (
    PAGE_BUDGET_PX,
    awards_table_rows,
    bold_metrics,
    curated_education_plain,
    curated_experience_plain,
    hydrate_block,
    hydrate_content,
    lint_resume,
    render_resume_html,
    skill_groups,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "real_flattened_resume.json"
FLATTENED = json.loads(FIXTURE.read_text(encoding="utf-8"))


def sections_of(content: dict) -> dict:
    return {item["id"]: item for item in content["sections"]}


# ---------------------------------------------------------------- 字段兜底回收

def test_hydrate_extracts_meta_tail_from_flattened_experience():
    flat = {"id": "f", "title": "某项目", "content": "使用 VR 头显采集数据，分析模型瓶颈。\n工业任务复杂；模型存在过拟合。 · 竞赛 · 实验室小组", "source_refs": [3], "origin": "fact"}
    hydrated = hydrate_block(flat, "experience")
    assert hydrated["fields"]["extra_1"] == "竞赛"
    assert hydrated["fields"]["extra_2"] == "实验室小组"
    # 尾巴从正文里剥离，正文保持完整句子。
    assert "实验室小组" not in hydrated["content"]
    assert hydrated["content"].startswith("使用 VR 头显采集数据")


def test_hydrate_recovers_award_whole_line():
    flat = {"id": "a", "title": "越疆 X-Trainer 竞赛", "content": "越疆 · 2026.06 · 省三等奖", "source_refs": [19], "origin": "fact"}
    hydrated = hydrate_block(flat, "awards")
    assert hydrated["fields"] == {"period": "2026.06", "issuer": "越疆", "result": "省三等奖"}
    assert hydrated["content"] == ""


def test_hydrate_ignores_prose_with_mid_dots():
    """正文里的" · "不是字段尾巴：不跟在完整句子后、也不含时间形状的段，一律不动。"""
    prose = {"id": "n", "title": "t", "content": "负责 A · B · C 三条产品线", "source_refs": [], "origin": "fact"}
    assert hydrate_block(prose, "experience") is prose
    availability = {"id": "b", "title": "许榕鑫", "content": "每周可实习 5 天；最长可连续实习时间不限 · 深圳 · 深圳", "source_refs": [1], "origin": "fact"}
    assert hydrate_block(availability, "basics") is availability


def test_hydrate_never_touches_structured_blocks():
    block = {"id": "s", "title": "t", "content": "正文。 · 竞赛 · 实验室小组", "fields": {"period": "2026.05"}, "display_fields": ["period"], "source_refs": [], "origin": "fact"}
    assert hydrate_block(block, "experience") is block


def test_flattened_fixture_hydrates_and_lints():
    """真实夹具：回收后经历块拿到 meta 值、成果块拿到时间/颁发方/结果。"""
    hydrated = hydrate_content(FLATTENED)
    sections = sections_of(hydrated)
    experience = sections["experience"]["blocks"][0]
    assert set(experience["fields"]) >= {"extra_1", "extra_2"}
    award = sections["awards"]["blocks"][0]
    assert award["fields"]["period"] == "2026.06"
    assert award["fields"]["result"] == "省三等奖"
    issues = lint_resume(FLATTENED)
    messages = " ".join(issue["message"] for issue in issues)
    assert "缺少电话号码" in messages and "缺少邮箱地址" in messages
    assert "没有时间" in messages  # 压平数据里教育/经历的时间确实不存在，必须亮出来


# ---------------------------------------------------------------- 导出体检

def test_lint_flags_missing_contact_garbage_and_zero_info():
    content = {"sections": [
        {"id": "basics", "title": "基本信息", "visibility": True, "blocks": [{"id": "b", "title": "许榕鑫", "content": "", "fields": {"city": "深圳"}, "display_fields": ["city"], "source_refs": [1], "origin": "fact"}]},
        {"id": "experience", "title": "项目与实践", "visibility": True, "blocks": [{"id": "e", "title": "某项目", "content": "- 做了具体的事。\n- 完成课程项目。", "fields": {"period": "2025.12"}, "display_fields": ["period"], "source_refs": [2], "origin": "fact"}]},
        {"id": "awards", "title": "成果", "visibility": True, "blocks": [{"id": "a", "title": "某奖", "content": "阿斯顿发斯蒂芬", "fields": {"period": "2026.06", "result": "省三等奖"}, "display_fields": ["period", "result"], "source_refs": [19], "origin": "fact"}]},
    ]}
    issues = lint_resume(content)
    levels = {(issue["section_id"], issue["level"]) for issue in issues}
    assert ("basics", "error") in levels
    by_section = {issue["section_id"]: issue["message"] for issue in issues}
    assert "阿斯顿发斯蒂芬" in by_section["awards"]
    assert "完成课程项目" in by_section["experience"]
    # 体检结果直接出现在导出 HTML 的屏幕告警条里，打印时隐藏。
    html = render_resume_html(content, "体检", 1, "ink", lint_issues=issues)
    assert "export-lint" in html and "缺少电话号码" in html


def test_render_hydration_surfaces_meta_and_awards_table():
    """导出渲染前先做字段回收：压平的经历排出 meta 值，成果排出三列表格。"""
    html = render_resume_html(FLATTENED, "许榕鑫", 1, "ink")
    assert '<span class="meta">实验室小组</span>' in html
    assert 'class="awards-table"' in html
    assert "省三等奖（越疆）" in html


# ---------------------------------------------------------------- 组稿策展

def test_curated_experience_is_bulleted_with_bold_metrics():
    details = {
        "context": "围绕分拣任务完成数据采集与训练。",
        "work": "使用 VR 头显采集机械臂运动数据。",
        "solution": "用视频抽帧处理训练数据，并筛选更稳健的策略。",
        "outcome": "分拣任务完成率约 60% - 70%，获省三等奖。",
        "challenge": "工业任务复杂，模型存在过拟合。",
    }
    plain = curated_experience_plain(details)
    lines = plain.split("\n")
    # 背景被"具体工作"取代、挑战不上纸面；三条 bullet、结果行量化指标加粗。
    assert lines[0].startswith("- 使用 VR 头显")
    assert all(line.startswith("- ") for line in lines)
    assert len(lines) == 3
    assert "**60%**" in lines[-1] and "**省三等奖**" in lines[-1]
    assert "工业任务复杂" not in plain


def test_bold_metrics_skips_authored_bold():
    assert bold_metrics("完成 **60%** 的分拣") == "完成 **60%** 的分拣"


def test_curated_education_prefixes_courses():
    plain = curated_education_plain({"achievement": "GPA 3.7/4.5", "courses": "数据结构、操作系统"})
    assert plain == "GPA 3.7/4.5\n核心课程：数据结构、操作系统"


def test_skill_groups_require_category_and_merge_items():
    blocks = [
        {"title": "C/C++", "content": "算法竞赛", "fields": {"skill_category": "编程语言", "proficiency": "熟练"}},
        {"title": "Python", "content": "", "fields": {"skill_category": "编程语言"}},
        {"title": "ROS2", "content": "仿真项目", "fields": {"skill_category": "机器人开发"}},
    ]
    assert skill_groups(blocks) == [("编程语言", "C/C++（熟练，算法竞赛）、Python"), ("机器人开发", "ROS2（仿真项目）")]
    missing = blocks + [{"title": "无分类", "content": "", "fields": {}}]
    assert skill_groups(missing) == []


def test_awards_table_rows_require_period_and_result():
    ok = [{"title": "竞赛", "fields": {"period": "2026.06", "issuer": "越疆", "result": "省三等奖"}}]
    assert awards_table_rows(ok) == [("2026.06", "竞赛", "省三等奖（越疆）")]
    assert awards_table_rows([{"title": "竞赛", "fields": {"period": "2026.06"}}]) == []


# ---------------------------------------------------------------- 版式结构

def test_intent_band_replaces_target_section():
    content = json.loads(json.dumps(FLATTENED))
    sections = sections_of(content)
    sections["target"]["blocks"] = [{"id": "t", "title": "求职目标", "content": "机器人数据采集员", "fields": {}, "display_fields": [], "source_refs": [], "origin": "user"}]
    html = render_resume_html(content, "横带", 1, "ink")
    assert 'class="intent-band"' in html and "求职意向" in html and "机器人数据采集员" in html
    # 不再出现"求职目标"独立栏目（横带标签是"求职意向"）。
    assert "<h2>求职目标</h2>" not in html


def test_intent_band_suppresses_placeholder_strategy():
    content = {"sections": [
        {"id": "target", "title": "求职目标", "visibility": True, "blocks": [{"id": "t", "title": "后端开发", "content": "请填写与目标岗位匹配的简历强调方向。", "fields": {}, "display_fields": [], "source_refs": [], "origin": "profile"}]},
        {"id": "experience", "title": "项目与实践", "visibility": True, "blocks": []},
    ]}
    html = render_resume_html(content, "占位", 1, "ink")
    assert "请填写与目标岗位匹配的简历强调方向" not in html


def test_skills_render_grouped_lines():
    content = {"sections": [
        {"id": "skills", "title": "技能", "visibility": True, "blocks": [
            {"id": "s1", "title": "C/C++", "content": "算法竞赛", "fields": {"skill_category": "编程语言", "proficiency": "熟练"}, "display_fields": ["skill_category", "proficiency"], "source_refs": [1], "origin": "fact"},
        ]},
    ]}
    html = render_resume_html(content, "技能", 1, "ink")
    assert "<strong>编程语言</strong>：C/C++（熟练，算法竞赛）" in html


def test_rail_layout_uses_label_rail():
    html = render_resume_html(FLATTENED, "标签栏", 1, "slate-rail")
    assert "page-rail" in html
    assert "rail-head" in html
    # 压平数据下成果回收成表格，仍以 rail 骨架呈现。
    assert 'class="awards-table"' in html


# ---------------------------------------------------------------- 紧凑档

def _line(count: int) -> str:
    return "中文字符正文一行五十二个字" * 7 + "。"


def test_content_slightly_over_one_page_compacts_into_one():
    """估算总高在一页的 1.0-1.08 倍之间时，整页换紧凑刻度收进一页（不再出半空第二页）。

    个人简介 1 条（单行）+ 项目与实践 13 条（每条两行，每条权重 34+2×17 = 68）：
    普通刻度下首页装 12 条（65 + 48 + 12×68 = 929 ≤ 980），第 13 条连同跨页的
    （续）标题落到第二页，估算总高 = 1045，落在 (980, 980×1.08] 触发区间——
    紧凑档收进一页。每条内容远短于切片上限，估算完全确定。
    """
    two_lines = ("字" * 51 + "。\n") * 2
    content = {"sections": [
        {"id": "profile", "title": "个人简介", "visibility": True, "blocks": [
            {"id": "p", "title": "个人简介", "content": "字" * 51 + "。", "fields": {}, "display_fields": [], "source_refs": [], "origin": "fact"}]},
        {"id": "experience", "title": "项目与实践", "visibility": True, "blocks": [
            {"id": f"e{i}", "title": f"项目{ i}", "content": two_lines, "fields": {"period": "2024-2025"}, "display_fields": ["period"], "source_refs": [1], "origin": "fact"}
            for i in range(13)
        ]},
    ]}
    html = render_resume_html(content, "紧凑", 1, "ink")
    assert html.count('class="page') == 1, "略超一页的内容应整页紧凑收进一页"
    assert "page compact" in html


def test_content_far_over_one_page_stays_multipage():
    line = "字" * 52 + "。"
    content = {"sections": [
        {"id": "experience", "title": "项目与实践", "visibility": True, "blocks": [
            {"id": "e", "title": "长项目", "content": "\n".join([line] * 120), "fields": {"period": "2024-2025"}, "display_fields": ["period"], "source_refs": [1], "origin": "fact"}]},
    ]}
    html = render_resume_html(content, "多页", 1, "ink")
    assert html.count('class="page') >= 2
    assert "page compact" not in html


def test_flattened_real_resume_fits_one_page():
    """真实压平简历此前排出"半空第二页"；回收 + 紧凑档后必须单页。"""
    html = render_resume_html(FLATTENED, "许榕鑫", 1, "ink")
    assert html.count('class="page') == 1
