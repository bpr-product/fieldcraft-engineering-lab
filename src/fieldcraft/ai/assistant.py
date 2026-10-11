"""Scoped, explainable question routing with source evidence and optional LLM.

The offline mode returns deterministic evidence summaries; it does not pretend to
have generated a model response. Optional model mode only runs when configured.
"""
from __future__ import annotations
import re
from fieldcraft.database import Database, utc_now
from .provider import ModelGateway
from .retrieval import EvidenceRetriever
from fieldcraft.services.common import NotFoundError, new_id


class ContextPilot:
    def __init__(self, db: Database, model: ModelGateway | None = None):
        self.db = db
        self.search = EvidenceRetriever(db)
        self.model = model or ModelGateway()

    def ask(self, tenant_id: str, user_id: str, session_id: str, question: str,
            active_project_id: str | None = None) -> dict:
        if not question.strip():
            raise ValueError("Question cannot be empty")
        if not self.db.exists_tenant(tenant_id):
            raise NotFoundError("Unknown workspace")
        trace = [{"step": "validate", "detail": "Workspace and question checked"}]
        with self.db.connection() as c:
            projects = [dict(p) for p in c.execute("SELECT id,name,estimated_material_cents,actual_material_cents FROM projects WHERE tenant_id=?", (tenant_id,))]
            conversation = c.execute("SELECT * FROM conversations WHERE id=? AND tenant_id=? AND user_id=?",
                                     (session_id, tenant_id, user_id)).fetchone()
            # A session ID belonging to another workspace or user must not be reused.
            clash = c.execute("SELECT 1 FROM conversations WHERE id=?", (session_id,)).fetchone()
            if clash and not conversation:
                raise NotFoundError("Session not accessible")
            previous_id = conversation["active_project_id"] if conversation else None
            if active_project_id and not any(p["id"] == active_project_id for p in projects):
                raise NotFoundError("Project not found for workspace")
            found = [p for p in projects if p["name"].lower() in question.lower()]
            # A project explicitly named in the question overrides stale page state.
            # Multiple named projects need a separate comparison intent.
            if len(found) > 1:
                return {"answer": "Your question mentions multiple projects. Please select one project for this demo.",
                        "mode": "clarification", "evidence": [], "trace": trace}
            selected = ((found[0]["id"] if len(found) == 1 else None) or active_project_id or previous_id)
            if conversation:
                c.execute("UPDATE conversations SET active_project_id=?,updated_at=? WHERE id=? AND tenant_id=?",
                          (selected, utc_now(), session_id, tenant_id))
            else:
                c.execute("""INSERT INTO conversations(id,tenant_id,user_id,active_project_id,updated_at)
                    VALUES(?,?,?,?,?)""", (session_id, tenant_id, user_id, selected, utc_now()))
        trace.append({"step": "context", "detail": f"Selected project: {selected or 'not specified'}"})
        lower = question.lower()
        route = "cost_variance" if any(w in lower for w in ("over budget", "exceed", "variance", "cost more")) else (
            "supplier" if any(w in lower for w in ("supplier", "material", "price", "availability")) else "project_insight")
        trace.append({"step": "route", "detail": route})
        # A project-scoped follow-up takes precedence over a global document search.
        if route == "cost_variance" and selected:
            p = next(p for p in projects if p["id"] == selected)
            variance = p["actual_material_cents"] - p["estimated_material_cents"]
            answer = (f"{p['name']}: actual material cost is {p['actual_material_cents'] / 100:,.2f} "
                      f"versus estimated {p['estimated_material_cents'] / 100:,.2f}. "
                      f"Variance is {variance / 100:+,.2f}. These are illustrative sample amounts; "
                      f"the available totals alone do not establish the cause of this variance.")
            evidence = self.search.search(tenant_id, question, project_id=selected, limit=2)
            trace.append({"step": "structured_query", "detail": "Scoped project cost comparison"})
            return {"answer": answer, "mode": "structured", "route": route,
                    "evidence": self._summarize_evidence(evidence), "trace": trace}
        # Page context is not proof that any unrelated user question is answerable.
        relevant_subject = any(term in lower for term in (
            "project", "estimate", "material", "supplier", "roof", "measurement",
            "cost", "site", "status", "trade", "budget", "cedar", "orion"))
        if not relevant_subject:
            return {"answer": "I don't know from the available project data.", "mode": "abstained",
                    "route": route, "evidence": [], "trace": trace + [
                        {"step": "evidence_gate", "detail": "Question does not match a supported project topic"}]}
        evidence = self.search.search(tenant_id, question, project_id=selected, limit=3)
        trace.append({"step": "retrieval", "detail": f"{len(evidence)} synthetic document(s) matched using lexical search"})
        if not evidence:
            return {"answer": "I don't know from the available project data.", "mode": "abstained",
                    "route": route, "evidence": [], "trace": trace}
        if self.model.configured:
            try:
                answer = self.model.compose(question, evidence)
            except Exception:
                # Explicit failure, not a silently substituted model answer.
                return {"answer": "Model request failed. Evidence is available below; retry after checking the model service.",
                        "mode": "model_error", "route": route, "evidence": self._summarize_evidence(evidence),
                        "trace": trace + [{"step": "generation", "detail": "Provider request failed"}]}
            trace.append({"step": "generation", "detail": "Configured model responded with evidence"})
            mode = "llm"
        else:
            answer = "Offline evidence preview (no LLM call): " + evidence[0]["text"].splitlines()[0]
            mode = "evidence_only"
            trace.append({"step": "generation", "detail": "Not run: model not configured"})
        return {"answer": answer, "mode": mode, "route": route,
                "evidence": self._summarize_evidence(evidence), "trace": trace}

    @staticmethod
    def _summarize_evidence(evidence: list[dict]) -> list[dict]:
        return [{"document_id": r["document_id"], "project_id": r["project_id"],
                 "score": r["score"], "version": r["version"], "source_refs": r["sources"]}
                for r in evidence]
