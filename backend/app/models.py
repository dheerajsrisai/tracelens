from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    incident_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="case", cascade="all, delete-orphan")


class Source(Base):
    """A camera or other evidence source (CCTV, traffic camera, bus camera, citizen)."""
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(20), default="CCTV")       # CCTV | TRAFFIC | BUS | CITIZEN | OTHER
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    filename: Mapped[str] = mapped_column(String(300))
    stored_name: Mapped[str] = mapped_column(String(100))
    media_type: Mapped[str] = mapped_column(String(10))                 # video | image
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")         # chain-of-custody fingerprint
    recorded_at: Mapped[datetime] = mapped_column(DateTime)             # start of the recording (naive local time)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # optional override of the source location
    lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING | PROCESSING | DONE | FAILED
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    fps: Mapped[float] = mapped_column(Float, default=0)
    duration_s: Mapped[float] = mapped_column(Float, default=0)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    case = relationship("Case", back_populates="evidence")
    source = relationship("Source")
    tracks = relationship("Track", back_populates="evidence", cascade="all, delete-orphan")


class Entity(Base):
    """One real-world person/vehicle, possibly seen by several cameras."""
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(60))
    group: Mapped[str] = mapped_column("kind", String(10))               # PERSON | VEHICLE
    cls: Mapped[str] = mapped_column(String(20))                        # PERSON | CAR | BUS | TRUCK | BICYCLE | MOTORCYCLE
    locked: Mapped[bool] = mapped_column(Boolean, default=False)        # True once an investigator edited it
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    case = relationship("Case", back_populates="entities")
    tracks = relationship("Track", back_populates="entity", passive_deletes=True)


class Track(Base):
    """One object followed through one piece of evidence (a ByteTrack track, or one detection in an image)."""
    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    local_id: Mapped[int] = mapped_column(Integer, default=0)           # ID given by the tracker inside this video
    cls: Mapped[str] = mapped_column(String(20))
    group: Mapped[str] = mapped_column("kind", String(10))
    conf: Mapped[float] = mapped_column(Float, default=0)
    n_det: Mapped[int] = mapped_column(Integer, default=1)
    start_offset: Mapped[float] = mapped_column(Float, default=0)       # seconds from the start of the evidence
    end_offset: Mapped[float] = mapped_column(Float, default=0)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    link_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    has_thumb: Mapped[bool] = mapped_column(Boolean, default=False)

    evidence = relationship("Evidence", back_populates="tracks")
    entity = relationship("Entity", back_populates="tracks")
