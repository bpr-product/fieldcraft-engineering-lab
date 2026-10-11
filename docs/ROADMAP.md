# Roadmap — improvements in priority order

The current code is intentionally runnable without credentials. Build quality comes before surface area.

1. Add a real optional embedding index and a measurable retrieval evaluation set, while retaining an explicit offline mode.
2. Use a real relational-source and document-store adapter (PostgreSQL/MongoDB) in a fully synthetic deployment.
3. Add a FastAPI dependency that enforces authenticated workspace access and policy checks before production-like hosting.
4. Introduce a simulated event queue and durable outbox for failure recovery and repeat-safe provider operations.
5. Build a memory evaluation harness for contradictions, temporal updates, injection rejection and downstream erasure.
6. Add CI to run unit tests, linting, package scans and synthetic end-to-end browser tests on each pull request.
7. Publish a 2-minute walkthrough showing source evidence, failure cases and the distinction between mock and live adapters.

Competition-specific development must follow the competition rules. A separate event submission should use a fresh repository and project code written only during the event; do not reuse this implementation as prewritten entry code if the rules prohibit it.
