"""Idempotent, bidirectional accounting synchronization against a local mock ledger.

Demonstrates stable external IDs, version-based concurrency, reconciliation and
per-record status. No real financial provider is contacted.
"""
from __future__ import annotations

from fieldcraft.database import Database, row_dict, utc_now
from .common import ConflictError, NotFoundError, ValidationError, audit, new_id

PROVIDER = "demo-ledger"


class AccountingBridge:
    def __init__(self, db: Database):
        self.db = db

    def sync(self, tenant_id: str) -> dict:
        if not self.db.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        with self.db.connection() as conn:
            records = [dict(r) for r in conn.execute(
                "SELECT * FROM financial_records WHERE tenant_id = ? ORDER BY id", (tenant_id,)
            )]
        results = []
        for record in records:
            try:
                result = self.push_one(tenant_id, record["id"])
            except ConflictError as exc:
                result = {"record_id": record["id"], "status": "conflict", "reason": str(exc)}
            results.append(result)
        return {"tenant_id": tenant_id, "provider_mode": "synthetic", "records": results,
                "created": sum(r["status"] == "created" for r in results),
                "updated": sum(r["status"] == "updated" for r in results),
                "unchanged": sum(r["status"] == "unchanged" for r in results),
                "conflicts": sum(r["status"] == "conflict" for r in results)}

    def push_one(self, tenant_id: str, record_id: str) -> dict:
        with self.db.connection() as c:
            local = c.execute("SELECT * FROM financial_records WHERE tenant_id=? AND id=?",
                              (tenant_id, record_id)).fetchone()
            if local is None:
                raise NotFoundError("Financial record not found for workspace")
            mapping = c.execute("""SELECT * FROM external_mappings WHERE tenant_id=?
                AND provider=? AND entity_kind='finance' AND local_id=?""",
                (tenant_id, PROVIDER, record_id)).fetchone()
            if mapping is None:
                # external_key is the stable local id. UNIQUE constraints also guard repeats.
                remote_id = new_id("ledger")
                c.execute("""INSERT INTO remote_accounting_records
                    (remote_id,tenant_id,external_key,project_id,kind,amount_cents,description,remote_version)
                    VALUES(?,?,?,?,?,?,?,1)""",
                    (remote_id, tenant_id, record_id, local["project_id"], local["kind"],
                     local["amount_cents"], local["description"]))
                c.execute("""INSERT INTO external_mappings
                    (tenant_id,provider,entity_kind,local_id,remote_id,remote_version,updated_at)
                    VALUES (?,?, 'finance',?,?,1,?)""",
                    (tenant_id, PROVIDER, record_id, remote_id, utc_now()))
                result = {"record_id": record_id, "remote_id": remote_id, "status": "created", "version": 1}
            else:
                remote = c.execute("SELECT * FROM remote_accounting_records WHERE tenant_id=? AND remote_id=?",
                                   (tenant_id, mapping["remote_id"])).fetchone()
                if remote is None:
                    raise ConflictError("Mapped remote record no longer exists; reconcile before retrying")
                if remote["remote_version"] != mapping["remote_version"]:
                    raise ConflictError("Remote version changed; refresh mapping before updating")
                if all(remote[key] == local[key] for key in ("kind", "amount_cents", "description", "project_id")):
                    result = {"record_id": record_id, "remote_id": mapping["remote_id"],
                              "status": "unchanged", "version": remote["remote_version"]}
                else:
                    next_version = remote["remote_version"] + 1
                    c.execute("""UPDATE remote_accounting_records
                        SET project_id=?,kind=?,amount_cents=?,description=?,remote_version=?
                        WHERE tenant_id=? AND remote_id=?""",
                        (local["project_id"], local["kind"], local["amount_cents"],
                         local["description"], next_version, tenant_id, mapping["remote_id"]))
                    c.execute("""UPDATE external_mappings SET remote_version=?, updated_at=?
                        WHERE tenant_id=? AND provider=? AND entity_kind='finance' AND local_id=?""",
                        (next_version, utc_now(), tenant_id, PROVIDER, record_id))
                    result = {"record_id": record_id, "remote_id": mapping["remote_id"],
                              "status": "updated", "version": next_version}
        audit(self.db, tenant_id, "accounting_sync", record_id, result["status"])
        return result

    def import_external(self, tenant_id: str, remote_id: str) -> dict:
        """Import an existing mock-ledger record, avoiding duplicate local records."""
        with self.db.connection() as c:
            remote = c.execute("SELECT * FROM remote_accounting_records WHERE tenant_id=? AND remote_id=?",
                               (tenant_id, remote_id)).fetchone()
            if remote is None:
                raise NotFoundError("Remote record not found")
            mapping = c.execute("""SELECT local_id FROM external_mappings WHERE tenant_id=?
                AND provider=? AND entity_kind='finance' AND remote_id=?""", (tenant_id, PROVIDER, remote_id)).fetchone()
            if mapping:
                return {"status": "already_imported", "record_id": mapping["local_id"]}
            project = c.execute("SELECT id FROM projects WHERE id=? AND tenant_id=?",
                                (remote["project_id"], tenant_id)).fetchone()
            if not project:
                raise ValidationError("Remote project does not map to this workspace")
            local_id = new_id("fin")
            c.execute("""INSERT INTO financial_records
                (id,tenant_id,project_id,kind,amount_cents,description,updated_at)
                VALUES (?,?,?,?,?,?,?)""",
                (local_id, tenant_id, remote["project_id"], remote["kind"],
                 remote["amount_cents"], remote["description"], utc_now()))
            c.execute("""INSERT INTO external_mappings
                (tenant_id,provider,entity_kind,local_id,remote_id,remote_version,updated_at)
                VALUES (?,?, 'finance',?,?,?,?)""", (tenant_id, PROVIDER, local_id, remote_id,
                                                        remote["remote_version"], utc_now()))
        audit(self.db, tenant_id, "accounting_pull", local_id, "created")
        return {"status": "created", "record_id": local_id}

    def simulate_remote_change(self, tenant_id: str, record_id: str, amount_cents: int) -> None:
        """Test-only helper to demonstrate optimistic concurrency conflicts."""
        with self.db.connection() as c:
            mapping = c.execute("""SELECT remote_id FROM external_mappings WHERE tenant_id=?
                AND provider=? AND entity_kind='finance' AND local_id=?""",
                (tenant_id, PROVIDER, record_id)).fetchone()
            if not mapping:
                raise NotFoundError("Sync record once before simulating a remote change")
            c.execute("""UPDATE remote_accounting_records SET amount_cents=?, remote_version=remote_version+1
                WHERE tenant_id=? AND remote_id=?""", (amount_cents, tenant_id, mapping["remote_id"]))

    def mappings(self, tenant_id: str) -> list[dict]:
        with self.db.connection() as c:
            return [dict(r) for r in c.execute("""SELECT entity_kind,local_id,remote_id,remote_version,updated_at
                FROM external_mappings WHERE tenant_id=? AND provider=? ORDER BY local_id""",
                (tenant_id, PROVIDER))]
