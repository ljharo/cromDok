"""ORM model for the env_vars table (values encrypted at rest)."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from cron_dok.adapters.output.persistence.models.base import Base


class EnvVarModel(Base):
    __tablename__ = "env_vars"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    runner_id: Mapped[int | None] = mapped_column(
        ForeignKey("runners.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
