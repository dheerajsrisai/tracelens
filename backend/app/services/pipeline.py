"""
Evidence processing: detect (YOLO11) -> track (ByteTrack) -> describe (appearance embedding) -> store.

Videos are tracked with Ultralytics' built-in ByteTrack. Images (citizen uploads) are detected only; every
detection becomes a one-frame track. After processing, the case is re-clustered (see rebuild.py).
"""
import logging
import math
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from sqlalchemy import delete

from ..config import settings
from ..database import SessionLocal
from ..models import Evidence, Track
from . import embedder
from .rebuild import rebuild_case

log = logging.getLogger("tracelens")

# COCO class id -> label. These are the object types relevant to an incident.
CLASS_MAP = {0: "PERSON", 1: "BICYCLE", 2: "CAR", 3: "MOTORCYCLE", 5: "BUS", 7: "TRUCK"}
GROUP_OF = {"PERSON": "PERSON"}      # everything else is a VEHICLE
MIN_CROP_PX = 20
TOP_CROPS = 5
MAX_TRACKS_PER_EVIDENCE = 300

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tracelens")   # one analysis at a time (CPU friendly)


def enqueue(evidence_id: int) -> None:
    _executor.submit(_safe_process, evidence_id)


def _safe_process(evidence_id: int) -> None:
    try:
        process_evidence(evidence_id)
    except Exception:                                    # never let the worker thread die silently
        log.error("Processing crashed for evidence %s\n%s", evidence_id, traceback.format_exc())


def _group(cls: str) -> str:
    return GROUP_OF.get(cls, "VEHICLE")


def _crop(img: np.ndarray, xyxy) -> Optional[np.ndarray]:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in xyxy]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < MIN_CROP_PX or y2 - y1 < MIN_CROP_PX:
        return None
    return img[y1:y2, x1:x2].copy()


class TrackAcc:
    """Accumulates everything we learn about one tracked object while a video is processed."""

    def __init__(self, tid: int):
        self.tid = tid
        self.votes: Counter = Counter()
        self.n = 0
        self.first = None
        self.last = None
        self.conf_sum = 0.0
        self.crops = []                                  # best (score, crop) pairs

    def update(self, frame_idx: int, cls: str, conf: float, img: np.ndarray, xyxy) -> None:
        self.n += 1
        self.votes[cls] += 1
        self.conf_sum += conf
        self.first = frame_idx if self.first is None else self.first
        self.last = frame_idx
        h, w = img.shape[:2]
        area = max(0.0, (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])) / float(w * h)
        score = conf * math.sqrt(area)                   # prefer large, confident views
        if len(self.crops) < TOP_CROPS or score > self.crops[-1][0]:
            c = _crop(img, xyxy)
            if c is not None:
                self.crops.append((score, c))
                self.crops.sort(key=lambda x: -x[0])
                del self.crops[TOP_CROPS:]


def _save_thumb(crop: np.ndarray, evidence_id: int, tid: int) -> None:
    h, w = crop.shape[:2]
    scale = 180.0 / max(h, 1)
    thumb = cv2.resize(crop, (max(1, int(w * scale)), 180), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(settings.media_dir / "thumbs" / f"{evidence_id}_{tid}.jpg"), thumb)


def _save_preview(frame: np.ndarray, evidence_id: int) -> None:
    h, w = frame.shape[:2]
    scale = min(1.0, 640.0 / max(w, 1))
    small = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(settings.media_dir / "previews" / f"{evidence_id}.jpg"), small)


def _make_track(ev: Evidence, tid: int, acc: TrackAcc, fps: float) -> Optional[Track]:
    if not acc.crops:
        return None
    cls = acc.votes.most_common(1)[0][0]
    group = _group(cls)
    vectors = [embedder.embed(c, group) for _, c in acc.crops]
    emb = embedder.mean_embedding(vectors)
    _save_thumb(acc.crops[0][1], ev.id, tid)
    return Track(
        evidence_id=ev.id, case_id=ev.case_id, local_id=tid, cls=cls, group=group,
        conf=acc.conf_sum / max(acc.n, 1), n_det=acc.n,
        start_offset=acc.first / fps, end_offset=acc.last / fps,
        embedding=emb.tolist(), has_thumb=True,
    )


