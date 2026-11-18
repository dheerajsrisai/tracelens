"""
Synthetic demo scenario (clearly labelled as such in the UI). Four cameras along a road; two pedestrians and
two cars appear in several of them. Scenes are drawn with OpenCV, so no real people are involved.
The objects' appearance descriptors then go through the SAME matching/clustering code as real evidence.
"""
import uuid
from datetime import datetime, timedelta

import cv2
import numpy as np

from . import embedder

CAMERAS = [  # demo coordinates (arbitrary road in a city centre)
    {"name": "DEMO Market Gate CCTV", "type": "CCTV", "lat": 12.9756, "lng": 77.6068, "bright": 1.00, "tint": (0, 0, 0)},
    {"name": "DEMO Junction traffic camera", "type": "TRAFFIC", "lat": 12.9779, "lng": 77.6089, "bright": 0.82, "tint": (8, -3, 5)},
    {"name": "DEMO Bus 21 front camera", "type": "BUS", "lat": 12.9801, "lng": 77.6110, "bright": 1.18, "tint": (-5, 3, 0)},
    {"name": "DEMO Citizen photo", "type": "CITIZEN", "lat": None, "lng": None, "bright": 0.92, "tint": (3, 0, -4)},
]

IDENTITIES = {
    "A": dict(kind="person", upper=(40, 40, 200), lower=(180, 90, 30)),      # red shirt, blue jeans
    "B": dict(kind="person", upper=(60, 170, 60), lower=(25, 25, 25)),       # green shirt, black trousers
    "V1": dict(kind="car", body=(235, 235, 235)),                            # white car
    "V2": dict(kind="car", body=(40, 40, 200)),                              # red car
}

# (camera index, seconds after 10:00:00, [(identity, x position)], optional override location)
SCENES = [
    (0, 5, [("A", 200), ("B", 430)], None),
    (0, 90, [("V1", 320)], None),
    (1, 190, [("A", 260), ("V1", 480)], None),
    (1, 215, [("B", 330)], None),
    (2, 380, [("A", 300), ("V2", 500)], None),
    (3, 555, [("A", 340)], (12.9822, 77.6128)),
]


def _noise(img, rng, sigma=8):
    return np.clip(img.astype(np.float32) + rng.normal(0, sigma, img.shape), 0, 255).astype(np.uint8)


