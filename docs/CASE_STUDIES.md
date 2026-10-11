# Engineering case studies

These five examples are independent illustrative software designs. Each one uses generated data and mock dependencies. They are suitable for discussing how an engineer approaches a problem, not for claiming that this code is a production deployment.

## 01 — Ledger Sync

**Problem:** Repeated export between two systems can create duplicates, while stale record versions can overwrite newer financial state.

**Implemented:** Workspace-scoped financial entities, stable external mappings, mock ledger identities, field comparison, version-based concurrency checks, pull/import and per-record status.

**Try:** Sync twice; the second result is `unchanged`. Introduce an out-of-band remote update using the test helper and observe a conflict rather than an unsafe overwrite.

**Engineering decision:** External mapping is a first-class table; names are not stable identities. Conflict should be explicit and diagnosable.

**Next:** Token lifecycle, safe retry classification, durable outbox, reconciliation dashboards and real provider sandbox tests.

## 02 — Supplier Material Import

**Problem:** Catalog data is only useful when it fits the application's units, vendors, branch context and duplicate rules.

**Implemented:** Branch catalog search, positive pricing, unit mapping, tenant-enabled unit checks, vendor ownership, duplicate detection and individual result reasons.

**Try:** Import `SHINGLE-01`, `NOPRICE-05`, `UNKNOWN-04`, then repeat the valid SKU. Inspect `added`, `missing_price`, `unmapped_uom`, `already_imported`.

**Engineering decision:** A provider's representation should be validated at the edge, while internal material definitions stay under workspace control.

**Next:** Real supplier OAuth, authenticated account/ship-to context, dimensional pricing, branch services, ordering and fulfillment tracking.

## 03 — Measurement Reports

**Problem:** Measurement reports arrive asynchronously and have their own lifecycle. A rejected or incomplete provider response should not look completed.

**Implemented:** Validated measurement requests, explicit order states, constrained transitions, normalized area/pitch/facet report and project-scoped retrieval.

**Try:** Request a report, ingest a sample, then attempt to ingest again. The second ingestion is rejected.

**Engineering decision:** Keep provider states separate from application readiness; do not write unvalidated report values into a project.

**Next:** Credential handling, remote polling/webhooks, object storage, retries and structured report versioning.

## 04 — Document Pipeline

**Problem:** Operational information is split among tables, while retrieval benefits from project-level context and source references.

**Implemented:** Scoped relational joins, structured JSON records, human-readable documents, canonical checksums, source IDs and deterministic refresh versions.

**Try:** Refresh; refresh again; add a material or completed report and refresh. Versions change only when source-derived payload changes.

**Engineering decision:** Separate the operational source model from the retrieval representation. Store enough lineage to explain and repair downstream state.

**Next:** PostgreSQL source connectors, message-driven update detection, document persistence, real embedding indexing and evaluation datasets.

## 05 — Context Pilot + Memory

**Problem:** Assistants can select the wrong project, answer without supporting evidence or repeat stale user context.

**Implemented:** Project/session context, traceable routing, deterministic cost variance, scoped document retrieval, evidence IDs, abstention, optional model generation and a separate explicit-user memory store.

**Try:** Ask a cost question, switch project, inspect trace and citations. Store a synthetic memory preference, update it on a later date, recall it historically and forget all versions.

**Engineering decision:** Source selection and state handling deserve as much engineering attention as response generation. User memory must have a write policy and deletion lineage.

**Next:** More robust entity disambiguation, actual embedding retrieval, evaluation over long conversation histories, trace grading and deletion testing across backups and caches.
