"""Emit layout calibration probes: one export HTML per representative template.

The pagination model is an *estimate* (weights in app/services.py and
web/src/lib/resume.ts) that must match what the browser actually lays out.
When it under-estimates, the export clips text off the bottom of the A4 page.
This script renders a probe with content chosen so every constant in
LAYOUT_METRICS can be measured from the DOM by web/scripts/measure_calib.mjs:

- a long, CJK-only paragraph                          -> units_per_line
- a block with many display fields                     -> meta_units / meta line height
- a second section                                     -> header vs header_first

Probes are written to output/tmp/calib/<template>.html. Run measure_calib.mjs
against that directory to read the geometry, then show_calib.mjs to print values
that can be copied into LAYOUT_METRICS.

校准探针的正文是**纯中文**、每行容量按**字宽单位**（全角 2、半角 1）统计，见
`app/services.py` 的 `text_units`。这两点都不能改回去：用拉丁字母较多的文本标定出的
每行容量对纯中文正文偏乐观，估算会少算近三成行数、把正文顶出 A4 底边；只按纯中文
字符数标定又会把带拉丁词的真实简历估高一截。
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services import render_resume_html  # noqa: E402
from app.templates import BUILTIN_TEMPLATES  # noqa: E402

OUT = Path("output/tmp/calib")

# One template per layout, plus the serif variants that exist in the library.
PROBES = ["classic", "onyx", "ink", "forest", "azure", "regent", "atlas", "flint", "quill", "lumen", "slate-rail"]

# Realistic resume prose: a Chinese resume body is CJK-dominant, and a CJK glyph is
# roughly twice as wide as a Latin one at the same font size. Probing with a
# Latin-heavy sentence measured ~69 units/line where the same box only fits ~53 CJK
# glyphs (=106 units), so the estimator under-charged every line and the packing
# overflowed the page bottom (long-azure/long-regent clipped). The probe text stays
# CJK-only and measures its capacity in glyph-width units, which is the safe and
# accurate bound for any real mix.
SENTENCE = (
    "负责中台服务的设计与落地，沉淀可复用组件与规范，推动跨团队协作和交付质量提升，"
    "主导接口性能优化，把响应时间从八百毫秒降到一百二十毫秒，节省约一半机器成本。"
)
BODY = SENTENCE * 45  # ~3300 chars, enough to measure a full-width fragment


def probe_content() -> dict:
    """Two experience blocks: a long meta-rich one and a short follower.

    The follower keeps the first block from being :last-of-type (several layouts
    trim the last block's margin, which would skew the base measurement).
    The long block's meta carries enough fields to wrap onto several rows: one
    row of fields only lower-bounds the row capacity, and under-measuring it
    makes the packer charge an extra meta line for every long field row.
    """
    long_block = {
        "id": "probe-long", "type": "fact", "title": "电商中台重构与数据管道建设",
        "content": BODY,
        "fields": {"period": "2024.03 – 2025.06", "organization": "某科技有限公司", "role": "后端负责人",
                   "team_size": "12 人", "tools": "Python, Kafka, MySQL, Docker, Kubernetes",
                   "duty_a": "跨团队协作与交付质量提升，沉淀可复用组件与工程规范",
                   "duty_b": "负责线上值班与故障复盘，输出改进项并跟踪到落地",
                   "duty_c": "参与招聘与面试，负责新人培养、代码评审与技术分享"},
        "field_labels": {},
        "display_fields": ["period", "organization", "role", "team_size", "tools", "duty_a", "duty_b", "duty_c"],
        "source_refs": [], "origin": "fact",
    }
    short_block = {
        "id": "probe-short", "type": "fact", "title": "性能优化专项",
        "content": "接口 P99 从 800ms 降至 120ms。",
        "fields": {"period": "2022.05 – 2022.12", "organization": "某科技有限公司", "role": "核心开发"},
        "field_labels": {}, "display_fields": ["period", "organization", "role"],
        "source_refs": [], "origin": "fact",
    }
    basics = {
        "id": "probe-basics", "type": "fact", "title": "陈晓",
        "content": "四年服务端经验，主导过中台重构与数据管道建设。",
        "fields": {"phone": "13800000000", "email": "chen@example.com", "city": "杭州",
                   "desired_city": "杭州", "status": "应届毕业生", "graduation": "2026年6月"},
        "field_labels": {},
        "display_fields": ["phone", "email", "city", "desired_city", "status", "graduation"],
        "source_refs": [], "origin": "fact",
    }
    def empty(sid, title):
        return {"id": sid, "type": sid, "title": title, "visibility": True, "blocks": []}

    def block(bid, title, content, fields, display=None):
        return {"id": bid, "type": "fact", "title": title, "content": content, "fields": fields,
                "field_labels": {}, "display_fields": display or list(fields), "source_refs": [], "origin": "fact"}

    # 技能/成果是侧栏布局的侧栏内容，必须有真实正文与字段才能量到侧栏列的口径；
    # 正文长度要盖过 measure_calib.mjs 挑段落用的 >200 字门槛。
    skills = {"id": "skills", "type": "skills", "title": "技能", "visibility": True, "blocks": [
        block("probe-skill-1", "工程工具链", SENTENCE * 4,
              {"skill_category": "工程工具", "proficiency": "熟练"}, ["skill_category", "proficiency"]),
        block("probe-skill-2", "方法论", SENTENCE * 2,
              {"skill_category": "方法论", "proficiency": "掌握"}, ["skill_category", "proficiency"]),
    ]}
    awards = {"id": "awards", "type": "awards", "title": "成果", "visibility": True, "blocks": [
        block("probe-award", "校级优秀毕业设计", SENTENCE,
              {"period": "2026.06", "issuer": "华东理工大学", "result": "评级 A"}),
    ]}
    links = {"id": "links", "type": "links", "title": "链接与作品集", "visibility": True, "blocks": [
        block("probe-link", "个人作品集", "", {"link_type": "作品集", "url": "https://example.com/work", "label": "example.com/work"}),
    ]}
    education = {"id": "education", "type": "education", "title": "教育经历", "visibility": True, "blocks": [
        block("probe-edu", "华东理工大学 · 自动化", "主修控制理论与机器人学。",
              {"period": "2022.09 – 2026.06", "degree": "本科", "gpa": "3.7/4.0", "ranking": "9/153"}),
    ]}
    return {"sections": [
        {"id": "basics", "type": "basics", "title": "基本信息", "visibility": True, "blocks": [basics]},
        empty("target", "求职目标"),
        empty("profile", "个人简介"),
        {"id": "experience", "type": "experience", "title": "项目与实践", "visibility": True,
         "blocks": [long_block, short_block]},
        education, skills, awards, links,
    ]}


OUT.mkdir(parents=True, exist_ok=True)
content = probe_content()
for slug in PROBES:
    html = render_resume_html(content, f"校准-{slug}", 1, slug)
    (OUT / f"{slug}.html").write_text(html, encoding="utf-8")
    descriptor = BUILTIN_TEMPLATES[slug]
    print(f"{slug:10} layout={descriptor['layout']:8} serif={bool(descriptor.get('serif'))}")
io.open(OUT / "_index.txt", "w", encoding="utf-8").write("\n".join(PROBES))
print("wrote", len(PROBES), "probes to", OUT)
