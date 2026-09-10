"""Promote a user to admin by email.

Usage: uv run python scripts/promote_admin.py EMAIL

This script connects to the database configured via the DATABASE_URL
environment variable (read by mvp.backend.config.Settings). In the Docker
container you MUST set DATABASE_URL (e.g. sqlite:////data/joaxx.db), otherwise
it falls back to the default ./joaxx.db relative to the current working
directory, which is NOT the volume-mounted database.
"""
import os
import sys

from sqlalchemy import select

from mvp.backend.database import SessionLocal
from mvp.backend.models import User


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/promote_admin.py EMAIL", file=sys.stderr)
        print(
            "NOTE: Set DATABASE_URL (e.g. sqlite:////data/joaxx.db) to target the "
            "correct database; without it, the default ./joaxx.db is used.",
            file=sys.stderr,
        )
        return 2
    if not os.environ.get("DATABASE_URL"):
        print(
            "WARNING: DATABASE_URL is not set; using the default ./joaxx.db "
            "(in the container, set DATABASE_URL=sqlite:////data/joaxx.db).",
            file=sys.stderr,
        )
    email = sys.argv[1]
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            print(f"User not found: {email}", file=sys.stderr)
            return 1
        user.is_admin = True
        db.commit()
        print(f"Promoted {email} to admin")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())