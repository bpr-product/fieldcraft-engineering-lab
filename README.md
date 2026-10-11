# FieldCraft — Engineering Systems Lab

Independent, synthetic portfolio project demonstrating five integrated construction-operations engineering workflows. This project is **not** an employer source-code release or a live commercial provider integration.

## Demonstrations

- Ledger Sync — idempotent import/export, stable external IDs, version-conflict handling.
- Supplier Import — catalog search, branch-aware pricing, UOM validation, duplicate prevention.
- Measurement Flow — measurement orders, state transitions, ingestion of synthetic reports.
- Document Pipeline — relational records transformed into versioned retrieval-ready evidence.
- Context Pilot — scoped retrieval, query routing, evidence-backed answers, execution trace.

A separate small memory experiment covers write gates, provenance, validity updates, and logical erasure.

## Local execution (after pushing project files)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn fieldcraft.api:app --app-dir src --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 or http://127.0.0.1:8000/docs.

```bash
python -m pytest
python scripts/check_public_safe.py
```

## Boundaries

All demo data is invented. Accounting, supplier, and measurement providers are simulations. Default retrieval is lexical/structured evidence, **not** a live embedding or vector-database deployment. An OpenAI-compatible model endpoint is optional and must be configured server-side. Local SQLite workspace scoping is not production authorization.

This repository is intended to communicate engineering decisions and failure handling, not to impersonate any employer product. No employer-owned code, data or secrets should be added.

## Publishing status

The GitHub repository has been initialized and the complete 41-file local source package is prepared separately. **Until the source files are pushed, this README does not represent a runnable GitHub checkout.**
