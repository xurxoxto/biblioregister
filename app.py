"""
BiblioRegister – School Library Management System
"""

from datetime import datetime, date, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    abort,
)
from sqlalchemy import or_, func
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db, Book, Student, Loan, Setting, Rating
from forms import BookForm, StudentForm, LoanForm, SettingsForm, CDU_COLORS, CDU_LABELS, CDU_CHOICES

csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    csrf.init_app(app)

    # ── Helpers ───────────────────────────────────────────────────
    def _init_settings(app_ctx):
        """Load persisted settings on startup."""
        for key in ["MAX_LOANS_PER_STUDENT", "DEFAULT_LOAN_DAYS", "MAX_RENEWALS"]:
            s = db.session.get(Setting, key)
            if s:
                app_ctx.config[key] = int(s.value)

    def _set_setting(key, value):
        s = db.session.get(Setting, key)
        if s:
            s.value = value
        else:
            s = Setting(key=key, value=value)
            db.session.add(s)
        db.session.commit()

    with app.app_context():
        db.create_all()
        _init_settings(app)

    # ── Inject CDU data into all templates ────────────────────────
    @app.context_processor
    def inject_cdu():
        return dict(cdu_colors=CDU_COLORS, cdu_labels=CDU_LABELS)

    # ──────────────────────────────────────────────────────────────
    #  DASHBOARD
    # ──────────────────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        total_books = Book.query.count()
        total_students = Student.query.count()
        active_loans = Loan.query.filter(Loan.returned_at.is_(None)).count()
        overdue_loans = Loan.query.filter(
            Loan.returned_at.is_(None), Loan.due_date < date.today()
        ).count()

        recent_loans = (
            Loan.query.filter(Loan.returned_at.is_(None))
            .order_by(Loan.borrowed_at.desc())
            .limit(10)
            .all()
        )

        overdue_list = (
            Loan.query.filter(
                Loan.returned_at.is_(None), Loan.due_date < date.today()
            )
            .order_by(Loan.due_date.asc())
            .limit(10)
            .all()
        )

        # Stats for charts
        loans_by_category = (
            db.session.query(Book.category, func.count(Loan.id))
            .join(Loan, Loan.book_id == Book.id)
            .filter(Loan.returned_at.is_(None))
            .group_by(Book.category)
            .all()
        )

        # CDU distribution of all books
        cdu_distribution = (
            db.session.query(Book.cdu, func.count(Book.id))
            .filter(Book.cdu.isnot(None), Book.cdu != "")
            .group_by(Book.cdu)
            .order_by(Book.cdu)
            .all()
        )

        return render_template(
            "dashboard.html",
            total_books=total_books,
            total_students=total_students,
            active_loans=active_loans,
            overdue_loans=overdue_loans,
            recent_loans=recent_loans,
            overdue_list=overdue_list,
            loans_by_category=loans_by_category,
            cdu_distribution=cdu_distribution,
        )

    # ──────────────────────────────────────────────────────────────
    #  BOOKS
    # ──────────────────────────────────────────────────────────────
    @app.route("/books")
    def book_list():
        page = request.args.get("page", 1, type=int)
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        cdu_filter = request.args.get("cdu", "").strip()
        available_only = request.args.get("available", "") == "1"

        query = Book.query

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Book.title.ilike(like),
                    Book.author.ilike(like),
                    Book.isbn.ilike(like),
                )
            )
        if category:
            query = query.filter(Book.category == category)
        if cdu_filter:
            query = query.filter(Book.cdu == cdu_filter)

        query = query.order_by(Book.title.asc())
        pagination = query.paginate(page=page, per_page=20, error_out=False)

        if available_only:
            # Post-filter for availability (computed property)
            items = [b for b in pagination.items if b.is_available]
        else:
            items = pagination.items

        categories = [
            r[0]
            for r in db.session.query(Book.category).distinct().order_by(Book.category).all()
            if r[0]
        ]

        cdus_in_use = [
            r[0]
            for r in db.session.query(Book.cdu).distinct().order_by(Book.cdu).all()
            if r[0]
        ]

        return render_template(
            "books/list.html",
            books=items,
            pagination=pagination,
            q=q,
            category=category,
            cdu_filter=cdu_filter,
            available_only=available_only,
            categories=categories,
            cdus_in_use=cdus_in_use,
        )

    @app.route("/books/new", methods=["GET", "POST"])
    def book_new():
        form = BookForm()
        if form.validate_on_submit():
            book = Book(
                isbn=form.isbn.data or None,
                title=form.title.data,
                author=form.author.data,
                publisher=form.publisher.data or None,
                year=form.year.data,
                cdu=form.cdu.data or None,
                category=form.category.data or None,
                location=form.location.data or None,
                copies_total=form.copies_total.data,
                language=form.language.data or "Español",
                description=form.description.data or None,
            )
            db.session.add(book)
            db.session.commit()
            flash(f'Libro "{book.title}" añadido correctamente.', "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template("books/form.html", form=form, editing=False)

    @app.route("/books/<int:book_id>")
    def book_detail(book_id):
        book = Book.query.get_or_404(book_id)
        active_loans = book.loans.filter(Loan.returned_at.is_(None)).all()
        history = (
            book.loans.filter(Loan.returned_at.isnot(None))
            .order_by(Loan.returned_at.desc())
            .limit(20)
            .all()
        )
        book_ratings = (
            Rating.query.filter_by(book_id=book.id)
            .order_by(Rating.created_at.desc())
            .all()
        )
        return render_template(
            "books/detail.html",
            book=book,
            active_loans=active_loans,
            history=history,
            book_ratings=book_ratings,
        )

    @app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
    def book_edit(book_id):
        book = Book.query.get_or_404(book_id)
        form = BookForm(obj=book)
        if form.validate_on_submit():
            form.populate_obj(book)
            db.session.commit()
            flash(f'Libro "{book.title}" actualizado.', "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template("books/form.html", form=form, editing=True, book=book)

    @app.route("/books/<int:book_id>/delete", methods=["POST"])
    def book_delete(book_id):
        book = Book.query.get_or_404(book_id)
        if book.loans.filter(Loan.returned_at.is_(None)).count() > 0:
            flash("No se puede eliminar: hay préstamos activos.", "danger")
            return redirect(url_for("book_detail", book_id=book.id))
        db.session.delete(book)
        db.session.commit()
        flash(f'Libro "{book.title}" eliminado.', "warning")
        return redirect(url_for("book_list"))

    # ──────────────────────────────────────────────────────────────
    #  STUDENTS
    # ──────────────────────────────────────────────────────────────
    @app.route("/students")
    def student_list():
        page = request.args.get("page", 1, type=int)
        q = request.args.get("q", "").strip()
        grade = request.args.get("grade", "").strip()
        group = request.args.get("group", "").strip()

        query = Student.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Student.first_name.ilike(like),
                    Student.last_name.ilike(like),
                    Student.student_id.ilike(like),
                    Student.email.ilike(like),
                )
            )
        if grade:
            query = query.filter(Student.grade == grade)
        if group:
            query = query.filter(Student.group_name == group)

        query = query.order_by(Student.last_name.asc(), Student.first_name.asc())
        pagination = query.paginate(page=page, per_page=20, error_out=False)

        grades = [
            r[0]
            for r in db.session.query(Student.grade).distinct().order_by(Student.grade).all()
            if r[0]
        ]
        groups = [
            r[0]
            for r in db.session.query(Student.group_name)
            .distinct()
            .order_by(Student.group_name)
            .all()
            if r[0]
        ]

        return render_template(
            "students/list.html",
            students=pagination.items,
            pagination=pagination,
            q=q,
            grade=grade,
            group=group,
            grades=grades,
            groups=groups,
        )

    @app.route("/students/new", methods=["GET", "POST"])
    def student_new():
        form = StudentForm()
        if form.validate_on_submit():
            student = Student(
                student_id=form.student_id.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data or None,
                phone=form.phone.data or None,
                grade=form.grade.data or None,
                group_name=form.group_name.data or None,
                max_loans=form.max_loans.data if form.max_loans.data is not None else None,
                is_active=form.is_active.data,
                notes=form.notes.data or None,
            )
            db.session.add(student)
            db.session.commit()
            flash(f"Alumno {student.full_name} registrado.", "success")
            return redirect(url_for("student_detail", student_id=student.id))
        return render_template("students/form.html", form=form, editing=False)

    @app.route("/students/<int:student_id>")
    def student_detail(student_id):
        student = Student.query.get_or_404(student_id)
        active_loans = student.loans.filter(Loan.returned_at.is_(None)).all()
        history = (
            student.loans.filter(Loan.returned_at.isnot(None))
            .order_by(Loan.returned_at.desc())
            .all()
        )
        # Get student's ratings keyed by book_id for easy lookup
        student_ratings = {
            r.book_id: r.stars
            for r in Rating.query.filter_by(student_id=student.id).all()
        }
        return render_template(
            "students/detail.html",
            student=student,
            active_loans=active_loans,
            history=history,
            student_ratings=student_ratings,
        )

    @app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
    def student_edit(student_id):
        student = Student.query.get_or_404(student_id)
        form = StudentForm(obj=student)
        if form.validate_on_submit():
            form.populate_obj(student)
            if form.max_loans.data is None or form.max_loans.data == "":
                student.max_loans = None
            db.session.commit()
            flash(f"Alumno {student.full_name} actualizado.", "success")
            return redirect(url_for("student_detail", student_id=student.id))
        return render_template(
            "students/form.html", form=form, editing=True, student=student
        )

    @app.route("/students/<int:student_id>/delete", methods=["POST"])
    def student_delete(student_id):
        student = Student.query.get_or_404(student_id)
        if student.loans.filter(Loan.returned_at.is_(None)).count() > 0:
            flash("No se puede eliminar: tiene préstamos activos.", "danger")
            return redirect(url_for("student_detail", student_id=student.id))
        db.session.delete(student)
        db.session.commit()
        flash(f"Alumno {student.full_name} eliminado.", "warning")
        return redirect(url_for("student_list"))

    # ──────────────────────────────────────────────────────────────
    #  LOANS
    # ──────────────────────────────────────────────────────────────
    @app.route("/loans")
    def loan_list():
        page = request.args.get("page", 1, type=int)
        status_filter = request.args.get("status", "active")
        q = request.args.get("q", "").strip()
        student_filter = request.args.get("student_id", "", type=str).strip()
        grade_filter = request.args.get("grade", "").strip()

        query = Loan.query.join(Book).join(Student)

        if status_filter == "active":
            query = query.filter(Loan.returned_at.is_(None))
        elif status_filter == "overdue":
            query = query.filter(
                Loan.returned_at.is_(None), Loan.due_date < date.today()
            )
        elif status_filter == "returned":
            query = query.filter(Loan.returned_at.isnot(None))

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Book.title.ilike(like),
                    Student.first_name.ilike(like),
                    Student.last_name.ilike(like),
                    Student.student_id.ilike(like),
                )
            )

        if student_filter:
            query = query.filter(Student.id == int(student_filter))

        if grade_filter:
            query = query.filter(Student.grade == grade_filter)

        query = query.order_by(Loan.borrowed_at.desc())
        pagination = query.paginate(page=page, per_page=20, error_out=False)

        grades = [
            r[0]
            for r in db.session.query(Student.grade).distinct().order_by(Student.grade).all()
            if r[0]
        ]

        return render_template(
            "loans/list.html",
            loans=pagination.items,
            pagination=pagination,
            status_filter=status_filter,
            q=q,
            student_filter=student_filter,
            grade_filter=grade_filter,
            grades=grades,
        )

    @app.route("/loans/checkout", methods=["GET", "POST"])
    def loan_checkout():
        if request.method == "POST":
            book_id = request.form.get("book_id", type=int)
            student_id_val = request.form.get("student_id", type=int)
            due_date_str = request.form.get("due_date", "")
            notes = request.form.get("notes", "").strip()

            book = Book.query.get_or_404(book_id)
            student = Student.query.get_or_404(student_id_val)

            # Validations
            if not book.is_available:
                flash("Este libro no tiene ejemplares disponibles.", "danger")
                return redirect(url_for("loan_checkout"))

            if not student.is_active:
                flash("Este alumno no está activo.", "danger")
                return redirect(url_for("loan_checkout"))

            max_loans = app.config["MAX_LOANS_PER_STUDENT"]
            if not student.can_borrow(max_loans):
                flash(
                    f"El alumno ya tiene el máximo de préstamos ({student.effective_max_loans}).",
                    "danger",
                )
                return redirect(url_for("loan_checkout"))

            # Check if student already has this book
            existing = Loan.query.filter_by(
                book_id=book.id, student_id=student.id
            ).filter(Loan.returned_at.is_(None)).first()
            if existing:
                flash("El alumno ya tiene este libro en préstamo.", "warning")
                return redirect(url_for("loan_checkout"))

            # Parse borrowed date
            borrowed_date_str = request.form.get("borrowed_date", "")
            try:
                borrowed = datetime.strptime(borrowed_date_str, "%Y-%m-%d")
            except ValueError:
                borrowed = datetime.utcnow()

            # Parse due date
            try:
                due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                due = borrowed.date() + timedelta(days=app.config["DEFAULT_LOAN_DAYS"])

            loan = Loan(
                book_id=book.id,
                student_id=student.id,
                borrowed_at=borrowed,
                due_date=due,
                notes=notes or None,
            )
            db.session.add(loan)
            db.session.commit()
            flash(
                f'Préstamo registrado: "{book.title}" → {student.full_name}', "success"
            )
            return redirect(url_for("loan_list"))

        default_borrowed = date.today()
        default_due = date.today() + timedelta(days=app.config["DEFAULT_LOAN_DAYS"])
        return render_template("loans/checkout.html", default_borrowed=default_borrowed, default_due=default_due)

    @app.route("/loans/<int:loan_id>/return", methods=["POST"])
    def loan_return(loan_id):
        loan = Loan.query.get_or_404(loan_id)
        if loan.returned_at:
            flash("Este préstamo ya fue devuelto.", "info")
            next_url = request.form.get("next", url_for("loan_list"))
            return redirect(next_url)
        else:
            loan.returned_at = datetime.utcnow()
            db.session.commit()
            # Check if student already rated this book
            existing_rating = Rating.query.filter_by(
                book_id=loan.book_id, student_id=loan.student_id
            ).first()
            if not existing_rating:
                # Redirect to rate page
                return redirect(url_for("rate_book", book_id=loan.book_id, student_id=loan.student_id))
            else:
                flash(
                    f'Libro "{loan.book.title}" devuelto por {loan.student.full_name}.',
                    "success",
                )
                next_url = request.form.get("next", url_for("loan_list"))
                return redirect(next_url)

    @app.route("/loans/<int:loan_id>/renew", methods=["POST"])
    def loan_renew(loan_id):
        loan = Loan.query.get_or_404(loan_id)
        max_renewals = app.config["MAX_RENEWALS"]
        if loan.returned_at:
            flash("No se puede renovar un préstamo ya devuelto.", "warning")
        elif loan.renewals >= max_renewals:
            flash(f"Se ha alcanzado el máximo de renovaciones ({max_renewals}).", "danger")
        else:
            loan.renewals += 1
            loan.due_date = date.today() + timedelta(days=app.config["DEFAULT_LOAN_DAYS"])
            db.session.commit()
            flash(
                f"Préstamo renovado. Nueva fecha: {loan.due_date.strftime('%d/%m/%Y')}",
                "success",
            )
        next_url = request.form.get("next", url_for("loan_list"))
        return redirect(next_url)

    @app.route("/loans/<int:loan_id>/update-due", methods=["POST"])
    def loan_update_due(loan_id):
        loan = Loan.query.get_or_404(loan_id)
        new_due_str = request.form.get("due_date", "")
        try:
            new_due = datetime.strptime(new_due_str, "%Y-%m-%d").date()
            loan.due_date = new_due
            db.session.commit()
            flash(
                f"Data límite actualizada a {new_due.strftime('%d/%m/%Y')}.",
                "success",
            )
        except ValueError:
            flash("Data non válida.", "danger")
        next_url = request.form.get("next", url_for("loan_list"))
        return redirect(next_url)

    # ──────────────────────────────────────────────────────────────
    #  RATINGS
    # ──────────────────────────────────────────────────────────────
    @app.route("/rate/<int:book_id>/<int:student_id>", methods=["GET", "POST"])
    def rate_book(book_id, student_id):
        book = Book.query.get_or_404(book_id)
        student = Student.query.get_or_404(student_id)

        if request.method == "POST":
            stars = request.form.get("stars", type=int)
            if stars and 1 <= stars <= 5:
                existing = Rating.query.filter_by(
                    book_id=book.id, student_id=student.id
                ).first()
                if existing:
                    existing.stars = stars
                else:
                    rating = Rating(
                        book_id=book.id, student_id=student.id, stars=stars
                    )
                    db.session.add(rating)
                db.session.commit()
                flash(
                    f'{student.first_name} valorou "{book.title}" con {stars} ⭐',
                    "success",
                )
            else:
                flash(
                    f'Libro "{book.title}" devuelto por {student.full_name}.',
                    "success",
                )
            return redirect(url_for("loan_list"))

        # GET — show the rating page
        return render_template(
            "loans/rate.html", book=book, student=student
        )

    @app.route("/rate/<int:book_id>/<int:student_id>/quick", methods=["POST"])
    def rate_book_quick(book_id, student_id):
        """AJAX-style quick rate from history tables."""
        book = Book.query.get_or_404(book_id)
        student = Student.query.get_or_404(student_id)
        stars = request.form.get("stars", type=int)
        if stars and 1 <= stars <= 5:
            existing = Rating.query.filter_by(
                book_id=book.id, student_id=student.id
            ).first()
            if existing:
                existing.stars = stars
            else:
                rating = Rating(
                    book_id=book.id, student_id=student.id, stars=stars
                )
                db.session.add(rating)
            db.session.commit()
            flash(f"Valoración actualizada: {stars} ⭐", "success")
        next_url = request.form.get("next", url_for("loan_list"))
        return redirect(next_url)

    # ──────────────────────────────────────────────────────────────
    #  API – Live search (AJAX)
    # ──────────────────────────────────────────────────────────────
    @app.route("/api/books/search")
    def api_book_search():
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])
        like = f"%{q}%"
        books = (
            Book.query.filter(
                or_(
                    Book.title.ilike(like),
                    Book.isbn.ilike(like),
                    Book.author.ilike(like),
                )
            )
            .limit(15)
            .all()
        )
        return jsonify(
            [
                {
                    "id": b.id,
                    "title": b.title,
                    "author": b.author,
                    "isbn": b.isbn or "",
                    "cdu": b.cdu or "",
                    "available": b.copies_available,
                    "is_available": b.is_available,
                }
                for b in books
            ]
        )

    @app.route("/api/students/search")
    def api_student_search():
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])
        like = f"%{q}%"
        students = (
            Student.query.filter(
                Student.is_active.is_(True),
                or_(
                    Student.first_name.ilike(like),
                    Student.last_name.ilike(like),
                    Student.student_id.ilike(like),
                ),
            )
            .limit(15)
            .all()
        )
        max_global = app.config["MAX_LOANS_PER_STUDENT"]
        return jsonify(
            [
                {
                    "id": s.id,
                    "student_id": s.student_id,
                    "full_name": s.full_name,
                    "grade": s.grade or "",
                    "group": s.group_name or "",
                    "active_loans": s.active_loans_count,
                    "can_borrow": s.can_borrow(max_global),
                    "max_loans": s.effective_max_loans,
                }
                for s in students
            ]
        )

    # ──────────────────────────────────────────────────────────────
    #  SETTINGS
    # ──────────────────────────────────────────────────────────────
    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        form = SettingsForm()
        if request.method == "GET":
            form.max_loans_per_student.data = app.config["MAX_LOANS_PER_STUDENT"]
            form.default_loan_days.data = app.config["DEFAULT_LOAN_DAYS"]
            form.max_renewals.data = app.config["MAX_RENEWALS"]

        if form.validate_on_submit():
            app.config["MAX_LOANS_PER_STUDENT"] = form.max_loans_per_student.data
            app.config["DEFAULT_LOAN_DAYS"] = form.default_loan_days.data
            app.config["MAX_RENEWALS"] = form.max_renewals.data

            # Persist to DB
            _set_setting("MAX_LOANS_PER_STUDENT", str(form.max_loans_per_student.data))
            _set_setting("DEFAULT_LOAN_DAYS", str(form.default_loan_days.data))
            _set_setting("MAX_RENEWALS", str(form.max_renewals.data))
            flash("Configuración guardada.", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", form=form)

    # ──────────────────────────────────────────────────────────────
    #  REPORTS
    # ──────────────────────────────────────────────────────────────
    @app.route("/reports")
    def reports():
        # Most borrowed books
        popular = (
            db.session.query(Book, func.count(Loan.id).label("loan_count"))
            .join(Loan, Loan.book_id == Book.id)
            .group_by(Book.id)
            .order_by(func.count(Loan.id).desc())
            .limit(20)
            .all()
        )

        # Most active readers
        readers = (
            db.session.query(Student, func.count(Loan.id).label("loan_count"))
            .join(Loan, Loan.student_id == Student.id)
            .group_by(Student.id)
            .order_by(func.count(Loan.id).desc())
            .limit(20)
            .all()
        )

        # Loans per month (last 12 months)
        monthly = (
            db.session.query(
                func.strftime("%Y-%m", Loan.borrowed_at).label("month"),
                func.count(Loan.id),
            )
            .group_by("month")
            .order_by(func.strftime("%Y-%m", Loan.borrowed_at).desc())
            .limit(12)
            .all()
        )

        # Overdue students
        overdue_students = (
            db.session.query(Student, func.count(Loan.id).label("overdue_count"))
            .join(Loan, Loan.student_id == Student.id)
            .filter(Loan.returned_at.is_(None), Loan.due_date < date.today())
            .group_by(Student.id)
            .order_by(func.count(Loan.id).desc())
            .all()
        )

        # CDU distribution
        cdu_distribution = (
            db.session.query(Book.cdu, func.count(Book.id))
            .filter(Book.cdu.isnot(None), Book.cdu != "")
            .group_by(Book.cdu)
            .order_by(Book.cdu)
            .all()
        )

        return render_template(
            "reports.html",
            popular=popular,
            readers=readers,
            monthly=list(reversed(monthly)),
            overdue_students=overdue_students,
            cdu_distribution=cdu_distribution,
        )

    # ──────────────────────────────────────────────────────────────
    #  DATABASE MANAGEMENT
    # ──────────────────────────────────────────────────────────────
    @app.route("/reset-db", methods=["GET"])
    def reset_db():
        import os

        db.drop_all()
        db.create_all()
        flash("Base de datos reseteada correctamente.", "warning")
        return redirect(url_for("settings"))

    @app.route("/reimport-data", methods=["GET"])
    def reimport_data():
        import subprocess, sys

        db.drop_all()
        db.create_all()
        try:
            result = subprocess.run(
                [sys.executable, "import_numbers.py"],
                capture_output=True,
                text=True,
                cwd=app.root_path,
            )
            if result.returncode == 0:
                flash("Datos reimportados correctamente.", "success")
            else:
                flash(f"Erro ao reimportar: {result.stderr[:300]}", "danger")
        except Exception as e:
            flash(f"Erro ao reimportar: {str(e)}", "danger")
        return redirect(url_for("settings"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
