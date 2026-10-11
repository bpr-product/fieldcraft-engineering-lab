"""SQLite-backed demo database. No external database or credentials required."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL, trade TEXT NOT NULL, city TEXT NOT NULL,
  status TEXT NOT NULL, estimated_material_cents INTEGER NOT NULL,
  actual_material_cents INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS vendors (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tenant_uoms (
  tenant_id TEXT NOT NULL REFERENCES tenants(id), code TEXT NOT NULL,
  PRIMARY KEY (tenant_id, code)
);
CREATE TABLE IF NOT EXISTS financial_records (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, description TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS remote_accounting_records (
  remote_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  external_key TEXT NOT NULL, project_id TEXT, kind TEXT NOT NULL,
  amount_cents INTEGER NOT NULL, description TEXT NOT NULL, remote_version INTEGER NOT NULL,
  UNIQUE (tenant_id, external_key)
);
CREATE TABLE IF NOT EXISTS external_mappings (
  tenant_id TEXT NOT NULL REFERENCES tenants(id), provider TEXT NOT NULL,
  entity_kind TEXT NOT NULL, local_id TEXT NOT NULL,
  remote_id TEXT NOT NULL, remote_version INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, provider, entity_kind, local_id),
  UNIQUE (tenant_id, provider, entity_kind, remote_id)
);
CREATE TABLE IF NOT EXISTS supplier_catalog (
  sku TEXT NOT NULL, branch_id TEXT NOT NULL, name TEXT NOT NULL,
  trade TEXT NOT NULL, supplier_uom TEXT NOT NULL,
  price_cents INTEGER, available_to_order INTEGER NOT NULL,
  PRIMARY KEY (sku, branch_id)
);
CREATE TABLE IF NOT EXISTS materials (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  vendor_id TEXT NOT NULL REFERENCES vendors(id),
  supplier_sku TEXT NOT NULL, name TEXT NOT NULL, trade TEXT NOT NULL,
  uom TEXT NOT NULL, unit_cost_cents INTEGER NOT NULL,
  UNIQUE (tenant_id, vendor_id, supplier_sku)
);
CREATE TABLE IF NOT EXISTS measurement_orders (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  provider_ref TEXT NOT NULL, status TEXT NOT NULL,
  report_json TEXT, requested_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  text TEXT NOT NULL, source_refs_json TEXT NOT NULL,
  payload_json TEXT NOT NULL, checksum TEXT NOT NULL,
  version INTEGER NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, project_id)
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  user_id TEXT NOT NULL, active_project_id TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
  user_id TEXT NOT NULL, topic TEXT NOT NULL, value TEXT NOT NULL,
  source_id TEXT NOT NULL, source_type TEXT NOT NULL,
  valid_from TEXT NOT NULL, valid_to TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(tenant_id, user_id, topic, valid_from);
CREATE TABLE IF NOT EXISTS memory_derivatives (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
  topic TEXT NOT NULL, originating_memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  derived_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id TEXT NOT NULL, event_kind TEXT NOT NULL,
  entity_ref TEXT NOT NULL, status TEXT NOT NULL, occurred_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def exists_tenant(self, tenant_id: str) -> bool:
        with self.connection() as conn:
            return conn.execute("SELECT 1 FROM tenants WHERE id = ?", (tenant_id,)).fetchone() is not None


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None
