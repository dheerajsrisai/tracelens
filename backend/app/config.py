import os
from pathlib import Path


class Settings:
    # --- infrastructure ---
    database_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://tracelens:tracelens@localhost:5432/tracelens")
    media_dir = Path(os.getenv("MEDIA_DIR", "media"))
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "1024"))

    # --- security ---
    jwt_secret = os.getenv("JWT_SECRET", "change-this-tracelens-secret-key-before-deploying-2024")
    jwt_hours = int(os.getenv("JWT_HOURS", "12"))
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    admin_email = os.getenv("ADMIN_EMAIL", "admin@tracelens.ai")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    # --- detection / tracking (YOLO11 + ByteTrack) ---
    yolo_model = os.getenv("YOLO_MODEL", "yolo11n.pt")          # yolo11s.pt / yolo11m.pt = more accurate, slower
    frame_stride = int(os.getenv("FRAME_STRIDE", "3"))           # analyse every Nth video frame
    det_conf = float(os.getenv("DET_CONF", "0.30"))
    imgsz = int(os.getenv("IMGSZ", "640"))
    min_detections = int(os.getenv("MIN_DETECTIONS", "3"))       # drop very short, noisy tracks (videos only)

    # --- cross-camera matching ---
    embedder = os.getenv("EMBEDDER", "histogram")                # histogram | resnet (experimental)
    match_threshold = float(os.getenv("MATCH_THRESHOLD", "0.75"))
    person_max_speed = float(os.getenv("PERSON_MAX_SPEED_MS", "7"))    # m/s, used for travel-time plausibility
    vehicle_max_speed = float(os.getenv("VEHICLE_MAX_SPEED_MS", "35"))
    same_place_m = float(os.getenv("SAME_PLACE_M", "30"))        # cameras closer than this "see the same spot"


settings = Settings()
settings.media_dir.mkdir(parents=True, exist_ok=True)
for sub in ("evidence", "thumbs", "previews"):
    (settings.media_dir / sub).mkdir(exist_ok=True)
