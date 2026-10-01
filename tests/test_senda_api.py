import csv
import io
import unittest
from datetime import date, datetime, timedelta

import models
from app import create_app
from config import Config
from tests.fake_firestore import FakeFirestore

API_KEY = "test-key"
AUTH = {"Authorization": f"Bearer {API_KEY}"}


class TestConfig(Config):
    TESTING = True
    SENDA_API_KEY = API_KEY
    WTF_CSRF_ENABLED = False
    FIREBASE_CREDENTIALS = None


def make_app(db):
    original_init = models.init_firebase
    models.init_firebase = lambda app: setattr(models, "_db", db)
    try:
        import app as app_module
        app_module.init_firebase = models.init_firebase
        return create_app(TestConfig)
    finally:
        models.init_firebase = original_init


def seed(db):
    today = date.today()
    db.collection("books").document("1").set({"title": "Libro uno", "author": "Autora Test"})
    db.collection("books").document("2").set({"title": "Libro dos", "author": None})
    for doc_id, code, first in (("1", "A-1", "Ana"), ("2", "A-2", "Luis"), ("3", "A-3", "Eva")):
        db.collection("students").document(doc_id).set(
            {"student_id": code, "first_name": first, "last_name": "Test", "is_active": True}
        )
    loans = {
        "1": dict(book_id=1, student_id=1, due_date=(today - timedelta(days=5)).isoformat(), returned_at=None),
        "2": dict(book_id=2, student_id=1, due_date=(today + timedelta(days=5)).isoformat(), returned_at=None),
        "3": dict(book_id=1, student_id=2, due_date=(today - timedelta(days=9)).isoformat(),
                  returned_at=datetime.utcnow()),
    }
    for doc_id, data in loans.items():
        db.collection("loans").document(doc_id).set({**data, "borrowed_at": datetime.utcnow(), "renewals": 0})
    db.collection("users").document("1").set(
        {"username": "teacher", "password_hash": "x", "is_admin": False, "is_active_user": True}
    )


class SendaApiTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        seed(self.db)
        self.client = make_app(self.db).test_client()

    def test_overdue_returns_only_unreturned_late_loans_per_code(self):
        response = self.client.get("/api/senda/loans/overdue?codes=A-1,A-2,NOPE", headers=AUTH)
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([entry["student_code"] for entry in body["overdue"]], ["A-1"])
        self.assertEqual(len(body["overdue"][0]["loans"]), 1)
        self.assertEqual(body["overdue"][0]["loans"][0]["book"]["title"], "Libro uno")
        self.assertEqual(body["unknown_codes"], ["NOPE"])

    def test_overdue_rejects_missing_or_oversized_code_lists(self):
        self.assertEqual(self.client.get("/api/senda/loans/overdue", headers=AUTH).status_code, 400)
        many = ",".join(f"C-{i}" for i in range(201))
        self.assertEqual(self.client.get(f"/api/senda/loans/overdue?codes={many}", headers=AUTH).status_code, 400)

    def test_senda_endpoints_require_the_api_key(self):
        for path in ("/api/senda/students", "/api/senda/loans/overdue?codes=A-1"):
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path, headers={"Authorization": "Bearer wrong"}).status_code, 401)

    def test_students_csv_export_has_the_columns_the_senda_backfill_expects(self):
        response = self.client.get("/api/senda/students?format=csv", headers=AUTH)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(response.mimetype, "text/csv")
        self.assertEqual({r["student_id"] for r in rows}, {"A-1", "A-2", "A-3"})
        self.assertEqual(set(rows[0]), {"student_id", "first_name", "last_name", "grade", "group", "is_active"})

    def test_students_csv_neutralises_spreadsheet_formulas(self):
        self.db.collection("students").document("4").set(
            {"student_id": "A-4", "first_name": "=HYPERLINK(1)", "last_name": "Test"}
        )
        rows = list(csv.DictReader(io.StringIO(
            self.client.get("/api/senda/students?format=csv", headers=AUTH).get_data(as_text=True))))
        self.assertTrue(next(r for r in rows if r["student_id"] == "A-4")["first_name"].startswith("'="))


class DangerousRoutesTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        seed(self.db)
        self.client = make_app(self.db).test_client()

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = user_id
            session["_fresh"] = True

    def test_get_no_longer_triggers_destructive_actions(self):
        self.login("1")
        for path in ("/reset-db", "/reimport-data"):
            self.assertEqual(self.client.get(path).status_code, 405)
        self.assertTrue(self.db.store["books"])

    def test_non_admin_cannot_reset_the_database(self):
        self.login("1")
        self.assertEqual(self.client.post("/reset-db").status_code, 403)
        self.assertTrue(self.db.store["books"])

    def test_admin_can_reset_the_database(self):
        self.db.collection("users").document("2").set(
            {"username": "boss", "password_hash": "x", "is_admin": True, "is_active_user": True}
        )
        self.login("2")
        self.assertEqual(self.client.post("/reset-db").status_code, 302)
        self.assertFalse(self.db.store.get("books"))


if __name__ == "__main__":
    unittest.main()
