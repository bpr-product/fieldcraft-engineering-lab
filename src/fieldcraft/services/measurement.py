"""External measurement report ordering and ingestion, implemented as an offline demo.

Project-specific orders have explicit states and validated report inputs.
"""
from __future__ import annotations
import json
import math
from fieldcraft.database import Database, utc_now
from .common import ConflictError, NotFoundError, ValidationError, audit, new_id


class MeasurementFlow:
    def __init__(self, db: Database):
        self.db = db

    def request(self, tenant_id: str, project_id: str) -> dict:
        with self.db.connection() as c:
            if not c.execute("SELECT 1 FROM projects WHERE tenant_id=? AND id=?", (tenant_id, project_id)).fetchone():
                raise NotFoundError("Project not found for workspace")
            oid = new_id("measure")
            provider_ref = new_id("demo-report")
            now = utc_now()
            c.execute("""INSERT INTO measurement_orders
                (id,tenant_id,project_id,provider_ref,status,report_json,requested_at,updated_at)
                VALUES(?,?,?,?, 'requested',NULL,?,?)""",
                (oid, tenant_id, project_id, provider_ref, now, now))
        audit(self.db, tenant_id, "measurement_order", oid, "requested")
        return {"id": oid, "project_id": project_id, "provider_ref": provider_ref, "status": "requested"}

    def move_status(self, tenant_id: str, order_id: str, new_status: str) -> dict:
        allowed = {"requested": {"processing", "cancelled"}, "processing": {"cancelled"},
                   "completed": set(), "cancelled": set()}
        with self.db.connection() as c:
            row = c.execute("SELECT status FROM measurement_orders WHERE tenant_id=? AND id=?",
                            (tenant_id, order_id)).fetchone()
            if not row:
                raise NotFoundError("Measurement order not found")
            if new_status not in allowed[row["status"]]:
                raise ConflictError(f"Invalid measurement transition: {row['status']} -> {new_status}")
            c.execute("UPDATE measurement_orders SET status=?,updated_at=? WHERE tenant_id=? AND id=?",
                      (new_status, utc_now(), tenant_id, order_id))
        audit(self.db, tenant_id, "measurement_status", order_id, new_status)
        return {"id": order_id, "status": new_status}

    def ingest(self, tenant_id: str, order_id: str, report: dict) -> dict:
        try:
            area = float(report["roof_area_sqft"])
            pitch = float(report["roof_pitch_ratio"])
            facets = int(report["facet_count"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError("Report requires roof_area_sqft, roof_pitch_ratio and facet_count") from exc
        if not (math.isfinite(area) and math.isfinite(pitch) and area > 0 and 0 <= pitch <= 2 and 1 <= facets <= 10000):
            raise ValidationError("Invalid measurement values")
        normalized = {"roof_area_sqft": round(area, 2), "roof_pitch_ratio": round(pitch, 3),
                      "facet_count": facets, "report_kind": "synthetic_roof_measurement"}
        with self.db.connection() as c:
            row = c.execute("SELECT status FROM measurement_orders WHERE tenant_id=? AND id=?",
                            (tenant_id, order_id)).fetchone()
            if not row:
                raise NotFoundError("Measurement order not found")
            if row["status"] in ("cancelled", "completed"):
                raise ConflictError("Cannot ingest report for a closed order")
            c.execute("""UPDATE measurement_orders SET status='completed',report_json=?,updated_at=?
                WHERE tenant_id=? AND id=?""", (json.dumps(normalized), utc_now(), tenant_id, order_id))
        audit(self.db, tenant_id, "measurement_ingest", order_id, "completed")
        return {"id": order_id, "status": "completed", "report": normalized}

    def list_orders(self, tenant_id: str) -> list[dict]:
        with self.db.connection() as c:
            results = [dict(r) for r in c.execute("""SELECT id,project_id,provider_ref,status,report_json,updated_at
                FROM measurement_orders WHERE tenant_id=? ORDER BY requested_at DESC""", (tenant_id,))]
        for r in results:
            r["report"] = json.loads(r.pop("report_json")) if r["report_json"] else None
        return results
