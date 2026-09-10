import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.services.storage import get_storage_service

logger = logging.getLogger("archive.health")
router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Public health endpoint. Reports only a boolean status per
    dependency -- no connection strings, hostnames, or credentials."""
    db_ok = False
    storage_ok = False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check: database unreachable: %s", type(exc).__name__)

    try:
        storage = get_storage_service()
        storage.exists("healthcheck/does-not-need-to-exist")
        storage_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check: storage unreachable: %s", type(exc).__name__)

    overall = "healthy" if (db_ok and storage_ok) else "degraded"
    return {"status": overall, "database": db_ok, "storage": storage_ok}
