"""Supplier catalog and safe, validated import into tenant-owned material records.

No real supplier account, inventory level or purchase order is represented here.
"""
from __future__ import annotations
from fieldcraft.database import Database
from .common import NotFoundError, audit, new_id

UOM_MAP = {"EA": "each", "BDL": "bundle", "SQ": "square", "LF": "linear_foot"}


class SupplierBridge:
    def __init__(self, db: Database):
        self.db = db

    def search(self, tenant_id: str, query: str = "", branch_id: str = "branch-a") -> list[dict]:
        if not self.db.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        with self.db.connection() as c:
            return [dict(r) for r in c.execute("""SELECT sku,branch_id,name,trade,supplier_uom,
                price_cents,available_to_order FROM supplier_catalog
                WHERE branch_id=? AND (lower(name) LIKE ? OR lower(sku) LIKE ?) ORDER BY sku LIMIT 100""",
                (branch_id, "%" + query.lower() + "%", "%" + query.lower() + "%"))]

    def import_materials(self, tenant_id: str, vendor_id: str, skus: list[str], branch_id: str = "branch-a") -> dict:
        with self.db.connection() as c:
            vendor = c.execute("SELECT id FROM vendors WHERE id=? AND tenant_id=?", (vendor_id, tenant_id)).fetchone()
            if not vendor:
                raise NotFoundError("Vendor not found for workspace")
            valid_uoms = {r[0] for r in c.execute("SELECT code FROM tenant_uoms WHERE tenant_id=?", (tenant_id,))}

        rows = []
        seen = set()
        for sku in skus:
            if sku in seen:
                rows.append({"sku": sku, "status": "skipped", "reason": "duplicate_in_request"})
                continue
            seen.add(sku)
            with self.db.connection() as c:
                item = c.execute("SELECT * FROM supplier_catalog WHERE sku=? AND branch_id=?",
                                 (sku, branch_id)).fetchone()
                reason = None
                if item is None:
                    reason = "unknown_item"
                elif item["price_cents"] is None or item["price_cents"] <= 0:
                    reason = "missing_price"
                elif not item["available_to_order"]:
                    reason = "not_available_to_order"
                elif item["supplier_uom"] not in UOM_MAP:
                    reason = "unmapped_uom"
                elif UOM_MAP[item["supplier_uom"]] not in valid_uoms:
                    reason = "uom_not_enabled_for_workspace"
                elif c.execute("""SELECT 1 FROM materials WHERE tenant_id=? AND vendor_id=?
                     AND supplier_sku=?""", (tenant_id, vendor_id, sku)).fetchone():
                    reason = "already_imported"
                if reason:
                    rows.append({"sku": sku, "status": "skipped", "reason": reason})
                    continue
                material_id = new_id("mat")
                c.execute("""INSERT INTO materials
                    (id,tenant_id,vendor_id,supplier_sku,name,trade,uom,unit_cost_cents)
                    VALUES(?,?,?,?,?,?,?,?)""", (material_id, tenant_id, vendor_id, sku,
                                                   item["name"], item["trade"],
                                                   UOM_MAP[item["supplier_uom"]], item["price_cents"]))
                rows.append({"sku": sku, "status": "added", "material_id": material_id})
        audit(self.db, tenant_id, "material_import", vendor_id, "processed")
        return {"provider_mode": "synthetic", "items": rows,
                "added": sum(r["status"] == "added" for r in rows),
                "skipped": sum(r["status"] == "skipped" for r in rows)}

    def list_materials(self, tenant_id: str) -> list[dict]:
        with self.db.connection() as c:
            return [dict(r) for r in c.execute("""SELECT id,vendor_id,supplier_sku,name,trade,uom,unit_cost_cents
                FROM materials WHERE tenant_id=? ORDER BY supplier_sku""", (tenant_id,))]
