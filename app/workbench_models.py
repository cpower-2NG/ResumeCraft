from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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


class FactRecord(WorkbenchBase):
    __tablename__ = "fact_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(250))
    content: Mapped[str] = mapped_column(Text, default="{}")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="active")
    source_note: Mapped[str] = mapped_column(Text, default="")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class FactAudit(WorkbenchBase):
    __tablename__ = "fact_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)
    before_content: Mapped[str] = mapped_column(Text, default="{}")
    after_content: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


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
    identity_key: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("workspace_id", "identity_key", name="uq_profile_identity_key"),)


class JobOpportunity(WorkbenchBase):
    __tablename__ = "job_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(ForeignKey("requirement_profiles.id"), index=True)
    company: Mapped[str] = mapped_column(String(180), default="")
    title: Mapped[str] = mapped_column(String(180), default="")
    raw_jd: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResumeTemplate(WorkbenchBase):
    __tablename__ = "resume_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_template_slug"),)


class TemplateVersion(WorkbenchBase):
    __tablename__ = "template_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("resume_templates.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_template_version"),)


class LinkedResume(WorkbenchBase):
    __tablename__ = "linked_resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(ForeignKey("requirement_profiles.id"), index=True)
    template_version_id: Mapped[int] = mapped_column(ForeignKey("template_versions.id"))
    selection: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ResumeIdentity(WorkbenchBase):
    __tablename__ = "resume_identities"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requirement_profile_id: Mapped[int] = mapped_column(ForeignKey("requirement_profiles.id"))
    identity_key: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(240))
    current_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("workspace_id", "identity_key", name="uq_resume_identity_key"), UniqueConstraint("workspace_id", "requirement_profile_id", name="uq_resume_per_profile"))


class ResumeVersion(WorkbenchBase):
    __tablename__ = "resume_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_identity_id: Mapped[int] = mapped_column(ForeignKey("resume_identities.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    source_manifest: Mapped[str] = mapped_column(Text, default="[]")
    profile_snapshot: Mapped[str] = mapped_column(Text)
    template_version_id: Mapped[int] = mapped_column(ForeignKey("template_versions.id"))
    reason: Mapped[str] = mapped_column(String(40))
    change_summary: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("resume_identity_id", "version_number", name="uq_resume_version"),)


class ResumeWorkingCopy(WorkbenchBase):
    __tablename__ = "resume_working_copies"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_identity_id: Mapped[int] = mapped_column(ForeignKey("resume_identities.id"), unique=True)
    base_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ResumeFactReference(WorkbenchBase):
    __tablename__ = "resume_fact_references"
    id: Mapped[int] = mapped_column(primary_key=True)
    resume_identity_id: Mapped[int] = mapped_column(ForeignKey("resume_identities.id"), index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(100))
    block_id: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("resume_identity_id", "fact_id", "section_id", "block_id", name="uq_resume_fact_ref"),)


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
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class FactEvidence(WorkbenchBase):
    __tablename__ = "fact_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    __table_args__ = (UniqueConstraint("fact_id", "evidence_id", name="uq_fact_evidence"),)


class PendingItem(WorkbenchBase):
    __tablename__ = "pending_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resume_identity_id: Mapped[int] = mapped_column(ForeignKey("resume_identities.id"), index=True)
    fact_id: Mapped[int] = mapped_column(ForeignKey("fact_records.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="source_changed")
    status: Mapped[str] = mapped_column(String(20), default="open")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
