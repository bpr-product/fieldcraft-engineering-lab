"""Demo HTTP interface. For local educational use only; no authentication layer.

All provider interactions and data are synthetic by default. Do not deploy
unprotected to the public internet or attach real customer records.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from fieldcraft.database import Database
from fieldcraft.seed import seed
from fieldcraft.services.accounting import AccountingBridge
from fieldcraft.services.supplier import SupplierBridge
from fieldcraft.services.measurement import MeasurementFlow
from fieldcraft.services.etl import DocumentPipeline
from fieldcraft.services.common import ConflictError, NotFoundError, ValidationError
from fieldcraft.ai.assistant import ContextPilot
from fieldcraft.ai.memory import UserMemory, ALLOWED_TOPICS

ROOT = Path(__file__).resolve().parents[2]


class WorkspaceRequest(BaseModel):
    tenant_id: str = "north-demo"


class PullRequest(WorkspaceRequest):
    remote_id: str = "inbound-sample-01"


class MockRemoteChange(WorkspaceRequest):
    record_id: str = "fin-1"
    amount_cents: int = Field(ge=0)


class ImportRequest(WorkspaceRequest):
    vendor_id: str = "vendor-main"
    branch_id: str = "branch-a"
    skus: list[str] = Field(min_length=1, max_length=100)


class MeasurementRequest(WorkspaceRequest):
    project_id: str = "prj-cedar"


class MeasurementStatus(WorkspaceRequest):
    status: Literal["processing", "cancelled"]


class MeasurementReport(WorkspaceRequest):
    roof_area_sqft: float = Field(gt=0, allow_inf_nan=False)
    roof_pitch_ratio: float = Field(ge=0, le=2, allow_inf_nan=False)
    facet_count: int = Field(ge=1, le=10000)


class AskRequest(WorkspaceRequest):
    user_id: str = "demo-user"
    session_id: str = "session-demo"
    question: str = Field(min_length=1, max_length=1000)
    active_project_id: str | None = None


class RememberRequest(WorkspaceRequest):
    user_id: str = "demo-user"
    topic: str
    value: str
    source_id: str
    source_type: str = "user_explicit"
    effective_date: str | None = None


class ForgetRequest(WorkspaceRequest):
    user_id: str = "demo-user"
    topic: str


def create_app(db: Database | None = None) -> FastAPI:
    storage = db or Database(os.getenv("FIELDCRAFT_DB", str(ROOT / "data" / "fieldcraft.sqlite3")))
    seed(storage)
    accounting = AccountingBridge(storage)
    supplier = SupplierBridge(storage)
    measurements = MeasurementFlow(storage)
    pipeline = DocumentPipeline(storage)
    assistant = ContextPilot(storage)
    memory = UserMemory(storage)

    app = FastAPI(title="FieldCraft Engineering Lab", version="0.1.0",
                  description="Independent portfolio example using entirely synthetic operational data")
    app.mount("/assets", StaticFiles(directory=str(ROOT / "ui")), name="assets")

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict(_: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation(_: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid_input(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "ui" / "index.html")

    @app.get("/api/overview")
    def overview(tenant_id: str = "north-demo"):
        if not storage.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        with storage.connection() as c:
            counts = {}
            for table in ("projects", "financial_records", "materials", "measurement_orders", "documents"):
                counts[table] = c.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
            projects = [dict(p) for p in c.execute("""SELECT id,name,city,trade,status,estimated_material_cents,
                actual_material_cents FROM projects WHERE tenant_id=? ORDER BY name""", (tenant_id,))]
            event_rows = [dict(e) for e in c.execute("""SELECT event_kind,entity_ref,status,occurred_at
                FROM audit_events WHERE tenant_id=? ORDER BY id DESC LIMIT 8""", (tenant_id,))]
        return {"project_count": counts["projects"], "metrics": counts, "projects": projects,
                "recent_events": event_rows, "model_mode": "configured_llm" if assistant.model.configured else "offline_evidence_only",
                "providers": "synthetic_only", "security": "local_demo_only"}

    @app.post("/api/accounting/sync")
    def sync_accounting(req: WorkspaceRequest):
        return accounting.sync(req.tenant_id)

    @app.post("/api/accounting/pull")
    def pull_accounting(req: PullRequest):
        return accounting.import_external(req.tenant_id, req.remote_id)

    @app.post("/api/accounting/mock-external-change")
    def mock_external_change(req: MockRemoteChange):
        accounting.simulate_remote_change(req.tenant_id, req.record_id, req.amount_cents)
        return {"status": "mock_remote_changed", "record_id": req.record_id,
                "next_step": "Run accounting sync to observe an optimistic concurrency conflict"}

    @app.get("/api/accounting/mappings")
    def mappings(tenant_id: str = "north-demo"):
        return accounting.mappings(tenant_id)

    @app.get("/api/supplier/search")
    def search_supplier(tenant_id: str = "north-demo", q: str = "", branch_id: str = "branch-a"):
        return {"items": supplier.search(tenant_id, q, branch_id), "availability_meaning": "can_order_not_physical_inventory"}

    @app.post("/api/supplier/import")
    def import_materials(req: ImportRequest):
        return supplier.import_materials(req.tenant_id, req.vendor_id, req.skus, req.branch_id)

    @app.get("/api/supplier/imported")
    def list_materials(tenant_id: str = "north-demo"):
        return supplier.list_materials(tenant_id)

    @app.post("/api/measurements/orders")
    def order_measurement(req: MeasurementRequest):
        return measurements.request(req.tenant_id, req.project_id)

    @app.post("/api/measurements/orders/{order_id}/status")
    def measurement_status(order_id: str, req: MeasurementStatus):
        return measurements.move_status(req.tenant_id, order_id, req.status)

    @app.post("/api/measurements/orders/{order_id}/ingest")
    def ingest_measurement(order_id: str, req: MeasurementReport):
        return measurements.ingest(req.tenant_id, order_id, req.model_dump(exclude={"tenant_id"}))

    @app.get("/api/measurements/orders")
    def list_orders(tenant_id: str = "north-demo"):
        return measurements.list_orders(tenant_id)

    @app.post("/api/documents/refresh")
    def refresh_documents(req: WorkspaceRequest):
        return pipeline.refresh(req.tenant_id)

    @app.get("/api/documents")
    def get_documents(tenant_id: str = "north-demo"):
        return pipeline.list_documents(tenant_id)

    @app.post("/api/assistant/ask")
    def ask(req: AskRequest):
        return assistant.ask(req.tenant_id, req.user_id, req.session_id, req.question, req.active_project_id)

    @app.get("/api/memory/topics")
    def topics():
        return {"topics": sorted(ALLOWED_TOPICS), "policy": "explicit_user_only"}

    @app.post("/api/memory/write")
    def remember(req: RememberRequest):
        return memory.remember(req.tenant_id, req.user_id, req.topic, req.value,
                               req.source_id, req.source_type, req.effective_date)

    @app.get("/api/memory/recall")
    def recall(tenant_id: str = "north-demo", user_id: str = "demo-user",
               topic: str = Query(), as_of: str | None = None):
        return memory.recall(tenant_id, user_id, topic, as_of)

    @app.post("/api/memory/forget")
    def forget(req: ForgetRequest):
        return memory.forget(req.tenant_id, req.user_id, req.topic)

    return app


app = create_app()
