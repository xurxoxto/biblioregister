"""
BiblioRegister — Firestore-backed data models.

Replaces SQLAlchemy with Google Cloud Firestore so the app can run online
with multiple devices sharing the same database in Firebase.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from flask import abort


# ─── Firebase initialisation ───────────────────────────────────
_db = None


def init_firebase(app):
    """Initialise Firebase Admin SDK and Firestore client."""
    import json as _json
    import os as _os
    global _db
    if not firebase_admin._apps:
        cred_path = app.config.get("FIREBASE_CREDENTIALS")
        cred_json = _os.environ.get("FIREBASE_CREDENTIALS_JSON")  # inline JSON string
        project_id = app.config.get("FIREBASE_PROJECT_ID")
        opts = {"projectId": project_id} if project_id else {}
        if cred_path:
            firebase_admin.initialize_app(credentials.Certificate(cred_path), opts)
        elif cred_json:
            try:
                info = _json.loads(cred_json)
            except _json.JSONDecodeError as e:
                raise RuntimeError(
                    f"FIREBASE_CREDENTIALS_JSON is not valid JSON: {e}"
                ) from e
            firebase_admin.initialize_app(credentials.Certificate(info), opts)
        else:
            # Application Default Credentials — works on Cloud Run automatically
            firebase_admin.initialize_app(options=opts)
    _db = firestore.client()


def get_db():
    """Return the Firestore client."""
    return _db


# ─── Helpers ────────────────────────────────────────────────────

def _next_id(collection_name):
    """Auto-increment ID using Firestore Increment sentinel (no transaction)."""
    db = get_db()
    ref = db.collection("_counters").document(collection_name)
    ref.set({"next_id": firestore.Increment(1)}, merge=True)
    snap = ref.get()
    return snap.get("next_id")


def _dt(value):
    """Convert value → datetime | None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                     "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _to_date(value):
    """Convert value → date | None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


# ─── Pagination (template-compatible) ──────────────────────────

class Pagination:
    """Mimics Flask-SQLAlchemy's pagination object."""

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, -(-total // per_page))  # ceil division
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge
                    or self.page - left_current <= num <= self.page + right_current
                    or num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def paginate_list(items, page, per_page=20):
    """Paginate a plain Python list."""
    total = len(items)
    start = (page - 1) * per_page
    return Pagination(items[start:start + per_page], page, per_page, total)


# ─── Bulk delete ───────────────────────────────────────────────

def drop_all():
    """Delete every document in every app collection."""
    db = get_db()
    for name in ("users", "books", "students", "loans",
                 "ratings", "settings", "_counters"):
        for doc_ref in db.collection(name).list_documents():
            doc_ref.delete()


def drop_data():
    """Delete all data except users and counters."""
    db = get_db()
    for name in ("books", "students", "loans", "ratings", "settings"):
        for doc_ref in db.collection(name).list_documents():
            doc_ref.delete()
    # Reset counters for data collections
    for name in ("books", "students", "loans", "ratings"):
        ref = db.collection("_counters").document(name)
        if ref.get().exists:
            ref.delete()


# ═══════════════════════════════════════════════════════════════
#  USER
# ═══════════════════════════════════════════════════════════════

class User(UserMixin):
    _COL = "users"

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.username = kw.get("username", "")
        self.password_hash = kw.get("password_hash", "")
        self.display_name = kw.get("display_name", "")
        self.is_admin = kw.get("is_admin", False)
        self.is_active_user = kw.get("is_active_user", True)
        self.created_at = _dt(kw.get("created_at")) or datetime.utcnow()

    # Flask-Login interface
    @property
    def is_active(self):
        return self.is_active_user

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw, method="pbkdf2:sha256")

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    # Persistence
    def _to_dict(self):
        return dict(
            username=self.username, password_hash=self.password_hash,
            display_name=self.display_name, is_admin=self.is_admin,
            is_active_user=self.is_active_user, created_at=self.created_at,
        )

    def save(self):
        if self.id is None:
            self.id = _next_id(self._COL)
        get_db().collection(self._COL).document(str(self.id)).set(self._to_dict())

    def delete(self):
        get_db().collection(self._COL).document(str(self.id)).delete()

    # Queries
    @classmethod
    def get(cls, doc_id):
        d = get_db().collection(cls._COL).document(str(doc_id)).get()
        return cls(id=int(d.id), **d.to_dict()) if d.exists else None

    @classmethod
    def get_or_404(cls, doc_id):
        obj = cls.get(doc_id)
        if not obj:
            abort(404)
        return obj

    @classmethod
    def find_by_username(cls, username):
        for d in (get_db().collection(cls._COL)
                  .where("username", "==", username).limit(1).stream()):
            return cls(id=int(d.id), **d.to_dict())
        return None

    @classmethod
    def query_all(cls):
        return sorted(
            [cls(id=int(d.id), **d.to_dict())
             for d in get_db().collection(cls._COL).stream()],
            key=lambda u: u.username,
        )

    @classmethod
    def count(cls):
        return sum(1 for _ in get_db().collection(cls._COL).stream())

    def __repr__(self):
        return f"<User {self.username}>"


