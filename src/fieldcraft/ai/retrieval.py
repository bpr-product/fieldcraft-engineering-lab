"""Deterministic lexical retrieval; clearly labelled as non-embedding offline mode.

Embedding/vector search can be added through a public plugin later. This module
intentionally never presents lexical matches as vector embeddings.
"""
from __future__ import annotations
import re
from fieldcraft.database import Database

STOP = {"the", "and", "for", "this", "that", "what", "which", "have", "did", "does",
        "into", "with", "how", "are", "was", "were", "show", "tell", "about", "from", "me"}


def tokens(text: str) -> set[str]:
    return {s for s in re.findall(r"[a-z0-9]+", text.lower()) if len(s) > 2 and s not in STOP}


class EvidenceRetriever:
    def __init__(self, db: Database):
        self.db = db

    def search(self, tenant_id: str, question: str, project_id: str | None = None, limit: int = 3) -> list[dict]:
        needle = tokens(question)
        with self.db.connection() as c:
            rows = c.execute("""SELECT id,project_id,text,source_refs_json,version FROM documents
                WHERE tenant_id=? AND (? IS NULL OR project_id=?)""",
                (tenant_id, project_id, project_id)).fetchall()
        import json
        matches = []
        for row in rows:
            haystack = tokens(row["text"])
            overlap = len(needle.intersection(haystack))
            if overlap or project_id:
                matches.append({"document_id": row["id"], "project_id": row["project_id"],
                                "score": overlap, "version": row["version"],
                                "text": row["text"],
                                "sources": json.loads(row["source_refs_json"])["sources"]})
        matches.sort(key=lambda r: (-r["score"], r["document_id"]))
        return matches[:limit]
