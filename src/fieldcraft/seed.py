"""Synthetic sample dataset for the standalone local demonstration."""
from __future__ import annotations
from .database import Database, utc_now


def seed(db: Database) -> None:
    with db.connection() as c:
        if c.execute("SELECT 1 FROM tenants WHERE id = 'north-demo'").fetchone():
            return
        c.executemany("INSERT INTO tenants (id,name) VALUES (?,?)", [
            ("north-demo", "Northstar Field Operations"),
            ("west-demo", "Westwind Contracting"),
        ])
        c.executemany("""INSERT INTO projects
            (id,tenant_id,name,trade,city,status,estimated_material_cents,actual_material_cents,notes)
            VALUES (?,?,?,?,?,?,?,?,?)""", [
            ("prj-cedar", "north-demo", "Cedar Residence", "roofing", "Austin", "active", 1450000, 1675000, "Complex pitch and tight access."),
            ("prj-orion", "north-demo", "Orion Warehouse", "roofing", "Dallas", "planning", 2250000, 1950000, "Large commercial roof with staged procurement."),
            ("prj-pine", "west-demo", "Pine Annex", "roofing", "Denver", "active", 995000, 820000, "Other tenant: must never appear in the Northstar demo."),
        ])
        c.executemany("INSERT INTO vendors (id,tenant_id,name) VALUES (?,?,?)", [
            ("vendor-main", "north-demo", "Sample Building Materials"),
            ("vendor-west", "west-demo", "Westwind Supply"),
        ])
        c.executemany("INSERT INTO tenant_uoms (tenant_id,code) VALUES (?,?)", [
            ("north-demo", "each"), ("north-demo", "bundle"),
            ("north-demo", "square"), ("north-demo", "linear_foot"),
            ("west-demo", "each"),
        ])
        date = utc_now()
        c.executemany("""INSERT INTO financial_records
            (id,tenant_id,project_id,kind,amount_cents,description,updated_at)
            VALUES (?,?,?,?,?,?,?)""", [
            ("fin-1", "north-demo", "prj-cedar", "expense", 42000, "Site transport", date),
            ("fin-2", "north-demo", "prj-cedar", "expense", 170000, "Supplier delivery", date),
            ("fin-3", "north-demo", "prj-orion", "bill", 920000, "Roof panels", date),
            ("fin-4", "west-demo", "prj-pine", "expense", 26000, "Site service", date),
        ])
        # An external-only ledger entry demonstrates reverse import (pull) without credentials.
        c.execute("""INSERT INTO remote_accounting_records
            (remote_id,tenant_id,external_key,project_id,kind,amount_cents,description,remote_version)
            VALUES (?,?,?,?,?,?,?,1)""",
            ("inbound-sample-01", "north-demo", "external-bill-sample", "prj-cedar",
             "bill", 32050, "Synthetic incoming supplier bill"))
        c.executemany("""INSERT INTO supplier_catalog
            (sku,branch_id,name,trade,supplier_uom,price_cents,available_to_order)
            VALUES (?,?,?,?,?,?,?)""", [
            ("SHINGLE-01", "branch-a", "Architectural shingles", "roofing", "BDL", 4350, 1),
            ("FLASH-02", "branch-a", "Aluminum flashing", "roofing", "LF", 320, 1),
            ("UNDERLAY-03", "branch-a", "Synthetic underlayment", "roofing", "SQ", 8100, 1),
            ("UNKNOWN-04", "branch-a", "Unmapped component", "roofing", "PALLET", 6000, 1),
            ("NOPRICE-05", "branch-a", "Special order item", "roofing", "EA", None, 1),
            ("SHINGLE-01", "branch-b", "Architectural shingles", "roofing", "BDL", 4490, 1),
            ("FLASH-02", "branch-b", "Aluminum flashing", "roofing", "LF", 330, 0),
        ])