# ═══════════════════════════════════════════════════════════════
#  SETTING  (key-value store)
# ═══════════════════════════════════════════════════════════════

class Setting:
    _COL = "settings"

    def __init__(self, key=None, value=None, description=None):
        self.key = key
        self.value = value
        self.description = description

    @classmethod
    def get(cls, key):
        d = get_db().collection(cls._COL).document(key).get()
        if d.exists:
            data = d.to_dict()
            return cls(key=key, value=data.get("value"),
                       description=data.get("description"))
        return None

    @classmethod
    def set_value(cls, key, value):
        get_db().collection(cls._COL).document(key).set(
            {"value": str(value)}, merge=True)


# ═══════════════════════════════════════════════════════════════
#  BOOK
# ═══════════════════════════════════════════════════════════════

class Book:
    _COL = "books"

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.isbn = kw.get("isbn")
        self.title = kw.get("title", "")
        self.author = kw.get("author", "")
        self.publisher = kw.get("publisher")
        self.year = kw.get("year")
        if self.year is not None:
            try:
                self.year = int(self.year)
            except (ValueError, TypeError):
                self.year = None
        self.cdu = kw.get("cdu")
        self.category = kw.get("category")
        self.location = kw.get("location")
        self.copies_total = int(kw.get("copies_total", 1) or 1)
        self.description = kw.get("description")
        self.language = kw.get("language", "Español")
        self.created_at = _dt(kw.get("created_at")) or datetime.utcnow()
        self.updated_at = _dt(kw.get("updated_at")) or datetime.utcnow()

    # Computed properties
    @property
    def copies_available(self):
        active = sum(
            1 for d in get_db().collection("loans")
            .where("book_id", "==", self.id).stream()
            if d.to_dict().get("returned_at") is None
        )
        return max(0, self.copies_total - active)

    @property
    def is_available(self):
        return self.copies_available > 0

    @property
    def avg_rating(self):
        stars = [d.to_dict().get("stars", 0)
                 for d in get_db().collection("ratings")
                 .where("book_id", "==", self.id).stream()]
        if not stars:
            return None
        return round(sum(stars) / len(stars), 1)

    @property
    def rating_count(self):
        return sum(1 for _ in get_db().collection("ratings")
                   .where("book_id", "==", self.id).stream())

    # Persistence
    def _to_dict(self):
        return dict(
            isbn=self.isbn, title=self.title, author=self.author or "",
            publisher=self.publisher, year=self.year, cdu=self.cdu,
            category=self.category, location=self.location,
            copies_total=self.copies_total, description=self.description,
            language=self.language,
            created_at=self.created_at, updated_at=self.updated_at,
        )

    def save(self):
        self.updated_at = datetime.utcnow()
        if self.id is None:
            self.id = _next_id(self._COL)
            self.created_at = datetime.utcnow()
        get_db().collection(self._COL).document(str(self.id)).set(self._to_dict())

    def delete(self):
        for d in get_db().collection("ratings").where("book_id", "==", self.id).stream():
            d.reference.delete()
        get_db().collection(self._COL).document(str(self.id)).delete()

    # Queries
    @classmethod
    def get(cls, doc_id):
        if doc_id is None:
            return None
        d = get_db().collection(cls._COL).document(str(doc_id)).get()
        return cls(id=int(d.id), **d.to_dict()) if d.exists else None

    @classmethod
    def get_or_404(cls, doc_id):
        obj = cls.get(doc_id)
        if not obj:
            abort(404)
        return obj

    @classmethod
    def load_all(cls):
        """All books, sorted by title."""
        return sorted(
            [cls(id=int(d.id), **d.to_dict())
             for d in get_db().collection(cls._COL).stream()],
            key=lambda b: (b.title or "").lower(),
        )

    @classmethod
    def count(cls):
        return sum(1 for _ in get_db().collection(cls._COL).stream())

    @classmethod
    def search(cls, q=None, category=None, cdu=None, available_only=False):
        books = cls.load_all()
        if q:
            ql = q.lower()
            books = [b for b in books
                     if ql in (b.title or "").lower()
                     or ql in (b.author or "").lower()
                     or ql in (b.isbn or "").lower()]
        if category:
            books = [b for b in books if b.category == category]
        if cdu:
            books = [b for b in books if b.cdu == cdu]
        if available_only:
            books = [b for b in books if b.is_available]
        return books

    @classmethod
    def distinct_categories(cls):
        return sorted({d.to_dict().get("category")
                       for d in get_db().collection(cls._COL).stream()
                       if d.to_dict().get("category")})

    @classmethod
    def distinct_cdus(cls):
        return sorted({d.to_dict().get("cdu")
                       for d in get_db().collection(cls._COL).stream()
                       if d.to_dict().get("cdu")})

    def __repr__(self):
        return f"<Book {self.title}>"


