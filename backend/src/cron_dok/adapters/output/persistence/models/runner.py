"""ORM model for the runners table.

``ResourceLimits`` is stored flattened (memory_mb/cpu_quota/pids_limit/
network_enabled) and the cron expression as plain text; the domain value
objects are rebuilt by the repository mapper.
"""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from cron_dok.adapters.output.persistence.models.base import Base


class RunnerModel(Base):
    __tablename__ = "runners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    script_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    cpu_quota: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    pids_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    network_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    on_overlap: Mapped[str] = mapped_column(String(20), nullable=False, default="skip")
    dependencies: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