def _person(img, cx, base_y, h, upper, lower):
    head_r, tw, lw = int(h * 0.08), int(h * 0.34), int(h * 0.26)
    top = base_y - h
    cv2.circle(img, (cx, top + head_r), head_r, (150, 170, 210), -1)
    t_top, t_bot = top + 2 * head_r + 2, top + int(h * 0.55)
    cv2.rectangle(img, (cx - tw // 2, t_top), (cx + tw // 2, t_bot), upper, -1)
    cv2.rectangle(img, (cx - lw // 2, t_bot), (cx + lw // 2, base_y), lower, -1)
    return (cx - tw // 2, top, cx + tw // 2, base_y)


def _car(img, cx, base_y, h, body):
    w = int(h * 2.3)
    x1, y2 = cx - w // 2, base_y
    y1 = y2 - h
    cv2.rectangle(img, (x1, y1 + int(h * 0.35)), (x1 + w, y2 - int(h * 0.12)), body, -1)                     # body
    cv2.rectangle(img, (x1 + int(w * 0.22), y1), (x1 + int(w * 0.72), y1 + int(h * 0.4)), body, -1)          # cabin
    cv2.rectangle(img, (x1 + int(w * 0.28), y1 + int(h * 0.08)), (x1 + int(w * 0.66), y1 + int(h * 0.36)), (60, 55, 50), -1)
    for wx in (0.22, 0.78):
        cv2.circle(img, (x1 + int(w * wx), y2 - int(h * 0.1)), int(h * 0.14), (20, 20, 20), -1)
    return (x1, y1, x1 + w, y2)


def generate_scenes(seed: int = 11):
    """Returns a list of scenes: {camera, time, image, objects:[{identity, cls, group, box, crop}], override}."""
    rng = np.random.default_rng(seed)
    day = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    out = []
    for cam_i, secs, objs, override in SCENES:
        cam = CAMERAS[cam_i]
        img = np.zeros((360, 640, 3), np.uint8)
        img[:] = (150, 150, 145)
        img[230:, :] = (95, 95, 100)                                                  # road
        boxes = []
        for ident, x in objs:
            spec = IDENTITIES[ident]
            if spec["kind"] == "person":
                box = _person(img, x, 330, 170, spec["upper"], spec["lower"])
                cls, group = "PERSON", "PERSON"
            else:
                box = _car(img, x, 320, 80, spec["body"])
                cls, group = "CAR", "VEHICLE"
            boxes.append((ident, cls, group, box))
        img = img.astype(np.float32) * cam["bright"] + np.array(cam["tint"], np.float32)
        img = _noise(np.clip(img, 0, 255).astype(np.uint8), rng)
        objects = []
        for ident, cls, group, (x1, y1, x2, y2) in boxes:
            px, py = int((x2 - x1) * 0.06), int((y2 - y1) * 0.04)
            crop = img[max(0, y1 - py):min(360, y2 + py), max(0, x1 - px):min(640, x2 + px)].copy()
            objects.append({"identity": ident, "cls": cls, "group": group, "box": (x1, y1, x2, y2), "crop": crop,
                            "emb": embedder.histogram_embedding(crop, group)})
        out.append({"camera": cam_i, "time": day + timedelta(seconds=secs), "image": img, "objects": objects, "override": override})
    return out


def create_demo_case(db, user_id):
    """Writes the demo scenario to the database and links it with the normal clustering code."""
    from ..config import settings
    from ..models import Case, Evidence, Source, Track
    from .rebuild import rebuild_case
    import hashlib

    case = Case(title="DEMO: synthetic multi-camera incident",
                description="Synthetic scenario for demonstration. Scenes are drawn images, not real footage. "
                            "Two pedestrians and two cars move past four cameras; TraceLens links them by appearance, "
                            "time and travel distance.", created_by=user_id,
                incident_time=datetime.now().replace(hour=10, minute=0, second=0, microsecond=0))
    db.add(case)
    sources = []
    for c in CAMERAS:
        s = Source(name=c["name"], type=c["type"], lat=c["lat"], lng=c["lng"], notes="Demo camera")
        db.add(s)
        sources.append(s)
    db.flush()

    for sc in generate_scenes():
        name = f"{uuid.uuid4().hex}.png"
        path = settings.media_dir / "evidence" / name
        ok, buf = cv2.imencode(".png", sc["image"])
        path.write_bytes(buf.tobytes())
        lat, lng = sc["override"] if sc["override"] else (None, None)
        ev = Evidence(case_id=case.id, source_id=sources[sc["camera"]].id, filename=f"demo-{sc['time']:%H%M%S}-cam{sc['camera'] + 1}.png",
                      stored_name=name, media_type="image", size_bytes=len(buf), sha256=hashlib.sha256(buf.tobytes()).hexdigest(),
                      recorded_at=sc["time"], lat=lat, lng=lng, status="DONE", progress=100, uploaded_by=user_id,
                      notes="Synthetic demo image")
        db.add(ev)
        db.flush()
        small = cv2.resize(sc["image"], (480, 270))
        cv2.imwrite(str(settings.media_dir / "previews" / f"{ev.id}.jpg"), small)
        for i, o in enumerate(sc["objects"]):
            crop = o["crop"]
            h, w = crop.shape[:2]
            cv2.imwrite(str(settings.media_dir / "thumbs" / f"{ev.id}_{i}.jpg"), cv2.resize(crop, (max(1, int(w * 180 / h)), 180)))
            db.add(Track(evidence_id=ev.id, case_id=case.id, local_id=i, cls=o["cls"], group=o["group"], conf=0.9, n_det=1,
                         start_offset=0, end_offset=0, embedding=o["emb"].tolist(), has_thumb=True))
    db.commit()
    rebuild_case(db, case.id)
    return case