def _process_video(db, ev: Evidence, path: Path) -> list:
    from ultralytics import YOLO

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Could not open this video. Use an H.264 MP4 if possible.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    fps = fps if 1 <= fps <= 240 else 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, first = cap.read()
    cap.release()
    if not ok:
        raise ValueError("The video has no readable frames")
    _save_preview(first, ev.id)
    ev.fps, ev.duration_s = fps, (total / fps if total else 0)
    db.commit()

    stride = max(1, settings.frame_stride)
    expected = max(1, math.ceil(total / stride)) if total else 0
    model = YOLO(settings.yolo_model)                    # fresh model per video = fresh ByteTrack state
    results = model.track(
        source=str(path), stream=True, persist=True, tracker="bytetrack.yaml",
        classes=list(CLASS_MAP), conf=settings.det_conf, imgsz=settings.imgsz, vid_stride=stride, verbose=False,
    )

    accs = {}
    for i, r in enumerate(results):
        frame_idx = i * stride
        if r.boxes is not None and r.boxes.id is not None:
            ids = r.boxes.id.int().cpu().tolist()
            xyxy = r.boxes.xyxy.cpu().numpy()
            clss = r.boxes.cls.int().cpu().tolist()
            confs = r.boxes.conf.cpu().tolist()
            for tid, box, c, cf in zip(ids, xyxy, clss, confs):
                label = CLASS_MAP.get(c)
                if label:
                    accs.setdefault(tid, TrackAcc(tid)).update(frame_idx, label, cf, r.orig_img, box)
        if expected and i % 20 == 0:
            ev.progress = min(95, int(100 * i / expected))
            db.commit()

    tracks = []
    kept = sorted((a for a in accs.values() if a.n >= settings.min_detections), key=lambda a: -a.n)[:MAX_TRACKS_PER_EVIDENCE]
    for acc in kept:
        t = _make_track(ev, acc.tid, acc, fps)
        if t:
            tracks.append(t)
    return tracks


def _process_image(db, ev: Evidence, path: Path) -> list:
    from ultralytics import YOLO

    img = cv2.imread(str(path))                          # honours EXIF orientation
    if img is None:
        raise ValueError("Could not read this image")
    _save_preview(img, ev.id)
    model = YOLO(settings.yolo_model)
    res = model.predict(source=img, conf=settings.det_conf, imgsz=settings.imgsz, classes=list(CLASS_MAP), verbose=False)[0]

    tracks = []
    for i, box in enumerate(res.boxes):
        label = CLASS_MAP.get(int(box.cls[0]))
        if not label:
            continue
        xyxy = box.xyxy[0].cpu().numpy()
        conf = float(box.conf[0])
        acc = TrackAcc(i)
        acc.update(0, label, conf, img, xyxy)
        t = _make_track(ev, i, acc, 1.0)
        if t:
            t.n_det = 1
            tracks.append(t)
    return tracks


def process_evidence(evidence_id: int) -> None:
    db = SessionLocal()
    try:
        ev = db.get(Evidence, evidence_id)
        if ev is None:
            return
        ev.status, ev.progress, ev.error = "PROCESSING", 0, ""
        db.execute(delete(Track).where(Track.evidence_id == ev.id))       # re-processing replaces old results
        db.commit()
        path = settings.media_dir / "evidence" / ev.stored_name
        try:
            tracks = _process_video(db, ev, path) if ev.media_type == "video" else _process_image(db, ev, path)
            db.add_all(tracks)
            ev.status, ev.progress = "DONE", 100
            db.commit()
        except Exception as exc:
            db.rollback()
            ev = db.get(Evidence, evidence_id)
            ev.status, ev.error = "FAILED", str(exc)[:500]
            db.commit()
            log.error("Evidence %s failed: %s", evidence_id, traceback.format_exc())
            return
        rebuild_case(db, ev.case_id)
    finally:
        db.close()
