"""Generate export HTML for dense sample contents across every builtin template.

Samples:
- real:   resume 1's current working copy, rebuilt through the app's own legacy
          field repair, so it carries real structured fields (period / meta).
- long:   compat-test style dense sample with a ~2700-char experience body.
- fields: many blocks with lots of display fields (field-heavy).

Output: output/tmp/<sample>-<slug>.html
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, ".")
from sqlalchemy import select

from app.services import json_value, render_resume_html
from app.templates import BUILTIN_TEMPLATES
from app.workbench_database import SessionLocal
from app.workbench_models import ResumeIdentity, ResumeWorkingCopy
from repair_working_copies import repair_content

OUT = Path("output/tmp")
OUT.mkdir(parents=True, exist_ok=True)


def _version_snapshot(identity_id: int = 1) -> dict:
    """回退路径：没有可用工作副本时，退回最新版本快照。"""
    conn = sqlite3.connect("data/resume_workbench.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "select content from resume_versions where resume_identity_id=? order by version_number desc limit 1",
        (identity_id,),
    ).fetchone()
    return json.loads(row["content"]) if row else {"sections": []}


def real_content(identity_id: int = 1) -> dict:
    """真实简历样本：取工作副本内容，并按 app 的修复规则在内存里补回结构化字段。

    这里以前读的是 resume_versions 的快照，而那份内容是早期压平过的（fields 全空）：
    于是 real-* 样本既没有时间列也没有 meta 行，线式/时间轴版式的左侧时间栏在整行
    样本里始终是空的。工作副本才是简历当前的样子；修复只在内存里做，不写数据库。
    """
    with SessionLocal() as db:
        identity = db.get(ResumeIdentity, identity_id) or db.scalars(
            select(ResumeIdentity).order_by(ResumeIdentity.id)
        ).first()
        copy = db.scalar(select(ResumeWorkingCopy).where(
            ResumeWorkingCopy.resume_identity_id == identity.id)) if identity else None
        content = json_value(copy.content, {}) if copy else {}
        if not content.get("sections"):
            return _version_snapshot(identity_id)
        repair_content(db, identity, content)
        return content


def base_block(section_id, title, fields, content, display=None):
    return {"id": f"fact-{title}", "type": "fact", "title": title, "content": content,
            "fields": fields, "field_labels": {}, "display_fields": display or [k for k in fields],
            "source_refs": [], "origin": "fact"}


def dense_content(long_factor: int, field_heavy: bool):
    experience_body = "负责中台服务的设计与落地，沉淀可复用组件与规范，推动跨团队协作和交付质量提升。" * long_factor
    exp_fields = {"period": "2024.03 – 2025.06", "organization": "某科技公司", "role": "后端负责人", "team_size": "12 人", "tools": "Python, Kafka, MySQL, Docker"}
    blocks_exp = [base_block("experience", "电商中台重构", exp_fields, experience_body)]
    if field_heavy:
        blocks_exp.append(base_block("experience", "数据管道建设", {**exp_fields, "period": "2023.01 – 2024.02", "role": "架构师"}, "梳理 14 条核心数据链路，建设血缘与质量监控。"))
        blocks_exp.append(base_block("experience", "性能优化专项", {"period": "2022.05 – 2022.12", "organization": "某科技公司", "role": "核心开发"}, "接口 P99 从 800ms 降至 120ms，节省一半机器成本。"))
    return {"sections": [
        {"id": "basics", "title": "基本信息", "visibility": True, "blocks": [base_block("basics", "陈晓", {"phone": "13800000000", "email": "chen@example.com", "city": "杭州", "desired_city": "杭州", "status": "应届毕业生", "graduation": "2026年6月", "availability": "每周实习 5 天，可连续实习 6 个月"}, "", ["phone", "email", "city", "desired_city", "status", "graduation", "availability"])]},
        {"id": "target", "title": "求职目标", "visibility": True, "blocks": [base_block("target", "后端开发工程师", {"role_direction": "服务端 · 数据方向", "core_requirements": "分布式、高并发、数据管道"}, "强调工程落地与数据链路治理经验。", ["role_direction"])]},
        {"id": "profile", "title": "个人简介", "visibility": True, "blocks": [base_block("profile", "个人简介", {}, "四年服务端经验，主导过中台重构与数据管道建设，关注稳定性与可维护性。")]},
        {"id": "experience", "title": "项目与实践", "visibility": True, "blocks": blocks_exp},
        {"id": "education", "title": "教育经历", "visibility": True, "blocks": [base_block("education", "华东理工大学 · 自动化", {"period": "2022.09 – 2026.06", "degree": "本科", "gpa": "3.7/4.0", "ranking": "9/153"}, "主修控制理论与机器人学。")]},
        {"id": "skills", "title": "技能", "visibility": True, "blocks": [base_block("skills", "工程工具链", {"skill_category": "工程工具", "proficiency": "熟练"}, "Python、Kafka、MySQL、Docker、K8s。"), base_block("skills", "方法论", {"skill_category": "方法论", "proficiency": "熟练"}, "代码评审、SRE 实践、容量规划。")]},
        {"id": "awards", "title": "成果", "visibility": True, "blocks": [base_block("awards", "校级优秀毕业设计", {"period": "2026.06", "issuer": "华东理工大学", "result": "评级 A"}, "")]},
        {"id": "links", "title": "链接与作品集", "visibility": True, "blocks": [base_block("links", "个人作品集", {"link_type": "作品集", "url": "https://example.com/work", "label": "example.com/work"}, "")]},
    ]}


samples = {
    "real": real_content(),
    "long": dense_content(long_factor=30, field_heavy=False),
    "fields": dense_content(long_factor=4, field_heavy=True),
}

for name, content in samples.items():
    for slug in BUILTIN_TEMPLATES:
        html = render_resume_html(content, f"样本-{name}", 1, slug)
        (OUT / f"{name}-{slug}.html").write_text(html, encoding="utf-8")
print("generated", len(samples) * len(BUILTIN_TEMPLATES), "files in", OUT)
