from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Entity, Track, User
from ..security import current_user
from ..services.rebuild import next_label, next_label_numbers

router = APIRouter(tags=["entities"])
"""Human-in-the-loop corrections. Any edited entity is 'locked' so automatic re-linking never undoes the investigator's decision."""


def _entity(db: Session, entity_id: int) -> Entity:
    e = db.get(Entity, entity_id)
    if not e:
        raise HTTPException(404, "Entity not found")
    return e


def _drop_if_empty(db: Session, entity_id):
    if entity_id is None:
        return
    e = db.get(Entity, entity_id)
    if e and not db.scalar(select(Track.id).where(Track.entity_id == entity_id).limit(1)):
        db.delete(e)


class RenameIn(BaseModel):
    label: str = Field(min_length=1, max_length=60)


@router.put("/entities/{entity_id}")
def rename(entity_id: int, data: RenameIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    e = _entity(db, entity_id)
    e.label, e.locked = data.label.strip(), True
    db.commit()
    return {"id": e.id, "label": e.label}


class MergeIn(BaseModel):
    target_id: int
    source_ids: List[int] = Field(min_length=1)


@router.post("/entities/merge")
def merge(data: MergeIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    target = _entity(db, data.target_id)
    for sid in set(data.source_ids):
        if sid == target.id:
            continue
        src = _entity(db, sid)
        if src.case_id != target.case_id or src.group != target.group:
            raise HTTPException(400, "Only entities of the same case and kind (person/vehicle) can be merged")
        for t in db.scalars(select(Track).where(Track.entity_id == sid)):
            t.entity_id, t.link_score = target.id, None
        db.flush()
        db.delete(src)
    target.locked, target.confidence = True, None
    db.commit()
    return {"id": target.id}


@router.post("/tracks/{track_id}/detach")
def detach(track_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """'This is not the same one': move a sighting into a new entity of its own."""
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Track not found")
    old = t.entity_id
    nums = next_label_numbers(list(db.scalars(select(Entity).where(Entity.case_id == t.case_id))))
    new = Entity(case_id=t.case_id, label=next_label(t.group, nums), group=t.group, cls=t.cls, locked=True)
    db.add(new)
    db.flush()
    t.entity_id, t.link_score = new.id, None
    if old:
        oe = db.get(Entity, old)
        if oe:
            oe.locked = True
    db.flush()
    _drop_if_empty(db, old)
    db.commit()
    return {"entity_id": new.id}


class AssignIn(BaseModel):
    entity_id: int


@router.post("/tracks/{track_id}/assign")
def assign(track_id: int, data: AssignIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    t = db.get(Track, track_id)
    if not t:
        raise HTTPException(404, "Track not found")
    target = _entity(db, data.entity_id)
    if target.case_id != t.case_id or target.group != t.group:
        raise HTTPException(400, "That entity belongs to a different case or kind of object")
    old = t.entity_id
    t.entity_id, t.link_score = target.id, None
    target.locked = True
    if old and old != target.id:
        oe = db.get(Entity, old)
        if oe:
            oe.locked = True
    db.flush()
    _drop_if_empty(db, old)
    db.commit()
    return {"entity_id": target.id}
