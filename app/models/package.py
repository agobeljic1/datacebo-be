from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.db.session import Base


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    # True for base package, False for add-on
    is_base = Column(Boolean, nullable=False, default=False)
    price = Column(Integer, nullable=False)
    # When true, the package is no longer available for new licenses
    is_deprecated = Column(Boolean, nullable=False, default=False, server_default="0")


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # many-to-many to packages via association table
    packages = relationship("Package", secondary="license_packages")


class LicensePackage(Base):
    __tablename__ = "license_packages"

    license_id = Column(Integer, ForeignKey("licenses.id", ondelete="CASCADE"), primary_key=True)
    package_id = Column(Integer, ForeignKey("packages.id", ondelete="CASCADE"), primary_key=True)


