from datetime import datetime, date
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=True, index=True)  # Código libro
    title = db.Column(db.String(300), nullable=False, index=True)
    author = db.Column(db.String(200), nullable=True, index=True)
    publisher = db.Column(db.String(200), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    cdu = db.Column(db.String(10), nullable=True, index=True)  # CDU classification
    category = db.Column(db.String(100), nullable=True, index=True)
    location = db.Column(db.String(100), nullable=True)  # shelf / section
    copies_total = db.Column(db.Integer, default=1)
    description = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(50), default="Español")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loans = db.relationship("Loan", backref="book", lazy="dynamic")

    @property
    def copies_available(self):
        active = self.loans.filter(Loan.returned_at.is_(None)).count()
        return max(0, self.copies_total - active)

    @property
    def is_available(self):
        return self.copies_available > 0

    @property
    def avg_rating(self):
        """Average star rating, or None if no ratings."""
        result = db.session.query(func.avg(Rating.stars)).filter(Rating.book_id == self.id).scalar()
        return round(result, 1) if result else None

    @property
    def rating_count(self):
        return self.ratings.count()

    def __repr__(self):
        return f"<Book {self.title}>"


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)  # Nº lector
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True, default="")
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    grade = db.Column(db.String(50), nullable=True)   # curso
    group_name = db.Column(db.String(50), nullable=True)   # grupo / clase
    max_loans = db.Column(db.Integer, nullable=True)  # override per-student, NULL = use global
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    loans = db.relationship("Loan", backref="student", lazy="dynamic")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_loans_count(self):
        return self.loans.filter(Loan.returned_at.is_(None)).count()

    def can_borrow(self, max_global):
        limit = self.max_loans if self.max_loans is not None else max_global
        return self.active_loans_count < limit

    @property
    def effective_max_loans(self):
        from flask import current_app
        return self.max_loans if self.max_loans is not None else current_app.config["MAX_LOANS_PER_STUDENT"]

    @property
    def total_books_read(self):
        return self.loans.filter(Loan.returned_at.isnot(None)).count()

    def __repr__(self):
        return f"<Student {self.full_name}>"


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    borrowed_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=False)
    returned_at = db.Column(db.DateTime, nullable=True)
    renewals = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_active(self):
        return self.returned_at is None

    @property
    def is_overdue(self):
        if self.returned_at:
            return False
        return date.today() > self.due_date

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

    def __repr__(self):
        return f"<Loan Book:{self.book_id} Student:{self.student_id}>"


class Setting(db.Model):
    """Key-value store for app settings."""
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(300), nullable=True)


class Rating(db.Model):
    """Star ratings (1-5) for books, given by students after reading."""
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    stars = db.Column(db.Integer, nullable=False)  # 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One rating per student per book
    __table_args__ = (db.UniqueConstraint("book_id", "student_id", name="uq_rating_book_student"),)

    book = db.relationship("Book", backref=db.backref("ratings", lazy="dynamic"))
    student = db.relationship("Student", backref=db.backref("ratings", lazy="dynamic"))

    def __repr__(self):
        return f"<Rating Book:{self.book_id} Student:{self.student_id} Stars:{self.stars}>"
