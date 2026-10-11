"""Shared service layer exceptions and audit events."""
from __future__ import annotations
from uuid import uuid4
from fieldcraft.database import Database, utc_now


class NotFoundError(ValueError):
    pass


class ValidationError(ValueError):
    pass


class ConflictError(ValueError):
    pass


def new_id(prefix: str) -> str:
    return prefix + "-" + uuid4().hex[:12]


def audit(db: Database, tenant: str, kind: str, entity: str, status: str) -> None:
    # Deliberately avoids recording user content, tokens or sensitive payloads.
    with db.connection() as c:
        c.execute("""INSERT INTO audit_events(tenant_id,event_kind,entity_ref,status,occurred_at)
                     VALUES (?,?,?,?,?)""", (tenant, kind, entity, status, utc_now()))