# ═══════════════════════════════════════════════════════════════
#  STUDENT
# ═══════════════════════════════════════════════════════════════

class Student:
    _COL = "students"

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.student_id = kw.get("student_id", "")
        self.first_name = kw.get("first_name", "")
        self.last_name = kw.get("last_name", "")
        self.email = kw.get("email")
        self.phone = kw.get("phone")
        self.grade = kw.get("grade")
        self.group_name = kw.get("group_name")
        self.max_loans = kw.get("max_loans")
        if self.max_loans is not None:
            try:
                self.max_loans = int(self.max_loans)
            except (ValueError, TypeError):
                self.max_loans = None
        self.is_active = kw.get("is_active", True)
        self.notes = kw.get("notes")
        self.created_at = _dt(kw.get("created_at")) or datetime.utcnow()
        self.updated_at = _dt(kw.get("updated_at")) or datetime.utcnow()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def active_loans_count(self):
        return sum(
            1 for d in get_db().collection("loans")
            .where("student_id", "==", self.id).stream()
            if d.to_dict().get("returned_at") is None
        )

    def can_borrow(self, max_global):
        limit = self.max_loans if self.max_loans is not None else max_global
        return self.active_loans_count < limit

    @property
    def effective_max_loans(self):
        from flask import current_app
        return (self.max_loans if self.max_loans is not None
                else current_app.config["MAX_LOANS_PER_STUDENT"])

    @property
    def total_books_read(self):
        return sum(
            1 for d in get_db().collection("loans")
            .where("student_id", "==", self.id).stream()
            if d.to_dict().get("returned_at") is not None
        )

    @property
    def ratings_count(self):
        """Number of ratings by this student."""
        return sum(1 for _ in get_db().collection("ratings")
                   .where("student_id", "==", self.id).stream())

    # Persistence
    def _to_dict(self):
        return dict(
            student_id=self.student_id,
            first_name=self.first_name, last_name=self.last_name,
            email=self.email, phone=self.phone,
            grade=self.grade, group_name=self.group_name,
            max_loans=self.max_loans, is_active=self.is_active,
            notes=self.notes,
            created_at=self.created_at, updated_at=self.updated_at,
        )

    def save(self):
        self.updated_at = datetime.utcnow()
        if self.id is None:
            self.id = _next_id(self._COL)
            self.created_at = datetime.utcnow()
        get_db().collection(self._COL).document(str(self.id)).set(self._to_dict())

    def delete(self):
        for d in get_db().collection("loans").where("student_id", "==", self.id).stream():
            d.reference.delete()
        for d in get_db().collection("ratings").where("student_id", "==", self.id).stream():
            d.reference.delete()
        get_db().collection(self._COL).document(str(self.id)).delete()

    # Queries
    @classmethod
    def get(cls, doc_id):
        if doc_id is None:
            return None
        d = get_db().collection(cls._COL).document(str(doc_id)).get()
        return cls(id=int(d.id), **d.to_dict()) if d.exists else None

    @classmethod
    def get_or_404(cls, doc_id):
        obj = cls.get(doc_id)
        if not obj:
            abort(404)
        return obj

    @classmethod
    def load_all(cls):
        """All students, sorted by last_name, first_name."""
        return sorted(
            [cls(id=int(d.id), **d.to_dict())
             for d in get_db().collection(cls._COL).stream()],
            key=lambda s: ((s.last_name or "").lower(),
                           (s.first_name or "").lower()),
        )

    @classmethod
    def count(cls):
        return sum(1 for _ in get_db().collection(cls._COL).stream())

    @classmethod
    def search(cls, q=None, grade=None, group=None):
        students = cls.load_all()
        if q:
            ql = q.lower()
            students = [s for s in students
                        if ql in (s.first_name or "").lower()
                        or ql in (s.last_name or "").lower()
                        or ql in (s.student_id or "").lower()
                        or ql in (s.email or "").lower()]
        if grade:
            students = [s for s in students if s.grade == grade]
        if group:
            students = [s for s in students if s.group_name == group]
        return students

    @classmethod
    def distinct_grades(cls):
        return sorted({d.to_dict().get("grade")
                       for d in get_db().collection(cls._COL).stream()
                       if d.to_dict().get("grade")})

    @classmethod
    def distinct_groups(cls):
        return sorted({d.to_dict().get("group_name")
                       for d in get_db().collection(cls._COL).stream()
                       if d.to_dict().get("group_name")})

    def __repr__(self):
        return f"<Student {self.full_name}>"


