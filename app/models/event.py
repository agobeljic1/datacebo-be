from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.session import Base


class DownloadEvent(Base):
    __tablename__ = "download_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    license_key = Column(String(64), nullable=True, index=True)
    package_name = Column(String(100), nullable=False, index=True)
    package_version = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    valid_at_log_time = Column(Integer, nullable=False)  # 1 valid, 0 invalid
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


