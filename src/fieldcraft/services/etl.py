"""Repeatable relational-to-document transformation with source lineage and versions.

Documents are built from scoped synthetic operational records, not sensitive data.
"""
from __future__ import annotations
from hashlib import sha256
import json
from fieldcraft.database import Database, utc_now
from .common import NotFoundError, audit


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class DocumentPipeline:
    def __init__(self, db: Database):
        self.db = db

    def refresh(self, tenant_id: str) -> dict:
        if not self.db.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        with self.db.connection() as c:
            project_ids = [r[0] for r in c.execute("SELECT id FROM projects WHERE tenant_id=? ORDER BY id", (tenant_id,))]
        results = [self.refresh_one(tenant_id, project_id) for project_id in project_ids]
        audit(self.db, tenant_id, "document_refresh", "workspace", "completed")
        return {"documents": results, "created": sum(x["status"] == "created" for x in results),
                "updated": sum(x["status"] == "updated" for x in results),
                "unchanged": sum(x["status"] == "unchanged" for x in results)}

    def refresh_one(self, tenant_id: str, project_id: str) -> dict:
        with self.db.connection() as c:
            project = c.execute("SELECT * FROM projects WHERE tenant_id=? AND id=?",
                                (tenant_id, project_id)).fetchone()
            if not project:
                raise NotFoundError("Project not found for workspace")
            financial = [dict(x) for x in c.execute("""SELECT id,kind,amount_cents,description FROM financial_records
                WHERE tenant_id=? AND project_id=? ORDER BY id""", (tenant_id, project_id))]
            material_list = [dict(x) for x in c.execute("""SELECT id,name,unit_cost_cents,uom FROM materials
                WHERE tenant_id=? ORDER BY id""", (tenant_id,))]
            orders = [dict(x) for x in c.execute("""SELECT id,status,report_json FROM measurement_orders
                WHERE tenant_id=? AND project_id=? ORDER BY id""", (tenant_id, project_id))]
            sources = [f"project:{project_id}"] + [f"financial:{r['id']}" for r in financial]
            sources += [f"material:{r['id']}" for r in material_list]
            sources += [f"measurement:{r['id']}" for r in orders]
            payload = {
                "project": {"id": project["id"], "name": project["name"], "trade": project["trade"],
                            "city": project["city"], "status": project["status"], "notes": project["notes"],
                            "estimated_material_cents": project["estimated_material_cents"],
                            "actual_material_cents": project["actual_material_cents"]},
                "financial": financial,
                "workspace_materials": material_list,
                "measurements": [{"id": r["id"], "status": r["status"],
                                  "report": json.loads(r["report_json"]) if r["report_json"] else None} for r in orders],
            }
            text_parts = [
                f"Project {project['name']} ({project['id']}) is a {project['trade']} job in {project['city']}.",
                f"Status: {project['status']}. Notes: {project['notes']}",
                f"Estimated material cost: {project['estimated_material_cents']} cents. "
                f"Actual material cost: {project['actual_material_cents']} cents.",
            ]
            for f in financial:
                text_parts.append(f"{f['kind']} {f['id']}: {f['description']}, amount {f['amount_cents']} cents.")
            if material_list:
                text_parts.append("Available workspace material records: " + ", ".join(m["name"] for m in material_list))
            for order in payload["measurements"]:
                if order["report"]:
                    text_parts.append(f"Measurement for {project['name']}: {order['report']}")
            text = "\n".join(text_parts)
            digest = sha256(_canonical(payload).encode()).hexdigest()
            doc_id = f"doc-{project_id}"
            old = c.execute("SELECT checksum,version FROM documents WHERE id=? AND tenant_id=?",
                            (doc_id, tenant_id)).fetchone()
            if old and old["checksum"] == digest:
                return {"id": doc_id, "project_id": project_id, "status": "unchanged", "version": old["version"]}
            version = (old["version"] + 1) if old else 1
            c.execute("""INSERT INTO documents
                (id,tenant_id,project_id,text,source_refs_json,payload_json,checksum,version,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET text=excluded.text,
                source_refs_json=excluded.source_refs_json,payload_json=excluded.payload_json,
                checksum=excluded.checksum,version=excluded.version,updated_at=excluded.updated_at""",
                (doc_id, tenant_id, project_id, text, _canonical({"sources": sources}),
                 _canonical(payload), digest, version, utc_now()))
        return {"id": doc_id, "project_id": project_id,
                "status": "updated" if old else "created", "version": version}

    def list_documents(self, tenant_id: str) -> list[dict]:
        with self.db.connection() as c:
            return [{"id": r["id"], "project_id": r["project_id"], "version": r["version"],
                     "sources": json.loads(r["source_refs_json"])["sources"], "text": r["text"]}
                    for r in c.execute("""SELECT id,project_id,version,text,source_refs_json
                        FROM documents WHERE tenant_id=? ORDER BY project_id""", (tenant_id,))]
