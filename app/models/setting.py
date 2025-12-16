"""
Setting model for storing application settings.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.models.base import Base


class Setting(Base):
    """
    Model for storing key-value application settings.

    This table stores various application settings as key-value pairs,
    such as task list order preferences, UI preferences, etc.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Setting(key='{self.key}')>"
