"""Add an investigator account:  python -m app.create_user someone@example.com "S3cretPass" "Full Name" """
import sys

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import User
from .security import hash_password

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit('usage: python -m app.create_user EMAIL PASSWORD "FULL NAME"')
    email, password, name = sys.argv[1].strip().lower(), sys.argv[2], sys.argv[3]
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit("That email already exists")
        db.add(User(email=email, name=name, password_hash=hash_password(password)))
        db.commit()
        print("created", email)
