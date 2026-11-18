from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..models import Case, Entity, Evidence, Track, User
from ..security import current_user
from ..services import timeline
from ..services.rebuild import rebuild_case

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    incident_time: Optional[datetime] = None


def case_out(c: Case, counts: dict = None) -> dict:
    d = {"id": c.id, "title": c.title, "description": c.description, "status": c.status,
         "incident_time": c.incident_time, "created_at": c.created_at}
    if counts is not None:
        d.update(counts)
    return d


def get_case(db: Session, case_id: int) -> Case:
    c = db.get(Case, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    return c


@router.get("")
def list_cases(db: Session = Depends(get_db), _: User = Depends(current_user)):
    ev = dict(db.execute(select(Evidence.case_id, func.count()).group_by(Evidence.case_id)).all())
    en = dict(db.execute(select(Entity.case_id, func.count()).group_by(Entity.case_id)).all())
    cases = db.scalars(select(Case).order_by(Case.created_at.desc()))
    return [case_out(c, {"evidence_count": ev.get(c.id, 0), "entity_count": en.get(c.id, 0)}) for c in cases]


@router.post("")
def create_case(data: CaseIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = Case(title=data.title.strip(), description=data.description, incident_time=data.incident_time, created_by=user.id)
    db.add(c)
    db.commit()
    return case_out(c)


@router.post("/demo")
def create_demo(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """One-click synthetic scenario so the whole workflow can be shown without real footage."""
    from ..services.demo import create_demo_case
    return case_out(create_demo_case(db, user.id))


@router.get("/{case_id}")
def read_case(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return case_out(get_case(db, case_id))


@router.put("/{case_id}")
def update_case(case_id: int, data: CaseIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    c = get_case(db, case_id)
    c.title, c.description, c.incident_time = data.title.strip(), data.description, data.incident_time
    db.commit()
    return case_out(c)


@router.delete("/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    c = get_case(db, case_id)
    for ev in c.evidence:
        (settings.media_dir / "evidence" / ev.stored_name).unlink(missing_ok=True)
        (settings.media_dir / "previews" / f"{ev.id}.jpg").unlink(missing_ok=True)
        for t in ev.tracks:
            (settings.media_dir / "thumbs" / f"{ev.id}_{t.local_id}.jpg").unlink(missing_ok=True)
    db.delete(c)
    db.commit()
    return {"ok": True}


def _timeline(db: Session, case_id: int) -> dict:
    case = get_case(db, case_id)
    entities = list(db.scalars(select(Entity).where(Entity.case_id == case_id)))
    tracks = list(db.scalars(
        select(Track).where(Track.case_id == case_id)
        .options(joinedload(Track.evidence).joinedload(Evidence.source))
    ).unique())
    tl = timeline.build(case, entities, tracks)
    ev = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id)))
    tl["case"] = case_out(case)
    tl["stats"] = {
        "evidence": len(ev), "pending": sum(1 for e in ev if e.status in ("PENDING", "PROCESSING")),
        "failed": sum(1 for e in ev if e.status == "FAILED"),
        "entities": len(tl["entities"]), "linked": sum(1 for e in tl["entities"] if e["n_sources"] > 1),
        "events": len(tl["events"]),
    }
    return tl


@router.get("/{case_id}/timeline")
def get_timeline(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return _timeline(db, case_id)


@router.post("/{case_id}/rebuild")
def rebuild(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    get_case(db, case_id)
    return rebuild_case(db, case_id)


@router.get("/{case_id}/export.csv")
def export_csv(case_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    tl = _timeline(db, case_id)
    return Response(timeline.to_csv(tl), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="case-{case_id}-timeline.csv"'})
