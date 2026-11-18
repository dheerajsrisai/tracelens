from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Evidence, Source, User
from ..security import current_user

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    type: Literal["CCTV", "TRAFFIC", "BUS", "CITIZEN", "OTHER"] = "CCTV"
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    notes: str = ""


def out(s: Source, n: int = 0) -> dict:
    return {"id": s.id, "name": s.name, "type": s.type, "lat": s.lat, "lng": s.lng, "notes": s.notes, "evidence_count": n}


@router.get("")
def list_cameras(db: Session = Depends(get_db), _: User = Depends(current_user)):
    counts = dict(db.execute(select(Evidence.source_id, func.count()).group_by(Evidence.source_id)).all())
    return [out(s, counts.get(s.id, 0)) for s in db.scalars(select(Source).order_by(Source.name))]


@router.post("")
def create_camera(data: CameraIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = Source(**data.model_dump())
    db.add(s)
    db.commit()
    return out(s)


@router.put("/{camera_id}")
def update_camera(camera_id: int, data: CameraIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = db.get(Source, camera_id)
    if not s:
        raise HTTPException(404, "Camera not found")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return out(s)


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = db.get(Source, camera_id)
    if not s:
        raise HTTPException(404, "Camera not found")
    if db.scalar(select(func.count()).select_from(Evidence).where(Evidence.source_id == camera_id)):
        raise HTTPException(409, "This camera has evidence attached and cannot be deleted")
    db.delete(s)
    db.commit()
    return {"ok": True}
