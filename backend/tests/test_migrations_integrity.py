"""Structural checks on the Alembic revision graph.

The suite builds its schema with ``create_all``, never by running migrations —
so a broken migration passes every test and only fails on deploy. That is
exactly what happened here: a new revision reused an existing id
(``a1b2c3d4e5f6``, already taken by knowledge_chunks), which made Alembic see a
CYCLE and refuse to run at all, while 171 tests stayed green.

These checks need no database, so they cost nothing and close that gap.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"

REVISION_RE = re.compile(r'^revision:?\s*(?::\s*str\s*)?=\s*["\']([^"\']+)["\']', re.M)
DOWN_RE = re.compile(
    r'^down_revision:?\s*(?::\s*str\s*\|\s*None\s*)?=\s*(?:["\']([^"\']+)["\']|None)', re.M
)


def _graph() -> dict[str, str | None]:
    graph: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        src = path.read_text()
        rev = REVISION_RE.search(src)
        assert rev, f"{path.name}: no revision id"
        down = DOWN_RE.search(src)
        graph[rev.group(1)] = down.group(1) if down and down.group(1) else None
    return graph


def test_revision_ids_are_unique() -> None:
    """Two files sharing an id makes Alembic report a cycle, not a duplicate —
    an error message that points nowhere near the actual mistake."""
    ids = []
    for path in VERSIONS.glob("*.py"):
        match = REVISION_RE.search(path.read_text())
        assert match, f"{path.name}: no revision id"
        ids.append(match.group(1))
    dupes = [rev for rev, n in Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate revision ids: {dupes}"


def test_exactly_one_head() -> None:
    graph = _graph()
    parents = {down for down in graph.values() if down}
    heads = [rev for rev in graph if rev not in parents]
    assert len(heads) == 1, f"expected one head, found {sorted(heads)}"


def test_exactly_one_base() -> None:
    graph = _graph()
    bases = [rev for rev, down in graph.items() if down is None]
    assert len(bases) == 1, f"expected one base, found {sorted(bases)}"


def test_every_down_revision_exists() -> None:
    graph = _graph()
    missing = {down for down in graph.values() if down and down not in graph}
    assert not missing, f"down_revision points at unknown revisions: {sorted(missing)}"


def test_chain_is_acyclic_and_reaches_the_base() -> None:
    graph = _graph()
    parents = {down for down in graph.values() if down}
    head = next(rev for rev in graph if rev not in parents)

    seen: set[str] = set()
    cursor: str | None = head
    while cursor is not None:
        assert cursor not in seen, f"cycle detected at {cursor}"
        seen.add(cursor)
        cursor = graph[cursor]

    assert seen == set(graph), (
        f"revisions unreachable from head: {sorted(set(graph) - seen)}"
    )
