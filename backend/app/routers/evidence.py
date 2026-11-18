import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Case, Evidence, Source, Track, User
from ..security import current_user
from ..services.pipeline import enqueue
from ..services.rebuild import rebuild_case
from .media import ranged_file

router = APIRouter(tags=["evidence"])

VIDEO_EXT = {"mp4", "mov", "avi", "mkv", "webm", "m4v"}
IMAGE_EXT = {"jpg", "jpeg", "png", "bmp", "webp"}


def ev_out(e: Evidence, track_count: int = 0) -> dict:
    return {
        "id": e.id, "case_id": e.case_id, "filename": e.filename, "media_type": e.media_type, "size_bytes": e.size_bytes,
        "sha256": e.sha256, "recorded_at": e.recorded_at, "lat": e.lat, "lng": e.lng, "notes": e.notes,
        "status": e.status, "progress": e.progress, "error": e.error, "fps": e.fps, "duration_s": e.duration_s,
        "uploaded_at": e.uploaded_at, "track_count": track_count,
        "source": {"id": e.source.id, "name": e.source.name, "type": e.source.type, "lat": e.source.lat, "lng": e.source.lng},
    }


def exif_datetime(path: Path) -> Optional[datetime]:
    try:
        from PIL import Image
        exif = Image.open(path).getexif()
        raw = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
        return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S") if raw else None
    except Exception:
        return None


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(400, "recorded_at must be a date-time such as 2026-05-01T10:30:00")


def get_ev(db: Session, evidence_id: int) -> Evidence:
    e = db.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    return e


@router.get("/cases/{case_id}/evidence")
def list_evidence(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    if not db.get(Case, case_id):
        raise HTTPException(404, "Case not found")
    counts = dict(db.execute(select(Track.evidence_id, func.count()).where(Track.case_id == case_id).group_by(Track.evidence_id)).all())
    rows = db.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.recorded_at))
    return [ev_out(e, counts.get(e.id, 0)) for e in rows]


@router.post("/cases/{case_id}/evidence")
async def upload_evidence(case_id: int, file: UploadFile = File(...), source_id: int = Form(...),
                          recorded_at: Optional[str] = Form(None), lat: Optional[float] = Form(None),
                          lng: Optional[float] = Form(None), notes: str = Form(""),
                          db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Case, case_id):
        raise HTTPException(404, "Case not found")
    if not db.get(Source, source_id):
        raise HTTPException(400, "Choose a camera / source for this evidence")
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext in VIDEO_EXT:
        media_type = "video"
    elif ext in IMAGE_EXT:
        media_type = "image"
    else:
        raise HTTPException(400, "Unsupported file type. Use video (MP4, MOV, AVI, MKV, WebM) or image (JPG, PNG, WebP)")
    if (lat is None) != (lng is None):
        raise HTTPException(400, "Give both latitude and longitude, or neither")

    stored = f"{uuid.uuid4().hex}.{ext}"
    path = settings.media_dir / "evidence" / stored
    sha, size, limit = hashlib.sha256(), 0, settings.max_upload_mb * 1024 * 1024
    with open(path, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
            sha.update(chunk)
            out.write(chunk)

    when = parse_time(recorded_at) or (exif_datetime(path) if media_type == "image" else None) or datetime.now().replace(microsecond=0)
    ev = Evidence(case_id=case_id, source_id=source_id, filename=Path(file.filename).name[:300], stored_name=stored,
                  media_type=media_type, size_bytes=size, sha256=sha.hexdigest(), recorded_at=when, lat=lat, lng=lng,
                  notes=notes, uploaded_by=user.id)
    db.add(ev)
    db.commit()
    enqueue(ev.id)
    return ev_out(ev)


class EvidenceUpdate(BaseModel):
    recorded_at: datetime
    source_id: int
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    notes: str = ""


@router.put("/evidence/{evidence_id}")
def update_evidence(evidence_id: int, data: EvidenceUpdate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Fixing the time or location shifts the whole timeline. Tracks store offsets, so no re-analysis is needed."""
    e = get_ev(db, evidence_id)
    if not db.get(Source, data.source_id):
        raise HTTPException(400, "Unknown camera")
    if (data.lat is None) != (data.lng is None):
        raise HTTPException(400, "Give both latitude and longitude, or neither")
    e.recorded_at, e.source_id, e.lat, e.lng, e.notes = data.recorded_at.replace(tzinfo=None), data.source_id, data.lat, data.lng, data.notes
    db.commit()
    rebuild_case(db, e.case_id)
    return ev_out(e)


@router.post("/evidence/{evidence_id}/reprocess")
def reprocess(evidence_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    e = get_ev(db, evidence_id)
    e.status, e.progress, e.error = "PENDING", 0, ""
    db.commit()
    enqueue(e.id)
    return ev_out(e)


@router.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    e = get_ev(db, evidence_id)
    case_id = e.case_id
    (settings.media_dir / "evidence" / e.stored_name).unlink(missing_ok=True)
    (settings.media_dir / "previews" / f"{e.id}.jpg").unlink(missing_ok=True)
    for t in e.tracks:
        (settings.media_dir / "thumbs" / f"{e.id}_{t.local_id}.jpg").unlink(missing_ok=True)
    db.delete(e)
    db.commit()
    rebuild_case(db, case_id)
    return {"ok": True}


@router.get("/evidence/{evidence_id}/file")
def evidence_file(evidence_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(current_user)):
    e = get_ev(db, evidence_id)
    return ranged_file(settings.media_dir / "evidence" / e.stored_name, request)


@router.get("/evidence/{evidence_id}/preview")
def evidence_preview(evidence_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(current_user)):
    get_ev(db, evidence_id)
    return ranged_file(settings.media_dir / "previews" / f"{evidence_id}.jpg", request, "image/jpeg")


@router.get("/evidence/{evidence_id}/tracks")
def evidence_tracks(evidence_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    get_ev(db, evidence_id)
    rows = db.scalars(select(Track).where(Track.evidence_id == evidence_id).order_by(Track.start_offset))
    return [{"id": t.id, "cls": t.cls, "conf": round(t.conf or 0, 2), "n_det": t.n_det, "start_offset": t.start_offset,
             "end_offset": t.end_offset, "entity_id": t.entity_id, "has_thumb": t.has_thumb} for t in rows]


@router.get("/tracks/{track_id}/thumb")
def track_thumb(track_id: int, request: Request, db: Session = Depends(get_db), _: User = Depends(current_user)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Track not found")
    return ranged_file(settings.media_dir / "thumbs" / f"{t.evidence_id}_{t.local_id}.jpg", request, "image/jpeg")
