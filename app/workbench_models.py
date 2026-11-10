from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .workbench_database import WorkbenchBase


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(WorkbenchBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Workspace(WorkbenchBase):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FactCategory(WorkbenchBase):
    __tablename__ = "fact_categories"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")


class FactSchemaVersion(WorkbenchBase):
    __tablename__ = "fact_schema_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_code: Mapped[str] = mapped_column(ForeignKey("fact_categories.code"))
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="published")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("category_code", "version_number", name="uq_fact_schema_version"),
        Index(
            "uq_fact_schema_current_published",
            "category_code",
            unique=True,
            sqlite_where=text("status = 'published'"),
        ),
    )


class FactFieldDefinition(WorkbenchBase):
    __tablename__ = "fact_field_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_code: Mapped[str] = mapped_column()
    schema_version_id: Mapped[int] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(160))
    value_type: Mapped[str] = mapped_column(String(30))
    requirement_level: Mapped[str] = mapped_column(String(30), default="optional")
    is_extension: Mapped[int] = mapped_column(Integer, default=0)
    storage_table: Mapped[str] = mapped_column(String(100))
    storage_column: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint(
            "schema_version_id", "field_key", name="uq_fact_field_definition"
        ),
    )


class FactRecord(WorkbenchBase):
    __tablename__ = "fact_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    category_code: Mapped[str] = mapped_column(ForeignKey("fact_categories.code"), index=True)
    schema_version_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(250))
    business_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recycled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_fact_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "id",
            "category_code",
            name="uq_fact_workspace_id_category",
        ),
        Index(
            "uq_fact_business_key_live",
            "workspace_id",
            "category_code",
            "business_key",
            unique=True,
            sqlite_where=text(
                "business_key IS NOT NULL AND status IN ('active', 'archived', 'recycled')"
            ),
        ),
        Index(
            "uq_one_live_basics_per_workspace",
            "workspace_id",
            unique=True,
            sqlite_where=text(
                "category_code = 'basics' AND status IN ('active', 'archived', 'recycled')"
            ),
        ),
    )


class FactBasicsDetail(WorkbenchBase):
    __tablename__ = "fact_basics_details"

    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column(default="basics")
    name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    desired_city: Mapped[str] = mapped_column(String(120), default="")
    birth_date: Mapped[str] = mapped_column(String(30), default="")
    age_text: Mapped[str] = mapped_column(String(30), default="")
    hometown: Mapped[str] = mapped_column(String(120), default="")
    identity_status: Mapped[str] = mapped_column(String(120), default="")
    graduation_date: Mapped[str] = mapped_column(String(30), default="")
    availability: Mapped[str] = mapped_column(Text, default="")
    bio: Mapped[str] = mapped_column(Text, default="")


class FactEducationDetail(WorkbenchBase):
    __tablename__ = "fact_education_details"

    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column(default="education")
    school: Mapped[str] = mapped_column(String(220), default="")
    major: Mapped[str] = mapped_column(String(220), default="")
    degree: Mapped[str] = mapped_column(String(100), default="")
    start_date: Mapped[str] = mapped_column(String(30), default="")
    end_date: Mapped[str] = mapped_column(String(30), default="")
    period_text: Mapped[str] = mapped_column(String(100), default="")
    gpa: Mapped[str] = mapped_column(String(80), default="")
    ranking: Mapped[str] = mapped_column(String(100), default="")
    achievement: Mapped[str] = mapped_column(Text, default="")
    courses: Mapped[str] = mapped_column(Text, default="")


class FactExperienceDetail(WorkbenchBase):
    __tablename__ = "fact_experience_details"

    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column(default="experience")
    experience_kind: Mapped[str] = mapped_column(String(40), default="project")
    period_text: Mapped[str] = mapped_column(String(100), default="")
    start_date: Mapped[str] = mapped_column(String(30), default="")
    end_date: Mapped[str] = mapped_column(String(30), default="")
    organization: Mapped[str] = mapped_column(String(250), default="")
    role: Mapped[str] = mapped_column(String(250), default="")
    team_size: Mapped[str] = mapped_column(String(80), default="")
    context_summary: Mapped[str] = mapped_column(Text, default="")
    work_summary: Mapped[str] = mapped_column(Text, default="")
    tools_summary: Mapped[str] = mapped_column(Text, default="")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    challenge: Mapped[str] = mapped_column(Text, default="")
    solution: Mapped[str] = mapped_column(Text, default="")
    public_note: Mapped[str] = mapped_column(Text, default="")


class SkillGroup(WorkbenchBase):
    __tablename__ = "skill_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(120))
    normalized_name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_skill_group_code"),
        UniqueConstraint("workspace_id", "normalized_name", name="uq_skill_group_name"),
    )


class FactSkillDetail(WorkbenchBase):
    __tablename__ = "fact_skill_details"

    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column(default="skill")
    skill_group_id: Mapped[int] = mapped_column(ForeignKey("skill_groups.id"))
    proficiency: Mapped[str] = mapped_column(String(80), default="")
    usage_context: Mapped[str] = mapped_column(Text, default="")


