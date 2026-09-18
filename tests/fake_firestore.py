"""In-memory fake for the subset of the Firestore client API VerbBoard's
write-path code actually exercises (issue #8).

Intended as the shared replacement for the ad-hoc _FakeDb/_FakeCollection
fakes duplicated across test_verb_service_generation.py,
test_progress_batch_repository.py, test_demand_logging.py, test_autogen.py,
test_verb_of_the_day.py, and the MagicMock-chain fakes in
test_session_tracker.py / test_nikud_normalization.py -- new tests should use
this instead of adding a seventh. Existing ad-hoc fakes are not migrated in
this pass; move them over opportunistically when their file is next touched.

Use via the `fake_db` fixture in conftest.py -- this module has no pytest
dependency itself.

Deliberately NOT supported (see issue #8 design discussion -- add only if a
real caller needs it): transactions, array_contains_any, !=, not-in, cursors
(start_after/end_before), offset, select/projections, nested dotted field
paths in update(), composite-index-requirement errors, ordering semantics for
docs missing the order_by field, snapshot listeners, the async client.
Sentinels (SERVER_TIMESTAMP, Increment, ArrayUnion) are stored opaquely,
unresolved -- store a real value in tests that need one.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, cast

from google.api_core.exceptions import AlreadyExists, NotFound

_UNSET = object()


class FakeSnapshot:
    def __init__(self, ref: "FakeDocRef", data: dict[str, Any] | None) -> None:
        self.reference = ref
        self.id = ref.id
        self._data = copy.deepcopy(data) if data is not None else None

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data) if self._data is not None else None


class FakeDocRef:
    def __init__(self, store: "FakeFirestore", path: str) -> None:
        self._store = store
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self, self._store._docs.get(self.path))

    def create(self, data: dict[str, Any]) -> None:
        if self.path in self._store._docs:
            raise AlreadyExists(f"Document already exists: {self.path}")
        self._store._docs[self.path] = copy.deepcopy(data)

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if merge and self.path in self._store._docs:
            self._store._docs[self.path].update(copy.deepcopy(data))
        else:
            self._store._docs[self.path] = copy.deepcopy(data)

    def update(self, data: dict[str, Any]) -> None:
        if self.path not in self._store._docs:
            raise NotFound(f"No document to update: {self.path}")
        self._store._docs[self.path].update(copy.deepcopy(data))

    def delete(self) -> None:
        self._store._docs.pop(self.path, None)

    def collection(self, name: str) -> "FakeCollection":
        return FakeCollection(self._store, f"{self.path}/{name}")


def _op_matches(actual: Any, op: str, expected: Any) -> bool:
    if op == "==":
        return actual == expected
    if op == ">=":
        return actual is not None and actual >= expected
    if op == "<=":
        return actual is not None and actual <= expected
    if op == "array_contains":
        return isinstance(actual, list) and expected in actual
    if op == "in":
        return actual in expected
    raise NotImplementedError(f"FakeQuery operator not supported: {op!r}")


class _CountValue:
    def __init__(self, count: int) -> None:
        self.value = count


class _CountQuery:
    def __init__(self, query: "FakeQuery") -> None:
        self._query = query

    def get(self) -> list[list[_CountValue]]:
        return [[_CountValue(len(self._query._matching_paths()))]]


class FakeQuery:
    def __init__(self, store: "FakeFirestore", collection_path: str, *, group: bool = False) -> None:
        self._store = store
        self._collection_path = collection_path
        self._group = group
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: tuple[str, str] | None = None
        self._limit: int | None = None

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        q = self._clone()
        q._filters.append((field, op, value))
        return q

    def order_by(self, field: str, direction: str = "ASCENDING") -> "FakeQuery":
        q = self._clone()
        q._order_by = (field, direction)
        return q

    def limit(self, n: int) -> "FakeQuery":
        q = self._clone()
        q._limit = n
        return q

    def count(self) -> _CountQuery:
        return _CountQuery(self)

    def stream(self) -> Iterable[FakeSnapshot]:
        for path in self._matching_paths():
            yield FakeSnapshot(FakeDocRef(self._store, path), self._store._docs[path])

    def _clone(self) -> "FakeQuery":
        q = FakeQuery(self._store, self._collection_path, group=self._group)
        q._filters = list(self._filters)
        q._order_by = self._order_by
        q._limit = self._limit
        return q

    def _matching_paths(self) -> list[str]:
        if self._group:
            paths = [p for p in self._store._docs if _parent_collection(p) == self._collection_path]
        else:
            prefix = self._collection_path + "/"
            paths = [p for p in self._store._docs if p.startswith(prefix) and "/" not in p[len(prefix) :]]

        for field, op, value in self._filters:
            paths = [p for p in paths if _op_matches(self._store._docs[p].get(field), op, value)]

        if self._order_by:
            field, direction = self._order_by
            # Ordering semantics for docs missing the order_by field are out of
            # scope (see module docstring) -- cast(Any) satisfies mypy rather
            # than asserting a comparability guarantee this fake doesn't make.
            paths.sort(
                key=lambda p: cast(Any, self._store._docs[p].get(field)),
                reverse=(direction == "DESCENDING"),
            )

        if self._limit is not None:
            paths = paths[: self._limit]

        return paths


def _parent_collection(path: str) -> str:
    parts = path.rsplit("/", 2)
    return parts[-2]


class FakeCollection(FakeQuery):
    def __init__(self, store: "FakeFirestore", path: str) -> None:
        super().__init__(store, path, group=False)
        self.path = path

    def document(self, doc_id: str | None = None) -> FakeDocRef:
        if doc_id is None:
            doc_id = f"auto_{len(self._store._docs)}_{id(object())}"
        return FakeDocRef(self._store, f"{self.path}/{doc_id}")

    def add(self, data: dict[str, Any]) -> tuple[None, FakeDocRef]:
        ref = self.document()
        ref.create(data)
        return (None, ref)


class _BatchOp:
    __slots__ = ("kind", "ref", "data", "merge")

    def __init__(self, kind: str, ref: FakeDocRef, data: dict[str, Any] | None, merge: bool) -> None:
        self.kind = kind
        self.ref = ref
        self.data = data
        self.merge = merge


class FakeBatch:
    def __init__(self) -> None:
        self._ops: list[_BatchOp] = []

    def set(self, ref: FakeDocRef, data: dict[str, Any], merge: bool = False) -> None:
        self._ops.append(_BatchOp("set", ref, data, merge))

    def update(self, ref: FakeDocRef, data: dict[str, Any]) -> None:
        self._ops.append(_BatchOp("update", ref, data, False))

    def delete(self, ref: FakeDocRef) -> None:
        self._ops.append(_BatchOp("delete", ref, None, False))

    def commit(self) -> None:
        ops, self._ops = self._ops, []
        for op in ops:
            if op.kind == "set":
                assert op.data is not None
                op.ref.set(op.data, merge=op.merge)
            elif op.kind == "update":
                assert op.data is not None
                op.ref.update(op.data)
            elif op.kind == "delete":
                op.ref.delete()


class FakeFirestore:
    """Root fake client. Stores every document flat, keyed by its full
    slash-joined path (e.g. "user_practice/uid1/languages/en"), which is what
    lets collection_group() report a real .reference.path like Firestore does.
    """

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self, name)

    def collection_group(self, name: str) -> FakeQuery:
        return FakeQuery(self, name, group=True)

    def batch(self) -> FakeBatch:
        return FakeBatch()

    def get_all(self, refs: Iterable[FakeDocRef]) -> list[FakeSnapshot]:
        return [ref.get() for ref in refs]

    def seed(self, collection: str, docs: dict[str, dict[str, Any]]) -> None:
        """Test-facing helper: directly populate documents without going
        through create()/set(), for arranging pre-existing state."""
        for doc_id, data in docs.items():
            self._docs[f"{collection}/{doc_id}"] = copy.deepcopy(data)

    def seed_path(self, path: str, data: dict[str, Any]) -> None:
        """Like seed(), but for a document under a subcollection path, e.g.
        seed_path("user_practice/uid1/languages/en", {...})."""
        self._docs[path] = copy.deepcopy(data)

    @property
    def data(self) -> dict[str, dict[str, Any]]:
        """Test-facing snapshot of all stored documents, for state
        assertions (e.g. confirming a document was NOT written)."""
        return copy.deepcopy(self._docs)
