"""Application settings model for key-value configuration."""
import json
from sqlalchemy import Column, String, Text
from app.database import Base


class ApplicationSettings(Base):
    """Key-value persistence for user preferences and configurations."""
    __tablename__ = "application_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)

    @classmethod
    def get_setting(cls, session, key: str, default: any = None) -> any:
        """Fetch setting value parsed by default type."""
        record = session.query(cls).filter(cls.key == key).first()
        if not record:
            return default
        try:
            return json.loads(record.value)
        except Exception:
            return record.value

    @classmethod
    def set_setting(cls, session, key: str, value: any) -> None:
        """Store setting as JSON string."""
        serialized = json.dumps(value)
        record = session.query(cls).filter(cls.key == key).first()
        if record:
            record.value = serialized
        else:
            record = cls(key=key, value=serialized)
            session.add(record)