class FactAchievementDetail(WorkbenchBase):
    __tablename__ = "fact_achievement_details"

    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column(default="achievement")
    achievement_kind: Mapped[str] = mapped_column(String(40), default="honor")
    period_text: Mapped[str] = mapped_column(String(100), default="")
    occurred_on: Mapped[str] = mapped_column(String(30), default="")
    issuer: Mapped[str] = mapped_column(String(220), default="")
    result_text: Mapped[str] = mapped_column(String(500), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    experience_fact_id: Mapped[int | None] = mapped_column(ForeignKey("fact_records.id"), nullable=True)
    parent_category_code: Mapped[str] = mapped_column(default="experience")


class FactExtensionValue(WorkbenchBase):
    __tablename__ = "fact_extension_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    fact_id: Mapped[int] = mapped_column()
    category_code: Mapped[str] = mapped_column()
    schema_version_id: Mapped[int] = mapped_column()
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("fact_field_definitions.id"))
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(nullable=True)
    boolean_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    json_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint("fact_id", "field_definition_id", name="uq_fact_extension"),
    )


class Tag(WorkbenchBase):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    normalized_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    merged_into_tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("workspace_id", "normalized_name", name="uq_tag_name"),
    )


class TagAlias(WorkbenchBase):
    __tablename__ = "tag_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"))
    alias: Mapped[str] = mapped_column(String(120))
    normalized_alias: Mapped[str] = mapped_column(String(120))
    __table_args__ = (
        UniqueConstraint("workspace_id", "normalized_alias", name="uq_tag_alias"),
    )


class FactTag(WorkbenchBase):
    __tablename__ = "fact_tags"

    workspace_id: Mapped[int] = mapped_column(primary_key=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)


class Evidence(WorkbenchBase):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(250))
    url: Mapped[str] = mapped_column(Text, default="")
    storage_key: Mapped[str] = mapped_column(Text, default="")
    filename: Mapped[str] = mapped_column(String(250), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_evidence_workspace_id"),
        Index(
            "uq_evidence_file_checksum",
            "workspace_id",
            "checksum",
            unique=True,
            sqlite_where=text("kind = 'file'"),
        ),
    )


class FactEvidence(WorkbenchBase):
    __tablename__ = "fact_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    relation_note: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("workspace_id", "fact_id", "evidence_id", name="uq_fact_evidence"),
    )


class ProfilePhoto(WorkbenchBase):
    __tablename__ = "profile_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(index=True)
    basics_fact_id: Mapped[int] = mapped_column(index=True)
    basics_category_code: Mapped[str] = mapped_column(default="basics")
    evidence_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_profile_photo_status",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "basics_fact_id", "basics_category_code"],
            [
                "fact_records.workspace_id",
                "fact_records.id",
                "fact_records.category_code",
            ],
            name="fk_profile_photo_basics",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "evidence_id"],
            ["evidence.workspace_id", "evidence.id"],
            name="fk_profile_photo_evidence",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "workspace_id", "evidence_id", name="uq_profile_photo_evidence"
        ),
        Index(
            "uq_active_profile_photo",
            "workspace_id",
            "basics_fact_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )


class FactAuditEvent(WorkbenchBase):
    __tablename__ = "fact_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    schema_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("fact_schema_versions.id"), nullable=True
    )
    changed_fields: Mapped[str] = mapped_column(Text, default="[]")
    before_values: Mapped[str] = mapped_column(Text, default="{}")
    after_values: Mapped[str] = mapped_column(Text, default="{}")
    related_fact_ids: Mapped[str] = mapped_column(Text, default="[]")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvidenceAuditEvent(WorkbenchBase):
    __tablename__ = "evidence_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    changed_fields: Mapped[str] = mapped_column(Text, default="[]")
    before_values: Mapped[str] = mapped_column(Text, default="{}")
    after_values: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExperienceSkillLink(WorkbenchBase):
    __tablename__ = "experience_skill_links"

    workspace_id: Mapped[int] = mapped_column(primary_key=True)
    experience_fact_id: Mapped[int] = mapped_column(
        ForeignKey("fact_records.id"), primary_key=True
    )
    skill_fact_id: Mapped[int] = mapped_column(
        ForeignKey("fact_records.id"), primary_key=True
    )
    experience_category: Mapped[str] = mapped_column(default="experience")
    skill_category: Mapped[str] = mapped_column(default="skill")