# ═══════════════════════════════════════════════════════════════
#  LOAN
# ═══════════════════════════════════════════════════════════════

class Loan:
    _COL = "loans"

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.book_id = kw.get("book_id")
        if self.book_id is not None:
            self.book_id = int(self.book_id)
        self.student_id = kw.get("student_id")
        if self.student_id is not None:
            self.student_id = int(self.student_id)
        self.borrowed_at = _dt(kw.get("borrowed_at")) or datetime.utcnow()
        self.due_date = _to_date(kw.get("due_date"))
        self.returned_at = _dt(kw.get("returned_at"))
        self.renewals = int(kw.get("renewals", 0) or 0)
        self.notes = kw.get("notes")
        self.created_at = _dt(kw.get("created_at")) or datetime.utcnow()
        # Lazy-loaded relationships
        self._book = kw.get("_book")
        self._student = kw.get("_student")

    # Relationships
    @property
    def book(self):
        if self._book is None and self.book_id is not None:
            self._book = Book.get(self.book_id)
        return self._book

    @property
    def student(self):
        if self._student is None and self.student_id is not None:
            self._student = Student.get(self.student_id)
        return self._student

    # Computed
    @property
    def is_active(self):
        return self.returned_at is None

    @property
    def is_overdue(self):
        if self.returned_at:
            return False
        return self.due_date is not None and date.today() > self.due_date

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (date.today() - self.due_date).days

    @property
    def status(self):
        if self.returned_at:
            return "returned"
        if self.is_overdue:
            return "overdue"
        return "active"

    # Persistence
    def _to_dict(self):
        return dict(
            book_id=self.book_id, student_id=self.student_id,
            borrowed_at=self.borrowed_at,
            due_date=self.due_date.isoformat() if self.due_date else None,
            returned_at=self.returned_at,
            renewals=self.renewals, notes=self.notes,
            created_at=self.created_at,
        )

    def save(self):
        if self.id is None:
            self.id = _next_id(self._COL)
            self.created_at = datetime.utcnow()
        get_db().collection(self._COL).document(str(self.id)).set(self._to_dict())

    def delete(self):
        get_db().collection(self._COL).document(str(self.id)).delete()

    # Queries
    @classmethod
    def get(cls, doc_id):
        if doc_id is None:
            return None
        d = get_db().collection(cls._COL).document(str(doc_id)).get()
        return cls(id=int(d.id), **d.to_dict()) if d.exists else None

    @classmethod
    def get_or_404(cls, doc_id):
        obj = cls.get(doc_id)
        if not obj:
            abort(404)
        return obj

    @classmethod
    def load_all(cls):
        """All loans, newest first."""
        loans = [cls(id=int(d.id), **d.to_dict())
                 for d in get_db().collection(cls._COL).stream()]
        return sorted(loans,
                      key=lambda l: l.borrowed_at or datetime.min,
                      reverse=True)

    @classmethod
    def find_active_for_book_student(cls, book_id, student_id):
        """Check if a student already has an active loan for a specific book."""
        for d in (get_db().collection(cls._COL)
                  .where("book_id", "==", book_id).stream()):
            data = d.to_dict()
            if data.get("student_id") == student_id and data.get("returned_at") is None:
                return cls(id=int(d.id), **data)
        return None

    @classmethod
    def preload(cls, loans):
        """Batch-load book and student refs for a list of loans."""
        book_ids = {l.book_id for l in loans if l.book_id}
        student_ids = {l.student_id for l in loans if l.student_id}
        books = {}
        for bid in book_ids:
            b = Book.get(bid)
            if b:
                books[bid] = b
        students = {}
        for sid in student_ids:
            s = Student.get(sid)
            if s:
                students[sid] = s
        for loan in loans:
            loan._book = books.get(loan.book_id)
            loan._student = students.get(loan.student_id)
        return loans

    def __repr__(self):
        return f"<Loan Book:{self.book_id} Student:{self.student_id}>"


