"""Re-links every track of a case into entities. Entities an investigator has edited ("locked") are preserved."""
import re
from collections import Counter
from datetime import timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..models import Entity, Evidence, Track
from .matching import MatchConfig, TrackInfo, cluster, cluster_confidence, member_confidence
from .timeline import effective_location

PREFIX = {"PERSON": "P", "VEHICLE": "V"}


def match_config() -> MatchConfig:
    return MatchConfig(threshold=settings.match_threshold, person_max_speed=settings.person_max_speed,
                       vehicle_max_speed=settings.vehicle_max_speed, same_place_m=settings.same_place_m)


def next_label_numbers(entities) -> dict:
    nums = {"PERSON": 0, "VEHICLE": 0}
    for e in entities:
        m = re.fullmatch(r"[PV]-(\d+)", e.label or "")
        if m and e.group in nums:
            nums[e.group] = max(nums[e.group], int(m.group(1)))
    return nums


def next_label(group: str, nums: dict) -> str:
    nums[group] += 1
    return f"{PREFIX[group]}-{nums[group]:02d}"


def rebuild_case(db: Session, case_id: int) -> dict:
    entities = list(db.scalars(select(Entity).where(Entity.case_id == case_id)))
    locked_ids = {e.id for e in entities if e.locked}
    nums = next_label_numbers(entities)

    tracks = list(db.scalars(
        select(Track).where(Track.case_id == case_id)
        .options(joinedload(Track.evidence).joinedload(Evidence.source))
    ).unique())
    free = [t for t in tracks if t.entity_id is None or t.entity_id not in locked_ids]
    for t in free:
        t.entity_id, t.link_score = None, None
    db.flush()
    for e in entities:
        if not e.locked:
            db.delete(e)
    db.flush()

    infos = []
    for t in free:
        ev = t.evidence
        lat, lng = effective_location(ev)
        infos.append(TrackInfo(
            id=t.id, evidence_id=ev.id, source_id=ev.source_id, cls=t.cls, group=t.group,
            start=ev.recorded_at + timedelta(seconds=t.start_offset), end=ev.recorded_at + timedelta(seconds=t.end_offset),
            lat=lat, lng=lng, emb=np.array(t.embedding, dtype=np.float32) if t.embedding else None,
        ))
    clusters, scores = cluster(infos, match_config())

    created = 0
    for idxs in sorted(clusters, key=lambda c: min(infos[i].start for i in c)):
        members = [free[i] for i in idxs]
        group = members[0].group
        cls = Counter(m.cls for m in members).most_common(1)[0][0]
        ent = Entity(case_id=case_id, label=next_label(group, nums), group=group, cls=cls,
                     locked=False, confidence=cluster_confidence(idxs, scores))
        db.add(ent)
        db.flush()
        for i in idxs:
            free[i].entity_id = ent.id
            free[i].link_score = member_confidence(i, idxs, scores)
        created += 1
    db.commit()
    return {"tracks": len(free), "entities": created, "locked_kept": len(locked_ids)}
