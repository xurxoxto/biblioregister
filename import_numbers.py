"""
Importar datos do ficheiro .numbers da biblioteca.
Uso: python import_numbers.py [ruta_al_ficheiro.numbers]

Por defecto busca: proxecto libros xls.numbers na carpeta Downloads
"""

import sys
from datetime import datetime
from numbers_parser import Document
from app import create_app
from models import Book, Student, Loan, drop_data, get_db


DEFAULT_PATH = "/Users/jorgegarcia/Library/Mobile Documents/com~apple~CloudDocs/Downloads/proxecto libros xls.numbers"


def import_data(filepath=None):
    filepath = filepath or DEFAULT_PATH
    print(f"📂 Abrindo ficheiro: {filepath}")
    doc = Document(filepath)

    app = create_app()

    with app.app_context():
        # ── Borrar datos existentes ──────────────────────────────
        print("\n🗑️  Borrando datos anteriores...")
        drop_data()

        # ── 1. Importar ALUMNADO ─────────────────────────────────
        print("\n🎓 Importando alumnado...")
        sheet_alumnado = doc.sheets["Alumnado"]
        table_alumnado = sheet_alumnado.tables[0]

        students_map = {}  # nº lector → Student object
        student_count = 0

        for row_num in range(1, table_alumnado.num_rows):
            num_lector = table_alumnado.cell(row_num, 0).value
            nombre = table_alumnado.cell(row_num, 1).value
            curso = table_alumnado.cell(row_num, 2).value

            if num_lector is None or nombre is None:
                continue

            num_lector_str = str(int(float(num_lector)))
            nombre_str = str(nombre).strip()
            curso_str = str(curso).strip() if curso else ""

            # Separar nome e apelidos se é posible
            parts = nombre_str.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            student = Student(
                student_id=num_lector_str,
                first_name=first_name,
                last_name=last_name,
                grade=curso_str,
                is_active=True,
            )
            student.save()
            students_map[num_lector_str] = student
            student_count += 1

        print(f"   ✅ {student_count} alumnos importados")

        # ── 2. Importar LIBROS ───────────────────────────────────
        print("\n📚 Importando libros...")
        sheet_libros = doc.sheets["Libros"]
        table_libros = sheet_libros.tables[0]

        books_by_code = {}   # código → Book object
        books_by_title = {}  # título → Book object (para libros sen código)
        book_count = 0

        for row_num in range(1, table_libros.num_rows):
            codigo = table_libros.cell(row_num, 0).value
            titulo = table_libros.cell(row_num, 1).value
            autoria = table_libros.cell(row_num, 2).value

            if titulo is None:
                continue

            titulo_str = str(titulo).strip()
            autoria_str = str(autoria).strip() if autoria else None
            codigo_str = str(int(float(codigo))) if codigo is not None else None

            book = Book(
                isbn=codigo_str,
                title=titulo_str,
                author=autoria_str or "",
                copies_total=1,
                language="Galego",
            )
            book.save()

            if codigo_str:
                books_by_code[codigo_str] = book
            books_by_title[titulo_str.lower()] = book
            book_count += 1

        print(f"   ✅ {book_count} libros importados")

        # ── 3. Importar PRÉSTAMOS (Rexistro) ─────────────────────
        print("\n📋 Importando préstamos...")
        sheet_rexistro = doc.sheets["Rexistro"]
        table_rexistro = sheet_rexistro.tables[0]

        loan_count = 0
        skipped = 0

        for row_num in range(1, table_rexistro.num_rows):
            num_lector = table_rexistro.cell(row_num, 0).value
            # nombre = table_rexistro.cell(row_num, 1).value  # not needed
            codigo_libro = table_rexistro.cell(row_num, 3).value
            titulo_libro = table_rexistro.cell(row_num, 4).value
            fecha_prestamo = table_rexistro.cell(row_num, 5).value
            fecha_devolucion = table_rexistro.cell(row_num, 6).value
            estado = table_rexistro.cell(row_num, 7).value

            if num_lector is None or titulo_libro is None:
                continue

            num_lector_str = str(int(float(num_lector)))
            titulo_str = str(titulo_libro).strip()

            # Buscar alumno
            student = students_map.get(num_lector_str)
            if not student:
                print(f"   ⚠️  Alumno N.º {num_lector_str} non atopado (fila {row_num}), saltando.")
                skipped += 1
                continue

            # Buscar libro por código ou título
            book = None
            if codigo_libro is not None:
                codigo_str = str(int(float(codigo_libro)))
                book = books_by_code.get(codigo_str)

            if book is None:
                book = books_by_title.get(titulo_str.lower())

            if book is None:
                # Crear o libro se non existe
                codigo_str = str(int(float(codigo_libro))) if codigo_libro else None
                book = Book(
                    isbn=codigo_str,
                    title=titulo_str,
                    author="",
                    copies_total=1,
                    language="Galego",
                )
                book.save()
                if codigo_str:
                    books_by_code[codigo_str] = book
                books_by_title[titulo_str.lower()] = book
                print(f"   📖 Libro creado automaticamente: '{titulo_str}' (código: {codigo_str})")

            # Parsear datas
            borrowed_at = _parse_date(fecha_prestamo)
            if not borrowed_at:
                print(f"   ⚠️  Data de préstamo inválida fila {row_num}, saltando.")
                skipped += 1
                continue

            returned_at = _parse_date(fecha_devolucion)
            due_date = borrowed_at.date()
            from datetime import timedelta
            due_date = borrowed_at.date() + timedelta(days=14)

            loan = Loan(
                book_id=book.id,
                student_id=student.id,
                borrowed_at=borrowed_at,
                due_date=due_date,
                returned_at=returned_at,
            )
            loan.save()
            loan_count += 1

        # ── Resumo ───────────────────────────────────────────────
        all_loans = Loan.load_all()
        active = sum(1 for l in all_loans if l.returned_at is None)
        returned = sum(1 for l in all_loans if l.returned_at is not None)

        print(f"\n{'='*50}")
        print(f"✅ IMPORTACIÓN COMPLETADA")
        print(f"{'='*50}")
        print(f"   🎓 Alumnos:    {student_count}")
        print(f"   📚 Libros:     {Book.count()}")
        print(f"   📋 Préstamos:  {loan_count} ({active} activos, {returned} devueltos)")
        if skipped:
            print(f"   ⚠️  Saltados:  {skipped}")
        print(f"{'='*50}")


def _parse_date(value):
    """Parse a date value from Numbers (can be datetime or string)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    import_data(path)
