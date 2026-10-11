"""Execute five synthetic services from the command line; no keys required."""
from pathlib import Path
import tempfile
from fieldcraft.database import Database
from fieldcraft.seed import seed
from fieldcraft.services.accounting import AccountingBridge
from fieldcraft.services.supplier import SupplierBridge
from fieldcraft.services.measurement import MeasurementFlow
from fieldcraft.services.etl import DocumentPipeline
from fieldcraft.ai.assistant import ContextPilot
from fieldcraft.ai.memory import UserMemory

with tempfile.TemporaryDirectory(prefix="fieldcraft-") as temp:
    db = Database(Path(temp) / "example.sqlite3")
    seed(db)
    tenant = "north-demo"
    print("1. Accounting sync", AccountingBridge(db).sync(tenant))
    print("2. Supplier import", SupplierBridge(db).import_materials(tenant, "vendor-main", ["SHINGLE-01", "NOPRICE-05"]))
    measures = MeasurementFlow(db)
    order = measures.request(tenant, "prj-cedar")
    print("3. Measurement report", measures.ingest(tenant, order["id"], {
        "roof_area_sqft": 2720, "roof_pitch_ratio": 0.33, "facet_count": 8,
    }))
    print("4. Document refresh", DocumentPipeline(db).refresh(tenant))
    print("5. Assistant", ContextPilot(db).ask(tenant, "demo-user", "session-demo", "Why did Cedar Residence exceed material cost?"))
    print("6. Explicit memory", UserMemory(db).remember(tenant, "demo-user", "diet", "vegetarian", "demo-conversation-001"))
