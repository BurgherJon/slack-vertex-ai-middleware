# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""FirestoreService.list_agents doc-filtering tests.

Underscore-prefixed documents (e.g. the "_placeholder" doc the Firestore
console forces you to create with a new collection) are markers, not
agents: they must be skipped silently, while genuinely malformed agent
docs keep producing a warning.
"""
import logging

from app.services.firestore_service import FirestoreService


class _Doc:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class _Collection:
    def __init__(self, docs: list[_Doc]):
        self._docs = docs

    async def get(self) -> list[_Doc]:
        return self._docs


class _Client:
    def __init__(self, docs: list[_Doc]):
        self._docs = docs

    def collection(self, name: str) -> _Collection:
        return _Collection(self._docs)


def _service(docs: list[_Doc]) -> FirestoreService:
    svc = FirestoreService.__new__(FirestoreService)
    svc.client = _Client(docs)
    svc.agents_collection = "agents"
    return svc


async def test_underscore_docs_are_skipped_silently(caplog):
    docs = [
        _Doc("_placeholder", {"_placeholder": True, "note": "Delete after adding real agents."}),
        _Doc(
            "agent-1",
            {"vertex_ai_agent_id": "re-1", "display_name": "Agent One"},
        ),
    ]
    with caplog.at_level(logging.WARNING):
        agents = await _service(docs).list_agents()

    assert [a.id for a in agents] == ["agent-1"]
    assert not any("Skipping agent" in r.message for r in caplog.records)


async def test_malformed_real_docs_still_warn(caplog):
    docs = [_Doc("agent-broken", {"unexpected": True})]
    with caplog.at_level(logging.WARNING):
        agents = await _service(docs).list_agents()

    assert agents == []
    assert any("Skipping agent agent-broken" in r.message for r in caplog.records)
