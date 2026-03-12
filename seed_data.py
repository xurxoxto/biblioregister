"""
Seed the database with sample data for testing.
Run: python seed_data.py
"""

from datetime import datetime, date, timedelta
import random
from app import create_app
from models import db, Book, Student, Loan

app = create_app()

BOOKS = [
    ("978-84-376-0494-7", "Don Quijote de la Mancha", "Miguel de Cervantes", "Cátedra", 1605, "Ficción", "Est. A-1"),
    ("978-84-339-7186-4", "Cien años de soledad", "Gabriel García Márquez", "Debolsillo", 1967, "Ficción", "Est. A-1"),
    ("978-84-204-8418-4", "La sombra del viento", "Carlos Ruiz Zafón", "Planeta", 2001, "Ficción", "Est. A-2"),
    ("978-84-226-5609-2", "El principito", "Antoine de Saint-Exupéry", "Salamandra", 1943, "Infantil", "Est. B-1"),
    ("978-84-339-0780-0", "1984", "George Orwell", "Debolsillo", 1949, "Ficción", "Est. A-2"),
    ("978-84-663-3015-6", "Harry Potter y la piedra filosofal", "J.K. Rowling", "Salamandra", 1997, "Juvenil", "Est. B-2"),
    ("978-84-322-1347-3", "El nombre de la rosa", "Umberto Eco", "Debolsillo", 1980, "Ficción", "Est. A-3"),
    ("978-84-233-4579-1", "Sapiens: De animales a dioses", "Yuval Noah Harari", "Debate", 2011, "Historia", "Est. C-1"),
    ("978-84-204-0488-4", "Breve historia del tiempo", "Stephen Hawking", "Crítica", 1988, "Ciencia", "Est. C-2"),
    ("978-84-376-1527-1", "La Celestina", "Fernando de Rojas", "Cátedra", 1499, "Teatro", "Est. A-1"),
    ("978-84-670-4306-2", "El Hobbit", "J.R.R. Tolkien", "Minotauro", 1937, "Juvenil", "Est. B-2"),
    ("978-84-204-7152-8", "Matemáticas para la vida", "Fernando Corbalán", "SM", 2007, "Matemáticas", "Est. C-3"),
    ("978-84-414-1399-1", "Física para futuros presidentes", "Richard A. Muller", "Antoni Bosch", 2009, "Ciencia", "Est. C-2"),
    ("978-84-376-2040-4", "Lazarillo de Tormes", "Anónimo", "Cátedra", 1554, "Ficción", "Est. A-1"),
    ("978-84-233-5036-8", "El arte de la guerra", "Sun Tzu", "Debolsillo", -500, "Historia", "Est. C-1"),
    ("978-84-01-02164-7", "Persépolis", "Marjane Satrapi", "Norma Editorial", 2000, "Cómic", "Est. D-1"),
    ("978-84-322-9073-3", "Poesía completa", "Federico García Lorca", "Debolsillo", 1940, "Poesía", "Est. A-4"),
    ("978-84-253-5274-8", "Introducción a la tecnología", "VV.AA.", "Anaya", 2020, "Tecnología", "Est. C-4"),
    ("978-84-670-5182-1", "English Grammar in Use", "Raymond Murphy", "Cambridge UP", 2012, "Inglés", "Est. D-2"),
    ("978-84-414-3684-6", "Historia del arte", "E.H. Gombrich", "Phaidon", 1950, "Arte", "Est. D-3"),
]

STUDENTS = [
    ("NIA001", "María", "García López", "1º ESO", "A"),
    ("NIA002", "Carlos", "Martínez Ruiz", "1º ESO", "A"),
    ("NIA003", "Laura", "Fernández Sánchez", "1º ESO", "B"),
    ("NIA004", "Diego", "López Hernández", "2º ESO", "A"),
    ("NIA005", "Ana", "Rodríguez Pérez", "2º ESO", "A"),
    ("NIA006", "Pablo", "González Martín", "2º ESO", "B"),
    ("NIA007", "Sofía", "Díaz García", "3º ESO", "A"),
    ("NIA008", "Javier", "Moreno Jiménez", "3º ESO", "A"),
    ("NIA009", "Elena", "Álvarez Torres", "3º ESO", "B"),
    ("NIA010", "Hugo", "Romero Navarro", "4º ESO", "A"),
    ("NIA011", "Lucía", "Sanz Molina", "4º ESO", "A"),
    ("NIA012", "Marcos", "Ruiz Serrano", "4º ESO", "B"),
    ("NIA013", "Carmen", "Herrero Blanco", "1º Bachillerato", "A"),
    ("NIA014", "Alejandro", "Prieto Vega", "1º Bachillerato", "B"),
    ("NIA015", "Irene", "Castro Ramos", "2º Bachillerato", "A"),
    ("NIA016", "Daniel", "Iglesias Flores", "1º CFGM", "A"),
    ("NIA017", "Paula", "Ortiz Medina", "1º CFGM", "A"),
    ("NIA018", "Adrián", "Delgado Santos", "2º CFGM", "A"),
    ("NIA019", "Marta", "Guerrero Luna", "1º CFGS", "A"),
    ("NIA020", "Sergio", "Núñez Campos", "2º CFGS", "A"),
]


def seed():
    with app.app_context():
        # Clear
        Loan.query.delete()
        Student.query.delete()
        Book.query.delete()
        db.session.commit()

        # Books
        books = []
        for isbn, title, author, publisher, year, category, location in BOOKS:
            copies = random.choice([1, 1, 1, 2, 2, 3])
            b = Book(
                isbn=isbn, title=title, author=author,
                publisher=publisher, year=year if year > 0 else None,
                category=category, location=location,
                copies_total=copies, language="Español",
            )
            db.session.add(b)
            books.append(b)

        # Students
        students = []
        for nia, first, last, grade, group in STUDENTS:
            s = Student(
                student_id=nia, first_name=first, last_name=last,
                grade=grade, group_name=group, is_active=True,
                email=f"{first.lower()}.{last.split()[0].lower()}@centro.edu",
            )
            db.session.add(s)
            students.append(s)

        db.session.commit()

        # Create some loans
        today = date.today()
        for _ in range(15):
            book = random.choice(books)
            student = random.choice(students)
            # Check if already has this book
            existing = Loan.query.filter_by(book_id=book.id, student_id=student.id).filter(
                Loan.returned_at.is_(None)
            ).first()
            if existing:
                continue

            days_ago = random.randint(1, 30)
            borrowed = datetime.now() - timedelta(days=days_ago)
            due = (today - timedelta(days=days_ago) + timedelta(days=30))

            loan = Loan(
                book_id=book.id,
                student_id=student.id,
                borrowed_at=borrowed,
                due_date=due,
            )
            # Some returned
            if random.random() < 0.3:
                loan.returned_at = borrowed + timedelta(days=random.randint(5, 20))

            db.session.add(loan)

        db.session.commit()
        print("✅ Base de datos poblada con datos de ejemplo.")
        print(f"   📚 {len(books)} libros")
        print(f"   🎓 {len(students)} alumnos")
        print(f"   📋 {Loan.query.count()} préstamos")


if __name__ == "__main__":
    seed()
