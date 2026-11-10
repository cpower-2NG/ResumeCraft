"""Add typed fact details while retaining the legacy content snapshot."""

import json

import sqlalchemy as sa
from alembic import op


revision = "0003_structured_fact_details"
down_revision = "0002_evidence_recycle_bin"
branch_labels = None
depends_on = None


def _fields(table, fields):
    return [
        sa.Column("fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), primary_key=True),
        *[sa.Column(name, sa.Text(), nullable=False, server_default="") for name in fields],
    ]


def upgrade():
    if "fact_categories" in sa.inspect(op.get_bind()).get_table_names():
        return
    if "personal_fact_details" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("personal_fact_details", *_fields("personal_fact_details", [
        "name", "phone", "email", "city", "desired_city", "birth_date", "age", "hometown",
        "status", "graduation", "availability", "bio",
    ]))
    op.create_table("education_fact_details", *_fields("education_fact_details", [
        "school", "major", "degree", "start_date", "end_date", "period", "gpa", "ranking",
        "achievement", "courses",
    ]))
    op.create_table("experience_fact_details", *_fields("experience_fact_details", [
        "kind", "period", "organization", "role", "team_size", "context", "work", "tools",
        "outcome", "challenge", "solution", "public_note",
    ]))
    op.create_table("skill_fact_details", *_fields("skill_fact_details", ["skill_category", "proficiency", "context"]))
    op.create_table("achievement_fact_details", *_fields("achievement_fact_details", ["period", "issuer", "result", "note"]))
    op.create_table("link_fact_details", *_fields("link_fact_details", ["link_type", "url", "label", "note"]))
    op.create_table(
        "fact_custom_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fact_id", sa.Integer(), sa.ForeignKey("fact_records.id"), nullable=False, index=True),
        sa.Column("field_key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("label", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("displayable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("fact_id", "field_key", name="uq_fact_custom_field"),
    )

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, category, content FROM fact_records")).mappings().all()
    details = {
        "basics": ("personal_fact_details", ["name", "phone", "email", "city", "desired_city", "birth_date", "age", "hometown", "status", "graduation", "availability", "bio"]),
        "education": ("education_fact_details", ["school", "major", "degree", "start_date", "end_date", "period", "gpa", "ranking", "achievement", "courses"]),
        "experience": ("experience_fact_details", ["kind", "period", "organization", "role", "team_size", "context", "work", "tools", "outcome", "challenge", "solution", "public_note"]),
        "skills": ("skill_fact_details", ["skill_category", "proficiency", "context"]),
        "awards": ("achievement_fact_details", ["period", "issuer", "result", "note"]),
        "links": ("link_fact_details", ["link_type", "url", "label", "note"]),
    }
    for row in rows:
        try:
            content = json.loads(row["content"] or "{}")
        except (TypeError, json.JSONDecodeError):
            content = {}
        if row["category"] not in details:
            continue
        table, fields = details[row["category"]]
        values = {"fact_id": row["id"]}
        for field in fields:
            source = "category" if row["category"] == "skills" and field == "skill_category" else field
            if source in content and content[source] not in (None, ""):
                values[field] = str(content[source])
        columns = ", ".join(values)
        placeholders = ", ".join(f":{key}" for key in values)
        bind.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"), values)

        known = {"summary", *fields}
        if row["category"] == "skills":
            known.add("category")
        for index, (key, value) in enumerate(content.items()):
            if key not in known and value not in (None, "", [], {}):
                bind.execute(sa.text(
                    "INSERT INTO fact_custom_fields (fact_id, field_key, value, label, displayable, sort_order) "
                    "VALUES (:fact_id, :field_key, :value, :label, 1, :sort_order)"
                ), {"fact_id": row["id"], "field_key": f"legacy.{key}", "value": str(value), "label": key, "sort_order": index})


def downgrade():
    op.drop_table("fact_custom_fields")
    op.drop_table("link_fact_details")
    op.drop_table("achievement_fact_details")
    op.drop_table("skill_fact_details")
    op.drop_table("experience_fact_details")
    op.drop_table("education_fact_details")
    op.drop_table("personal_fact_details")
