"""
BiblioRegister – School Library Management System
Backend powered by Google Cloud Firestore.
"""

from datetime import datetime, date, timedelta
from collections import Counter
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
from flask_wtf.csrf import CSRFProtect
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from config import Config
from models import (
    init_firebase, get_db, drop_all, drop_data, paginate_list,
    User, Book, Student, Loan, Setting, Rating,
)
from forms import (
    BookForm, StudentForm, LoanForm, SettingsForm,
    LoginForm, ChangePasswordForm, CreateUserForm,
    CDU_COLORS, CDU_LABELS, CDU_CHOICES,
)

csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    csrf.init_app(app)

    # Firestore
    init_firebase(app)

    # Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Inicia sesión para acceder."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(int(user_id))

    # ── Helpers ───────────────────────────────────────────────────
    def _init_settings():
        """Load persisted settings on startup."""
        for key in ["MAX_LOANS_PER_STUDENT", "DEFAULT_LOAN_DAYS", "MAX_RENEWALS"]:
            s = Setting.get(key)
            if s:
                app.config[key] = int(s.value)

    def _set_setting(key, value):
        Setting.set_value(key, str(value))

    def _create_default_admin():
        """Create admin user on first run if no users exist."""
        if User.count() == 0:
            admin = User(
                username=app.config.get("ADMIN_USERNAME", "admin"),
                display_name="Administrador",
                is_admin=True,
            )
            admin.set_password(app.config.get("ADMIN_PASSWORD", "biblio2025"))
            admin.save()

    # Defer Firestore calls to first request (avoids gRPC startup hang)
    # _init_settings()
    # _create_default_admin()

    # ── Health check (Cloud Scheduler / uptime monitors) ───────
    @app.route("/healthz")
    def healthz():
        return "ok", 200

    # ── Require login ─────────────────────────────────────────────
    _initialized = {"done": False}

    @app.before_request
    def require_login():
        # Lazy init: run Firestore queries on first request, not at startup
        if not _initialized["done"]:
            _initialized["done"] = True
            _init_settings()
            _create_default_admin()

        allowed = ("login", "static", "healthz")
        if request.endpoint and request.endpoint not in allowed:
            if not current_user.is_authenticated:
                return redirect(url_for("login"))

    @app.context_processor
    def inject_cdu():
        return dict(cdu_colors=CDU_COLORS, cdu_labels=CDU_LABELS)

    # ──────────────────────────────────────────────────────────────
    #  AUTHENTICATION
    # ──────────────────────────────────────────────────────────────
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.find_by_username(form.username.data)
            if user and user.check_password(form.password.data):
                if not user.is_active:
                    flash("Esta cuenta está desactivada.", "danger")
                    return render_template("auth/login.html", form=form)
                login_user(user, remember=True)
                flash(f"Bienvenido/a, {user.display_name or user.username}.", "success")
                return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Usuario o contraseña incorrectos.", "danger")
        return render_template("auth/login.html", form=form)

    @app.route("/logout")
    def logout():
        logout_user()
        flash("Sesión cerrada.", "info")
        return redirect(url_for("login"))

    # ──────────────────────────────────────────────────────────────
    #  DASHBOARD
    # ──────────────────────────────────────────────────────────────
    @app.route("/")
    def dashboard():
        total_books = Book.count()
        total_students = Student.count()
        all_loans = Loan.load_all()

        active_list = [l for l in all_loans if l.returned_at is None]
        active_loans = len(active_list)
        overdue_list_all = [l for l in active_list if l.is_overdue]
        overdue_loans = len(overdue_list_all)

        recent_loans = active_list[:10]
        overdue_display = sorted(overdue_list_all, key=lambda l: l.due_date)[:10]
        Loan.preload(recent_loans + overdue_display)

        # Loans by category
        books_map = {b.id: b for b in Book.load_all()}
        cat_counter = Counter()
        for l in active_list:
            b = books_map.get(l.book_id)
            if b and b.category:
                cat_counter[b.category] += 1
        loans_by_category = list(cat_counter.items())

        # CDU distribution
        cdu_counter = Counter()
        for b in books_map.values():
            if b.cdu:
                cdu_counter[b.cdu] += 1
        cdu_distribution = sorted(cdu_counter.items())

        return render_template(
            "dashboard.html",
            total_books=total_books,
            total_students=total_students,
            active_loans=active_loans,
            overdue_loans=overdue_loans,
            recent_loans=recent_loans,
            overdue_list=overdue_display,
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

        books = Book.search(q=q, category=category, cdu=cdu_filter,
                            available_only=available_only)
        pagination = paginate_list(books, page, 20)
        categories = Book.distinct_categories()
        cdus_in_use = Book.distinct_cdus()

        return render_template(
            "books/list.html",
            books=pagination.items,
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
            book.save()
            flash(f'Libro "{book.title}" añadido correctamente.', "success")
            return redirect(url_for("book_detail", book_id=book.id,
                                    just_created=1))
        return render_template("books/form.html", form=form, editing=False)

    @app.route("/books/<int:book_id>")
    def book_detail(book_id):
        book = Book.get_or_404(book_id)
        # Load all loans for this book
        all_book_loans = [
            Loan(id=int(d.id), **d.to_dict())
            for d in get_db().collection("loans")
            .where("book_id", "==", book_id).stream()
        ]
        active_loans = [l for l in all_book_loans if l.returned_at is None]
        history = sorted(
            [l for l in all_book_loans if l.returned_at is not None],
            key=lambda l: l.returned_at, reverse=True,
        )[:20]
        Loan.preload(active_loans + history)

        book_ratings = Rating.find_by_book(book_id)
        return render_template(
            "books/detail.html",
            book=book,
            active_loans=active_loans,
            history=history,
            book_ratings=book_ratings,
        )

    @app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
    def book_edit(book_id):
        book = Book.get_or_404(book_id)
        form = BookForm(obj=book)
        if form.validate_on_submit():
            form.populate_obj(book)
            book.save()
            flash(f'Libro "{book.title}" actualizado.', "success")
            return redirect(url_for("book_detail", book_id=book.id))
        return render_template("books/form.html", form=form, editing=True, book=book)

    @app.route("/books/<int:book_id>/delete", methods=["POST"])
    def book_delete(book_id):
        book = Book.get_or_404(book_id)
        has_active = any(
            d.to_dict().get("returned_at") is None
            for d in get_db().collection("loans")
            .where("book_id", "==", book_id).stream()
        )
        if has_active:
            flash("No se puede eliminar: hay préstamos activos.", "danger")
            return redirect(url_for("book_detail", book_id=book.id))
        book.delete()
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

        students = Student.search(q=q, grade=grade, group=group)
        pagination = paginate_list(students, page, 20)
        grades = Student.distinct_grades()
        groups = Student.distinct_groups()

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
                max_loans=(form.max_loans.data
                           if form.max_loans.data is not None else None),
                is_active=form.is_active.data,
                notes=form.notes.data or None,
            )
            student.save()
            flash(f"Alumno {student.full_name} registrado.", "success")
            return redirect(url_for("student_detail", student_id=student.id))
        return render_template("students/form.html", form=form, editing=False)

    @app.route("/students/<int:student_id>")
    def student_detail(student_id):
        student = Student.get_or_404(student_id)
        all_student_loans = [
            Loan(id=int(d.id), **d.to_dict())
            for d in get_db().collection("loans")
            .where("student_id", "==", student_id).stream()
        ]
        active_loans = [l for l in all_student_loans if l.returned_at is None]
        history = sorted(
            [l for l in all_student_loans if l.returned_at is not None],
            key=lambda l: l.returned_at, reverse=True,
        )
        Loan.preload(active_loans + history)

        student_ratings = {
            r.book_id: r.stars for r in Rating.find_by_student(student_id)
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
        student = Student.get_or_404(student_id)
        form = StudentForm(obj=student)
        if form.validate_on_submit():
            form.populate_obj(student)
            if form.max_loans.data is None or form.max_loans.data == "":
                student.max_loans = None
            student.save()
            flash(f"Alumno {student.full_name} actualizado.", "success")
            return redirect(url_for("student_detail", student_id=student.id))
        return render_template(
            "students/form.html", form=form, editing=True, student=student
        )

    @app.route("/students/<int:student_id>/delete", methods=["POST"])
    def student_delete(student_id):
        student = Student.get_or_404(student_id)
        has_active = any(
            d.to_dict().get("returned_at") is None
            for d in get_db().collection("loans")
            .where("student_id", "==", student_id).stream()
        )
        if has_active:
            flash("No se puede eliminar: tiene préstamos activos.", "danger")
            return redirect(url_for("student_detail", student_id=student.id))
        student.delete()
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

        all_loans = Loan.load_all()
        Loan.preload(all_loans)

        # Status filter
        if status_filter == "active":
            all_loans = [l for l in all_loans if l.returned_at is None]
        elif status_filter == "overdue":
            all_loans = [l for l in all_loans
                         if l.returned_at is None and l.is_overdue]
        elif status_filter == "returned":
            all_loans = [l for l in all_loans if l.returned_at is not None]

        # Text search across book title + student name
        if q:
            ql = q.lower()
            all_loans = [
                l for l in all_loans
                if (l.book and ql in (l.book.title or "").lower())
                or (l.student and (
                    ql in (l.student.first_name or "").lower()
                    or ql in (l.student.last_name or "").lower()
                    or ql in (l.student.student_id or "").lower()
                ))
            ]

        if student_filter:
            try:
                sid = int(student_filter)
                all_loans = [l for l in all_loans if l.student_id == sid]
            except ValueError:
                pass

        if grade_filter:
            all_loans = [l for l in all_loans
                         if l.student and l.student.grade == grade_filter]

        pagination = paginate_list(all_loans, page, 20)
        grades = Student.distinct_grades()

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

            book = Book.get_or_404(book_id)
            student = Student.get_or_404(student_id_val)

            if not book.is_available:
                flash("Este libro no tiene ejemplares disponibles.", "danger")
                return redirect(url_for("loan_checkout"))
            if not student.is_active:
                flash("Este alumno no está activo.", "danger")
                return redirect(url_for("loan_checkout"))

            max_loans = app.config["MAX_LOANS_PER_STUDENT"]
            if not student.can_borrow(max_loans):
                flash(
                    f"El alumno ya tiene el máximo de préstamos "
                    f"({student.effective_max_loans}).",
                    "danger",
                )
                return redirect(url_for("loan_checkout"))

            existing = Loan.find_active_for_book_student(book.id, student.id)
            if existing:
                flash("El alumno ya tiene este libro en préstamo.", "warning")
                return redirect(url_for("loan_checkout"))

            borrowed_date_str = request.form.get("borrowed_date", "")
            try:
                borrowed = datetime.strptime(borrowed_date_str, "%Y-%m-%d")
            except ValueError:
                borrowed = datetime.utcnow()

            try:
                due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                due = (borrowed.date()
                       + timedelta(days=app.config["DEFAULT_LOAN_DAYS"]))

            loan = Loan(
                book_id=book.id,
                student_id=student.id,
                borrowed_at=borrowed,
                due_date=due,
                notes=notes or None,
            )
            loan.save()
            flash(
                f'Préstamo registrado: "{book.title}" → {student.full_name}',
                "success",
            )
            return redirect(url_for("loan_checkout",
                                    student_id=student.id))

        default_borrowed = date.today()
        default_due = date.today() + timedelta(
            days=app.config["DEFAULT_LOAN_DAYS"])
        return render_template(
            "loans/checkout.html",
            default_borrowed=default_borrowed,
            default_due=default_due,
        )

    @app.route("/loans/<int:loan_id>/return", methods=["POST"])
    def loan_return(loan_id):
        loan = Loan.get_or_404(loan_id)
        if loan.returned_at:
            flash("Este préstamo ya fue devuelto.", "info")
            return redirect(request.form.get("next", url_for("loan_list")))

        loan.returned_at = datetime.utcnow()
        loan.save()

        book = loan.book
        student = loan.student
        book_title = book.title if book else "?"
        student_name = student.full_name if student else "?"

        existing_rating = Rating.find_by_book_student(
            loan.book_id, loan.student_id)
        if not existing_rating:
            rate_url = url_for("rate_book",
                               book_id=loan.book_id,
                               student_id=loan.student_id)
            flash(
                f'Libro "{book_title}" devuelto por {student_name}. '
                f'<a href="{rate_url}" class="alert-link fw-bold">⭐ Valorar libro</a>',
                "success",
            )
        else:
            flash(
                f'Libro "{book_title}" devuelto por {student_name}.',
                "success",
            )
        return redirect(request.form.get("next", url_for("loan_list")))

    @app.route("/loans/<int:loan_id>/renew", methods=["POST"])
    def loan_renew(loan_id):
        loan = Loan.get_or_404(loan_id)
        max_renewals = app.config["MAX_RENEWALS"]
        if loan.returned_at:
            flash("No se puede renovar un préstamo ya devuelto.", "warning")
        elif loan.renewals >= max_renewals:
            flash(
                f"Se ha alcanzado el máximo de renovaciones ({max_renewals}).",
                "danger",
            )
        else:
            loan.renewals += 1
            loan.due_date = (date.today()
                             + timedelta(days=app.config["DEFAULT_LOAN_DAYS"]))
            loan.save()
            flash(
                f"Préstamo renovado. Nueva fecha: "
                f"{loan.due_date.strftime('%d/%m/%Y')}",
                "success",
            )
        return redirect(request.form.get("next", url_for("loan_list")))

    @app.route("/loans/<int:loan_id>/update-due", methods=["POST"])
    def loan_update_due(loan_id):
        loan = Loan.get_or_404(loan_id)
        new_due_str = request.form.get("due_date", "")
        try:
            new_due = datetime.strptime(new_due_str, "%Y-%m-%d").date()
            loan.due_date = new_due
            loan.save()
            flash(
                f"Data límite actualizada a {new_due.strftime('%d/%m/%Y')}.",
                "success",
            )
        except ValueError:
            flash("Data non válida.", "danger")
        return redirect(request.form.get("next", url_for("loan_list")))

    # ──────────────────────────────────────────────────────────────
    #  RATINGS
    # ──────────────────────────────────────────────────────────────
    @app.route("/rate/<int:book_id>/<int:student_id>", methods=["GET", "POST"])
    def rate_book(book_id, student_id):
        book = Book.get_or_404(book_id)
        student = Student.get_or_404(student_id)

        if request.method == "POST":
            stars = request.form.get("stars", type=int)
            if stars and 1 <= stars <= 5:
                existing = Rating.find_by_book_student(book.id, student.id)
                if existing:
                    existing.stars = stars
                    existing.save()
                else:
                    Rating(book_id=book.id,
                           student_id=student.id,
                           stars=stars).save()
                flash(
                    f'{student.first_name} valorou "{book.title}" '
                    f'con {stars} ⭐',
                    "success",
                )
            else:
                flash(
                    f'Libro "{book.title}" devuelto por {student.full_name}.',
                    "success",
                )
            return redirect(url_for("loan_list"))

        return render_template("loans/rate.html", book=book, student=student)

    @app.route("/rate/<int:book_id>/<int:student_id>/quick", methods=["POST"])
    def rate_book_quick(book_id, student_id):
        book = Book.get_or_404(book_id)
        student = Student.get_or_404(student_id)
        stars = request.form.get("stars", type=int)
        if stars and 1 <= stars <= 5:
            existing = Rating.find_by_book_student(book.id, student.id)
            if existing:
                existing.stars = stars
                existing.save()
            else:
                Rating(book_id=book.id,
                       student_id=student.id,
                       stars=stars).save()
            flash(f"Valoración actualizada: {stars} ⭐", "success")
        return redirect(request.form.get("next", url_for("loan_list")))

    # ──────────────────────────────────────────────────────────────
    #  API – Live search (AJAX)
    # ──────────────────────────────────────────────────────────────
    @app.route("/api/books/search")
    def api_book_search():
        q = request.args.get("q", "").strip()
        if len(q) < 1:
            return jsonify([])
        books = Book.search(q=q)[:15]
        return jsonify([
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
        ])

    @app.route("/api/students/search")
    def api_student_search():
        q = request.args.get("q", "").strip()
        if len(q) < 1:
            return jsonify([])
        students = [s for s in Student.search(q=q) if s.is_active][:15]
        max_global = app.config["MAX_LOANS_PER_STUDENT"]
        return jsonify([
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
        ])

    # ──────────────────────────────────────────────────────────────
    #  API – AJAX returns & data endpoints
    # ──────────────────────────────────────────────────────────────
    @app.route("/api/loans/<int:loan_id>/return", methods=["POST"])
    def api_loan_return(loan_id):
        """AJAX endpoint to return a book without page reload."""
        loan = Loan.get(loan_id)
        if not loan:
            return jsonify({"ok": False, "error": "Préstamo no encontrado"}), 404
        if loan.returned_at:
            return jsonify({"ok": False, "error": "Ya devuelto"})
        loan.returned_at = datetime.utcnow()
        loan.save()
        book = loan.book
        student = loan.student
        has_rating = Rating.find_by_book_student(
            loan.book_id, loan.student_id) is not None
        return jsonify({
            "ok": True,
            "loan_id": loan.id,
            "book_id": loan.book_id,
            "student_id": loan.student_id,
            "book_title": book.title if book else "",
            "student_name": student.full_name if student else "",
            "has_rating": has_rating,
        })

    @app.route("/api/students/<int:student_id>/loans")
    def api_student_loans(student_id):
        """Get a student's active loans (for the circulation page)."""
        student = Student.get(student_id)
        if not student:
            return jsonify([])
        loans_docs = list(
            get_db().collection("loans")
            .where("student_id", "==", student_id).stream()
        )
        loans = [
            Loan(id=int(d.id), **d.to_dict())
            for d in loans_docs
            if d.to_dict().get("returned_at") is None
        ]
        Loan.preload(loans)
        return jsonify([
            {
                "id": l.id,
                "book_id": l.book_id,
                "book_title": l.book.title if l.book else "?",
                "book_author": l.book.author if l.book else "",
                "book_cdu": l.book.cdu if l.book else "",
                "borrowed_at": l.borrowed_at.strftime("%d/%m/%Y") if l.borrowed_at else "",
                "due_date": l.due_date.strftime("%d/%m/%Y") if l.due_date else "",
                "is_overdue": l.is_overdue,
                "days_overdue": l.days_overdue,
            }
            for l in sorted(loans,
                            key=lambda x: x.borrowed_at or datetime.min,
                            reverse=True)
        ])

    @app.route("/api/books/<int:book_id>")
    def api_book_get(book_id):
        """Get a single book by ID."""
        book = Book.get(book_id)
        if not book:
            return jsonify({}), 404
        return jsonify({
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "isbn": book.isbn or "",
            "cdu": book.cdu or "",
            "available": book.copies_available,
            "is_available": book.is_available,
        })

    @app.route("/api/students/<int:student_id>")
    def api_student_get(student_id):
        """Get a single student by ID."""
        student = Student.get(student_id)
        if not student:
            return jsonify({}), 404
        max_global = app.config["MAX_LOANS_PER_STUDENT"]
        return jsonify({
            "id": student.id,
            "student_id": student.student_id,
            "full_name": student.full_name,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "grade": student.grade or "",
            "group": student.group_name or "",
            "active_loans": student.active_loans_count,
            "can_borrow": student.can_borrow(max_global),
            "max_loans": student.effective_max_loans,
        })

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
            _set_setting("MAX_LOANS_PER_STUDENT", form.max_loans_per_student.data)
            _set_setting("DEFAULT_LOAN_DAYS", form.default_loan_days.data)
            _set_setting("MAX_RENEWALS", form.max_renewals.data)
            flash("Configuración guardada.", "success")
            return redirect(url_for("settings"))

        return render_template("settings.html", form=form)

    # ──────────────────────────────────────────────────────────────
    #  REPORTS
    # ──────────────────────────────────────────────────────────────
    @app.route("/reports")
    def reports():
        all_loans = Loan.load_all()
        all_books = Book.load_all()
        all_students = Student.load_all()
        books_map = {b.id: b for b in all_books}
        students_map = {s.id: s for s in all_students}

        # Most borrowed books
        book_counter = Counter(l.book_id for l in all_loans)
        popular = [(books_map[bid], cnt)
                   for bid, cnt in book_counter.most_common(20)
                   if bid in books_map]

        # Most active readers
        student_counter = Counter(l.student_id for l in all_loans)
        readers = [(students_map[sid], cnt)
                   for sid, cnt in student_counter.most_common(20)
                   if sid in students_map]

        # Loans per month (last 12)
        month_counter = Counter()
        for l in all_loans:
            if l.borrowed_at:
                month_counter[l.borrowed_at.strftime("%Y-%m")] += 1
        monthly = sorted(month_counter.items())[-12:]

        # Overdue students
        overdue_counter = Counter()
        for l in all_loans:
            if l.returned_at is None and l.is_overdue:
                overdue_counter[l.student_id] += 1
        overdue_students = [(students_map[sid], cnt)
                            for sid, cnt in overdue_counter.most_common()
                            if sid in students_map]

        # CDU distribution
        cdu_counter = Counter(b.cdu for b in all_books if b.cdu)
        cdu_distribution = sorted(cdu_counter.items())

        return render_template(
            "reports.html",
            popular=popular,
            readers=readers,
            monthly=monthly,
            overdue_students=overdue_students,
            cdu_distribution=cdu_distribution,
        )

    # ──────────────────────────────────────────────────────────────
    #  USER MANAGEMENT
    # ──────────────────────────────────────────────────────────────
    @app.route("/users")
    def user_list():
        if not current_user.is_admin:
            flash("Solo los administradores pueden gestionar usuarios.", "danger")
            return redirect(url_for("dashboard"))
        users = User.query_all()
        return render_template("users/list.html", users=users)

    @app.route("/users/new", methods=["GET", "POST"])
    def user_new():
        if not current_user.is_admin:
            flash("Solo los administradores pueden crear usuarios.", "danger")
            return redirect(url_for("dashboard"))
        form = CreateUserForm()
        if form.validate_on_submit():
            if User.find_by_username(form.username.data):
                flash("Ya existe un usuario con ese nombre.", "danger")
            else:
                user = User(
                    username=form.username.data,
                    display_name=form.display_name.data or form.username.data,
                    is_admin=form.is_admin.data,
                )
                user.set_password(form.password.data)
                user.save()
                flash(f"Usuario '{user.username}' creado.", "success")
                return redirect(url_for("user_list"))
        return render_template("users/form.html", form=form)

    @app.route("/users/<int:user_id>/toggle", methods=["POST"])
    def user_toggle(user_id):
        if not current_user.is_admin:
            abort(403)
        user = User.get_or_404(user_id)
        if user.id == current_user.id:
            flash("No puedes desactivarte a ti mismo.", "danger")
        else:
            user.is_active_user = not user.is_active_user
            user.save()
            state = "activado" if user.is_active_user else "desactivado"
            flash(f"Usuario '{user.username}' {state}.", "success")
        return redirect(url_for("user_list"))

    @app.route("/users/<int:user_id>/delete", methods=["POST"])
    def user_delete(user_id):
        if not current_user.is_admin:
            abort(403)
        user = User.get_or_404(user_id)
        if user.id == current_user.id:
            flash("No puedes eliminarte a ti mismo.", "danger")
        else:
            user.delete()
            flash(f"Usuario '{user.username}' eliminado.", "warning")
        return redirect(url_for("user_list"))

    @app.route("/change-password", methods=["GET", "POST"])
    def change_password():
        form = ChangePasswordForm()
        if form.validate_on_submit():
            if not current_user.check_password(form.current_password.data):
                flash("La contraseña actual es incorrecta.", "danger")
            else:
                current_user.set_password(form.new_password.data)
                current_user.save()
                flash("Contraseña actualizada correctamente.", "success")
                return redirect(url_for("settings"))
        return render_template("users/change_password.html", form=form)

    # ──────────────────────────────────────────────────────────────
    #  DATABASE MANAGEMENT
    # ──────────────────────────────────────────────────────────────
    @app.route("/reset-db", methods=["GET"])
    def reset_db():
        drop_all()
        _create_default_admin()
        flash("Base de datos reseteada correctamente.", "warning")
        return redirect(url_for("settings"))

    @app.route("/reimport-data", methods=["GET"])
    def reimport_data():
        import subprocess, sys

        drop_data()
        try:
            result = subprocess.run(
                [sys.executable, "import_numbers.py"],
                capture_output=True, text=True, cwd=app.root_path,
            )
            if result.returncode == 0:
                flash("Datos reimportados correctamente.", "success")
            else:
                flash(f"Erro ao reimportar: {result.stderr[:300]}", "danger")
        except Exception as e:
            flash(f"Erro ao reimportar: {str(e)}", "danger")
        return redirect(url_for("settings"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, host="0.0.0.0", port=5001)
