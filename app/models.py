from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    desired_city: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(100), default="")
    graduation: Mapped[str] = mapped_column(String(50), default="")
    availability: Mapped[str] = mapped_column(String(100), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(200), default="")


class Education(Base):
    __tablename__ = "educations"

    id: Mapped[int] = mapped_column(primary_key=True)
    school: Mapped[str] = mapped_column(String(200), default="")
    major: Mapped[str] = mapped_column(String(200), default="")
    degree: Mapped[str] = mapped_column(String(100), default="")
    period: Mapped[str] = mapped_column(String(100), default="")
    achievement: Mapped[str] = mapped_column(Text, default="")
    courses: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    source_ref: Mapped[str] = mapped_column(String(200), default="")


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), default="")
    kind: Mapped[str] = mapped_column(String(100), default="")
    period: Mapped[str] = mapped_column(String(100), default="")
    organization: Mapped[str] = mapped_column(String(250), default="")
    role: Mapped[str] = mapped_column(String(250), default="")
    context: Mapped[str] = mapped_column(Text, default="")
    work: Mapped[str] = mapped_column(Text, default="")
    tools: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    challenge: Mapped[str] = mapped_column(Text, default="")
    solution: Mapped[str] = mapped_column(Text, default="")
    public_note: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(String(500), default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    source_ref: Mapped[str] = mapped_column(String(200), default="")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    proficiency: Mapped[str] = mapped_column(String(50), default="能用")
    context: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    source_ref: Mapped[str] = mapped_column(String(200), default="")


class Award(Base):
    __tablename__ = "awards"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250), default="")
    period: Mapped[str] = mapped_column(String(100), default="")
    issuer: Mapped[str] = mapped_column(String(200), default="")
    result: Mapped[str] = mapped_column(String(250), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    source_ref: Mapped[str] = mapped_column(String(200), default="")


class JobTarget(Base):
    __tablename__ = "job_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResumeTemplate(Base):
    __tablename__ = "resume_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), default="")
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResumeDocument(Base):
    __tablename__ = "resume_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="未命名简历")
    target_id: Mapped[int | None] = mapped_column(ForeignKey("job_targets.id"), nullable=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("resume_templates.id"))
    snapshot: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target: Mapped[JobTarget | None] = relationship()
    template: Mapped[ResumeTemplate] = relationship()

