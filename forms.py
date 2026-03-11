from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    IntegerField,
    TextAreaField,
    SelectField,
    BooleanField,
    DateField,
    HiddenField,
    PasswordField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange, Email, EqualTo


# ── Auth Forms ────────────────────────────────────────────────────────
class LoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Contraseña", validators=[DataRequired()])


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=4, max=128)],
    )
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden.")],
    )


class CreateUserForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=80)])
    display_name = StringField("Nombre", validators=[Optional(), Length(max=150)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=4, max=128)])
    is_admin = BooleanField("Administrador", default=False)


# ── Book Form ─────────────────────────────────────────────────────────

# CDU categories with colors (used in templates too)
CDU_CHOICES = [
    ("", "-- Seleccionar CDU --"),
    ("0", "0 — Xeneralidades"),
    ("1", "1 — Filosofía"),
    ("2", "2 — Relixión"),
    ("3", "3 — Ciencias Sociais"),
    ("5", "5 — Ciencias Naturais"),
    ("6", "6 — Ciencias Aplicadas"),
    ("7", "7 — Arte / Deportes"),
    ("8", "8 — Lingua / Literatura"),
    ("9", "9 — Historia / Xeografía"),
    ("I", "I — Infantil / Imaxinación"),
    ("X", "X — Cómic / Xeral"),
    ("C", "C — Coñecemento"),
    ("P", "P — Poesía"),
    ("T", "T — Teatro"),
]

# Mapping CDU → color for the UI
CDU_COLORS = {
    "0": "#6c757d",   # grey
    "1": "#8e44ad",   # purple
    "2": "#c0392b",   # dark red
    "3": "#e67e22",   # orange
    "5": "#27ae60",   # green
    "6": "#2980b9",   # blue
    "7": "#e74c3c",   # red
    "8": "#f39c12",   # gold
    "9": "#1abc9c",   # teal
    "I": "#e91e63",   # pink
    "X": "#00bcd4",   # cyan
    "C": "#4caf50",   # leaf green
    "P": "#9c27b0",   # violet
    "T": "#ff5722",   # deep orange
}

CDU_LABELS = {c[0]: c[1] for c in CDU_CHOICES if c[0]}

class BookForm(FlaskForm):
    isbn = StringField("Código", validators=[Optional(), Length(max=20)])
    title = StringField("Título", validators=[DataRequired(), Length(max=300)])
    author = StringField("Autoría", validators=[Optional(), Length(max=200)])
    publisher = StringField("Editorial", validators=[Optional(), Length(max=200)])
    year = IntegerField("Año", validators=[Optional(), NumberRange(min=0, max=2100)])
    cdu = SelectField("CDU", choices=CDU_CHOICES, validators=[Optional()])
    category = SelectField(
        "Categoría",
        choices=[
            ("", "-- Seleccionar --"),
            ("Ficción", "Ficción"),
            ("No Ficción", "No Ficción"),
            ("Ciencia", "Ciencia"),
            ("Matemáticas", "Matemáticas"),
            ("Historia", "Historia"),
            ("Lengua", "Lengua"),
            ("Inglés", "Inglés"),
            ("Arte", "Arte"),
            ("Tecnología", "Tecnología"),
            ("Enciclopedia", "Enciclopedia"),
            ("Cómic", "Cómic"),
            ("Poesía", "Poesía"),
            ("Teatro", "Teatro"),
            ("Infantil", "Infantil"),
            ("Juvenil", "Juvenil"),
            ("Otro", "Otro"),
        ],
        validators=[Optional()],
    )
    location = StringField("Ubicación / Estantería", validators=[Optional(), Length(max=100)])
    copies_total = IntegerField("Nº Ejemplares", default=1, validators=[DataRequired(), NumberRange(min=1)])
    language = StringField("Idioma", default="Español", validators=[Optional(), Length(max=50)])
    description = TextAreaField("Descripción", validators=[Optional()])


# ── Student Form ──────────────────────────────────────────────────────
class StudentForm(FlaskForm):
    student_id = StringField("Nº Lector", validators=[DataRequired(), Length(max=50)])
    first_name = StringField("Nombre", validators=[DataRequired(), Length(max=100)])
    last_name = StringField("Apelidos", validators=[Optional(), Length(max=100)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=200)])
    phone = StringField("Teléfono", validators=[Optional(), Length(max=20)])
    grade = SelectField(
        "Curso",
        choices=[
            ("", "-- Seleccionar --"),
            ("3A", "3º A"),
            ("3B", "3º B"),
            ("3C", "3º C"),
            ("4A", "4º A"),
            ("4B", "4º B"),
            ("4C", "4º C"),
            ("5A", "5º A"),
            ("5B", "5º B"),
            ("5C", "5º C"),
            ("6A", "6º A"),
            ("6B", "6º B"),
            ("6C", "6º C"),
            ("1º ESO", "1º ESO"),
            ("2º ESO", "2º ESO"),
            ("3º ESO", "3º ESO"),
            ("4º ESO", "4º ESO"),
            ("Outro", "Outro"),
        ],
        validators=[Optional()],
    )
    group_name = StringField("Grupo / Clase", validators=[Optional(), Length(max=50)])
    max_loans = IntegerField(
        "Límite préstamos (vacío = global)",
        validators=[Optional(), NumberRange(min=0, max=50)],
    )
    is_active = BooleanField("Activo", default=True)
    notes = TextAreaField("Notas", validators=[Optional()])


# ── Loan (Checkout) Form ─────────────────────────────────────────────
class LoanForm(FlaskForm):
    book_id = HiddenField("book_id", validators=[DataRequired()])
    student_id = HiddenField("student_id", validators=[DataRequired()])
    borrowed_date = DateField("Data de recollida", format="%Y-%m-%d", validators=[DataRequired()])
    due_date = DateField("Data límite de devolución", format="%Y-%m-%d", validators=[DataRequired()])
    notes = TextAreaField("Notas", validators=[Optional()])


# ── Settings Form ────────────────────────────────────────────────────
class SettingsForm(FlaskForm):
    max_loans_per_student = IntegerField(
        "Máx. préstamos por alumno",
        validators=[DataRequired(), NumberRange(min=1, max=50)],
    )
    default_loan_days = IntegerField(
        "Días de préstamo por defecto",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
    )
    max_renewals = IntegerField(
        "Máx. renovaciones",
        validators=[DataRequired(), NumberRange(min=0, max=10)],
    )
