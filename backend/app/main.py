import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import select, text

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Evidence, User
from .routers import auth, cameras, cases, entities, evidence
from .security import current_user, hash_password
from .services.pipeline import enqueue

log = logging.getLogger("tracelens")
logging.basicConfig(level=logging.INFO)


def wait_for_db(retries: int = 40):
    for i in range(retries):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as exc:
            log.info("Waiting for the database (%s/%s): %s", i + 1, retries, exc.__class__.__name__)
            time.sleep(2)
    raise RuntimeError("Database is not reachable")


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == settings.admin_email)):
            db.add(User(email=settings.admin_email, name="Administrator", password_hash=hash_password(settings.admin_password)))
            db.commit()
            print(f">> Default investigator created: {settings.admin_email} / {settings.admin_password}")
        # resume work interrupted by a restart
        for ev in db.scalars(select(Evidence).where(Evidence.status.in_(["PENDING", "PROCESSING"]))):
            ev.status = "PENDING"
            enqueue(ev.id)
        db.commit()
    yield


app = FastAPI(title="TraceLens AI", lifespan=lifespan)

api = APIRouter(prefix="/api")
api.include_router(auth.router)
protected = [Depends(current_user)]
api.include_router(cameras.router)
api.include_router(cases.router)
api.include_router(evidence.router)
api.include_router(entities.router)


@api.get("/health")
def health():
    return {"status": "ok", "model": settings.yolo_model, "embedder": settings.embedder}


app.include_router(api)
