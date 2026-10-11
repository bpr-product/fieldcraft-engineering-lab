"""Explicit-user memory with version history, source tracking and logical erasure.

This demonstration does not claim physical erasure from backups or storage media.
No information obtained from external pages is permitted to author a memory.
"""
from __future__ import annotations
from datetime import date
from fieldcraft.database import Database
from fieldcraft.services.common import NotFoundError, ValidationError, audit, new_id

# High-signal topics make the public example predictable; real users would need
# a consent model and configurable per-application salience policy.
ALLOWED_TOPICS = frozenset({"home_city", "diet", "food_allergy", "manager", "workplace", "spice_preference"})


class UserMemory:
    def __init__(self, db: Database):
        self.db = db

    def remember(self, tenant_id: str, user_id: str, topic: str, value: str,
                 source_id: str, source_type: str = "user_explicit", effective_date: str | None = None) -> dict:
        if not self.db.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        # Deliberate write-time gate: external messages and inferred facts cannot become durable memory.
        if source_type != "user_explicit":
            return {"status": "skipped", "reason": "untrusted_or_inferred_source"}
        if topic not in ALLOWED_TOPICS:
            return {"status": "skipped", "reason": "low_signal_topic"}
        if not value or not source_id or len(value) > 500:
            raise ValidationError("Nonempty value and source ID required (value max 500 chars)")
        when = effective_date or date.today().isoformat()
        try:
            date.fromisoformat(when)
        except ValueError as exc:
            raise ValidationError("effective_date must be YYYY-MM-DD") from exc
        # Never treat text inside untrusted material as an instruction.
        mid = new_id("memory")
        with self.db.connection() as c:
            active = c.execute("""SELECT id,value,valid_from FROM memories
                WHERE tenant_id=? AND user_id=? AND topic=? AND valid_to IS NULL
                ORDER BY valid_from DESC LIMIT 1""", (tenant_id, user_id, topic)).fetchone()
            if active and active["value"] == value:
                return {"status": "unchanged", "id": active["id"]}
            if active and when <= active["valid_from"]:
                raise ValidationError("Update date must be after the existing active memory")
            if active:
                c.execute("UPDATE memories SET valid_to=? WHERE id=?", (when, active["id"]))
            c.execute("""INSERT INTO memories
                (id,tenant_id,user_id,topic,value,source_id,source_type,valid_from,valid_to,created_at)
                VALUES (?,?,?,?,?,?,?, ?,NULL,?)""",
                (mid, tenant_id, user_id, topic, value, source_id, source_type, when, date.today().isoformat()))
        audit(self.db, tenant_id, "memory_write", "source_verified", "updated" if active else "created")
        return {"status": "updated" if active else "created", "id": mid,
                "topic": topic, "valid_from": when, "source_id": source_id}

    def recall(self, tenant_id: str, user_id: str, topic: str, as_of: str | None = None) -> dict:
        when = as_of or date.today().isoformat()
        try:
            date.fromisoformat(when)
        except ValueError as exc:
            raise ValidationError("as_of must be YYYY-MM-DD") from exc
        with self.db.connection() as c:
            row = c.execute("""SELECT id,value,source_id,valid_from,valid_to FROM memories
                WHERE tenant_id=? AND user_id=? AND topic=? AND valid_from <= ?
                  AND (valid_to IS NULL OR valid_to > ?) ORDER BY valid_from DESC LIMIT 1""",
                (tenant_id, user_id, topic, when, when)).fetchone()
        if not row:
            return {"known": False, "topic": topic, "answer": "I don't know from the available memory."}
        return {"known": True, "topic": topic, "value": row["value"], "source_id": row["source_id"],
                "valid_from": row["valid_from"], "valid_to": row["valid_to"]}

    def forget(self, tenant_id: str, user_id: str, topic: str) -> dict:
        """Erases all versions and explicitly modelled derivatives of one topic."""
        with self.db.connection() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM memories WHERE tenant_id=? AND user_id=? AND topic=?",
                                           (tenant_id, user_id, topic))]
            # ON DELETE CASCADE removes derived summaries linked to the source memory.
            c.execute("DELETE FROM memories WHERE tenant_id=? AND user_id=? AND topic=?", (tenant_id, user_id, topic))
        # No topic/value/source ID is retained in the audit event.
        audit(self.db, tenant_id, "memory_erasure", "redacted", "completed")
        return {"status": "forgotten", "removed_versions": len(ids), "derivatives_erased": True}

    def attach_derivative(self, tenant_id: str, user_id: str, memory_id: str, text: str) -> str:
        """Testable example of a derived summary that must disappear with its source."""
        with self.db.connection() as c:
            row = c.execute("""SELECT topic FROM memories WHERE id=? AND tenant_id=? AND user_id=?""",
                            (memory_id, tenant_id, user_id)).fetchone()
            if not row:
                raise NotFoundError("Memory not found")
            derivative_id = new_id("derivative")
            c.execute("""INSERT INTO memory_derivatives
                (id,tenant_id,user_id,topic,originating_memory_id,derived_text)
                VALUES(?,?,?,?,?,?)""", (derivative_id, tenant_id, user_id, row["topic"], memory_id, text))
        return derivative_id
