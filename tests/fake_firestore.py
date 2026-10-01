"""Minimal in-memory stand-in for the Firestore client used by models.py."""


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data)

    def get(self, field):
        return self._data.get(field)


class FakeQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, field, op, value):
        tests = {
            "==": lambda v: v == value,
            "in": lambda v: v in value,
        }
        return FakeQuery([d for d in self._docs if tests[op](d.to_dict().get(field))])

    def limit(self, count):
        return FakeQuery(self._docs[:count])

    def stream(self):
        return iter(self._docs)


class FakeDocRef:
    def __init__(self, store, name, doc_id):
        self._store, self._name, self._id = store, name, doc_id

    def get(self):
        return FakeDoc(self._id, self._store.get(self._name, {}).get(self._id))

    def set(self, data, merge=False):
        collection = self._store.setdefault(self._name, {})
        collection[self._id] = {**collection.get(self._id, {}), **data} if merge else dict(data)

    def delete(self):
        self._store.get(self._name, {}).pop(self._id, None)


class FakeCollection(FakeQuery):
    def __init__(self, store, name):
        self._store, self._name = store, name

    @property
    def _docs(self):
        return [FakeDoc(i, d) for i, d in self._store.get(self._name, {}).items()]

    def document(self, doc_id):
        return FakeDocRef(self._store, self._name, doc_id)

    def list_documents(self):
        return [FakeDocRef(self._store, self._name, i) for i in list(self._store.get(self._name, {}))]


class FakeFirestore:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self.store, name)