# ═══════════════════════════════════════════════════════════════
#  RATING
# ═══════════════════════════════════════════════════════════════

class Rating:
    _COL = "ratings"

    def __init__(self, **kw):
        self.id = kw.get("id")
        self.book_id = kw.get("book_id")
        if self.book_id is not None:
            self.book_id = int(self.book_id)
        self.student_id = kw.get("student_id")
        if self.student_id is not None:
            self.student_id = int(self.student_id)
        self.stars = int(kw.get("stars", 0) or 0)
        self.created_at = _dt(kw.get("created_at")) or datetime.utcnow()
        self._book = kw.get("_book")
        self._student = kw.get("_student")

    # Lazy relationships
    @property
    def book(self):
        if self._book is None and self.book_id:
            self._book = Book.get(self.book_id)
        return self._book

    @property
    def student(self):
        if self._student is None and self.student_id:
            self._student = Student.get(self.student_id)
        return self._student

    # Persistence
    def _to_dict(self):
        return dict(
            book_id=self.book_id, student_id=self.student_id,
            stars=self.stars, created_at=self.created_at,
        )

    def save(self):
        if self.id is None:
            self.id = _next_id(self._COL)
        get_db().collection(self._COL).document(str(self.id)).set(self._to_dict())

    def delete(self):
        get_db().collection(self._COL).document(str(self.id)).delete()

    # Queries
    @classmethod
    def find_by_book_student(cls, book_id, student_id):
        for d in (get_db().collection(cls._COL)
                  .where("book_id", "==", book_id).stream()):
            data = d.to_dict()
            if data.get("student_id") == student_id:
                return cls(id=int(d.id), **data)
        return None

    @classmethod
    def find_by_book(cls, book_id):
        return sorted(
            [cls(id=int(d.id), **d.to_dict())
             for d in get_db().collection(cls._COL)
             .where("book_id", "==", book_id).stream()],
            key=lambda r: r.created_at or datetime.min, reverse=True,
        )

    @classmethod
    def find_by_student(cls, student_id):
        return [cls(id=int(d.id), **d.to_dict())
                for d in get_db().collection(cls._COL)
                .where("student_id", "==", student_id).stream()]

    def __repr__(self):
        return f"<Rating Book:{self.book_id} Stars:{self.stars}>"
