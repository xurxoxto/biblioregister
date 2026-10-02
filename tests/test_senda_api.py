"""Tests for the read-only Senda API (/api/senda/*), using an in-memory Firestore fake."""

import unittest
from datetime import datetime, timedelta
from unittest import mock

import models
from app import create_app
from config import Config

API_KEY = "test-key"


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = str(doc_id)
        self._data = data
        self.exists = True

    def to_dict(self):
        return dict(self._data)


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def where(self, field, _op, value):
        return FakeCollection([d for d in self.docs if d._data.get(field) == value])

    def limit(self, n):
        return FakeCollection(self.docs[:n])

    def stream(self):
        return iter(self.docs)

    def document(self, doc_id):
        match = next((d for d in self.docs if d.id == str(doc_id)), None)
        missing = mock.Mock(exists=False)
        return mock.Mock(get=lambda: match or missing)


def build_data():
    now = datetime.utcnow()
    day = timedelta(days=1)
    fmt = "%Y-%m-%d"
    return {
        "users": [FakeDoc(1, {"username": "admin"})],
        "settings": [],
        "students": [
            FakeDoc(1, {"student_id": "A01", "first_name": "Ana", "last_name": "Gil",
                        "max_loans": 2}),
            FakeDoc(2, {"student_id": "B02", "first_name": "Bea", "last_name": "Paz"}),
        ],
        "books": [FakeDoc(i, {"title": f"Libro {i}", "author": "Autor"}) for i in (1, 2, 3)],
        "loans": [
            # overdue, still out
            FakeDoc(1, {"book_id": 1, "student_id": 1, "borrowed_at": now - 40 * day,
                        "due_date": (now - 10 * day).strftime(fmt), "returned_at": None}),
            # returned
            FakeDoc(2, {"book_id": 2, "student_id": 1, "borrowed_at": now - 90 * day,
                        "due_date": (now - 60 * day).strftime(fmt),
                        "returned_at": now - 65 * day}),
            # active, on time
            FakeDoc(3, {"book_id": 3, "student_id": 1, "borrowed_at": now - 2 * day,
                        "due_date": (now + 28 * day).strftime(fmt), "returned_at": None}),
            # other student
            FakeDoc(4, {"book_id": 3, "student_id": 2, "borrowed_at": now,
                        "due_date": None, "returned_at": None}),
        ],
    }


class SendaApiTests(unittest.TestCase):
    def setUp(self):
        data = build_data()
        db = mock.Mock()
        db.collection = lambda name: FakeCollection(data[name])
        patches = [
            mock.patch.object(models, "_db", db),
            mock.patch("app.init_firebase", lambda app: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        class TestConfig(Config):
            TESTING = True
            SENDA_API_KEY = API_KEY

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.auth = {"X-API-Key": API_KEY}

    def get(self, url, headers=None):
        return self.client.get(url, headers=self.auth if headers is None else headers)

    def test_missing_or_wrong_key_is_unauthorized(self):
        self.assertEqual(self.get("/api/senda/students/1/loans", {}).status_code, 401)
        bad = {"X-API-Key": "nope"}
        self.assertEqual(self.get("/api/senda/students/1/loans", bad).status_code, 401)

    def test_bearer_token_is_accepted(self):
        headers = {"Authorization": f"Bearer {API_KEY}"}
        self.assertEqual(self.get("/api/senda/students/1/loans", headers).status_code, 200)

    def test_api_disabled_without_configured_key(self):
        self.app.config["SENDA_API_KEY"] = None
        self.assertEqual(self.get("/api/senda/students/1/loans").status_code, 503)

    def test_summary_and_history_for_student(self):
        body = self.get("/api/senda/students/1/loans").get_json()
        self.assertEqual(body["student"]["student_id"], "A01")
        self.assertEqual(body["summary"], {
            "active_loans": 2, "overdue_loans": 1, "returned_loans": 1,
            "total_loans": 3, "max_loans": 2, "can_borrow": False,
        })
        self.assertEqual([l["id"] for l in body["loans"]], [3, 1, 2])  # newest first
        self.assertEqual({l["id"]: l["status"] for l in body["loans"]},
                         {1: "overdue", 2: "returned", 3: "active"})
        self.assertEqual(body["loans"][1]["days_overdue"], 10)
        self.assertEqual(body["loans"][0]["book"]["title"], "Libro 3")

    def test_status_filter(self):
        for status, ids in (("active", {1, 3}), ("overdue", {1}), ("returned", {2})):
            body = self.get(f"/api/senda/students/1/loans?status={status}").get_json()
            self.assertEqual({l["id"] for l in body["loans"]}, ids, status)

    def test_invalid_status_is_bad_request(self):
        self.assertEqual(self.get("/api/senda/students/1/loans?status=x").status_code, 400)

    def test_lookup_by_school_code(self):
        body = self.get("/api/senda/students/code/B02/loans").get_json()
        self.assertEqual(body["student"]["id"], 2)
        self.assertEqual(body["summary"]["active_loans"], 1)

    def test_unknown_student_is_404(self):
        self.assertEqual(self.get("/api/senda/students/99/loans").status_code, 404)
        self.assertEqual(self.get("/api/senda/students/code/ZZ/loans").status_code, 404)

    def test_rest_of_app_still_requires_login(self):
        self.assertEqual(self.client.get("/books").status_code, 302)


if __name__ == "__main__":
    unittest.main()