class RequirementProfile(WorkbenchBase):
    __tablename__ = "requirement_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    role_direction: Mapped[str] = mapped_column(String(180), default="")
    core_requirements: Mapped[str] = mapped_column(Text, default="[]")
    general_requirements: Mapped[str] = mapped_column(Text, default="")
    responsibilities: Mapped[str] = mapped_column(Text, default="")
    resume_strategy: Mapped[str] = mapped_column(Text, default="")
    raw_jd: Mapped[str] = mapped_column(Text, default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recycled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class JobOpportunity(WorkbenchBase):
    __tablename__ = "job_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_profiles.id"), index=True
    )
    company: Mapped[str] = mapped_column(String(180), default="")
    title: Mapped[str] = mapped_column(String(180), default="")
    raw_jd: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProfileAuditEvent(WorkbenchBase):
    __tablename__ = "profile_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("requirement_profiles.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    changed_fields_json: Mapped[str] = mapped_column(Text, default="[]")
    before_values_json: Mapped[str] = mapped_column(Text, default="{}")
    after_values_json: Mapped[str] = mapped_column(Text, default="{}")
    related_profile_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Template(WorkbenchBase):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_key: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    renderer_key: Mapped[str] = mapped_column(String(100))
    supported_sections_json: Mapped[str] = mapped_column(Text, default="[]")
    default_sections_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="available")
    successor_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class TemplatePreference(WorkbenchBase):
    __tablename__ = "workspace_template_preferences"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), primary_key=True
    )
    default_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    last_selected_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class LinkedResume(WorkbenchBase):
    __tablename__ = "linked_resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_profiles.id"), index=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    selection_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(20), default="open")
    converted_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Resume(WorkbenchBase):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(ForeignKey("requirement_profiles.id"))
    origin_linked_resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("linked_resumes.id"), nullable=True, unique=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    display_name: Mapped[str] = mapped_column(String(240))
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume_versions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recycled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        Index(
            "uq_active_resume_per_profile",
            "workspace_id",
            "requirement_profile_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )


class ResumeVersion(WorkbenchBase):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[str] = mapped_column(Text)
    profile_snapshot_json: Mapped[str] = mapped_column(Text)
    profile_snapshot_hash: Mapped[str] = mapped_column(String(64))
    source_manifest_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_manifest_json: Mapped[str] = mapped_column(Text, default="[]")
    content_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(40))
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("resume_id", "version_number", name="uq_resume_version"),
    )


class ResumeWorkingCopy(WorkbenchBase):
    __tablename__ = "resume_working_copies"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), unique=True)
    base_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume_versions.id"), nullable=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    content_json: Mapped[str] = mapped_column(Text)
    content_state: Mapped[str] = mapped_column(String(20), default="clean")
    evidence_sync_state: Mapped[str] = mapped_column(String(20), default="clean")
    baseline_state: Mapped[str] = mapped_column(String(20), default="current")
    pending_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ResumeFactUse(WorkbenchBase):
    __tablename__ = "resume_fact_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    section_code: Mapped[str] = mapped_column(String(100))
    block_key: Mapped[str] = mapped_column(String(100))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    fact_content_hash: Mapped[str] = mapped_column(String(64), default="")
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resume_id",
            "fact_id",
            "section_code",
            "block_key",
            name="uq_resume_fact_use",
        ),
    )


class ResumeVersionFactSnapshot(WorkbenchBase):
    __tablename__ = "resume_version_fact_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    resume_version_id: Mapped[int] = mapped_column(
        ForeignKey("resume_versions.id"), index=True
    )
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    section_code: Mapped[str] = mapped_column(String(100))
    block_key: Mapped[str] = mapped_column(String(100))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    fact_content_hash: Mapped[str] = mapped_column(String(64), default="")
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resume_version_id",
            "fact_id",
            "section_code",
            "block_key",
            name="uq_version_fact_snapshot",
        ),
    )


class ResumeEvidenceUse(WorkbenchBase):
    __tablename__ = "resume_evidence_uses"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    section_code: Mapped[str] = mapped_column(String(100))
    block_key: Mapped[str] = mapped_column(String(100))
    display_mode: Mapped[str] = mapped_column(String(30), default="reference")
    label: Mapped[str] = mapped_column(String(250), default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resume_id",
            "evidence_id",
            "section_code",
            "block_key",
            name="uq_resume_evidence_use",
        ),
    )


class ResumeVersionEvidenceSnapshot(WorkbenchBase):
    __tablename__ = "resume_version_evidence_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    resume_version_id: Mapped[int] = mapped_column(
        ForeignKey("resume_versions.id"), index=True
    )
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    section_code: Mapped[str] = mapped_column(String(100))
    block_key: Mapped[str] = mapped_column(String(100))
    display_mode: Mapped[str] = mapped_column(String(30), default="reference")
    label: Mapped[str] = mapped_column(String(250), default="")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resume_version_id",
            "evidence_id",
            "section_code",
            "block_key",
            name="uq_version_evidence_snapshot",
        ),
    )


class PendingIssue(WorkbenchBase):
    __tablename__ = "pending_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="source_changed")
    status: Mapped[str] = mapped_column(String(20), default="open")
    fact_id: Mapped[int | None] = mapped_column(ForeignKey("fact_records.id"), nullable=True)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_profiles.id"), nullable=True
    )
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True)
    section_code: Mapped[str] = mapped_column(String(100), default="")
    block_key: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExportEvent(WorkbenchBase):
    __tablename__ = "export_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    resume_version_id: Mapped[int] = mapped_column(
        ForeignKey("resume_versions.id"), index=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), index=True)
    format: Mapped[str] = mapped_column(String(20), default="html")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    forced: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
