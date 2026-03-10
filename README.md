# 📚 BiblioRegister

**Sistema de Gestión de Biblioteca Escolar** — inspirado en Koha, diseñado para centros educativos.

## ✨ Características

- **Gestión de Libros**: Catálogo completo con ISBN, categorías, ubicación, múltiples ejemplares
- **Gestión de Alumnado**: Registro por curso y grupo, filtrado avanzado
- **Préstamos**: Checkout/devolución con búsqueda en tiempo real (AJAX)
- **Límite de préstamos**: Configurable globalmente y por alumno individual
- **Renovaciones**: Con límite máximo configurable
- **Control de retrasos**: Panel de préstamos vencidos con alertas
- **Informes**: Libros más prestados, lectores más activos, estadísticas mensuales
- **Configuración**: Panel de ajustes persistente

## 🚀 Instalación

### Requisitos
- Python 3.9+

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/biblioregister.git
cd biblioregister

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. (Opcional) Poblar con datos de ejemplo
python seed_data.py

# 5. Ejecutar la aplicación
python app.py
```

La aplicación estará disponible en **http://localhost:5000**

## 📁 Estructura

```
biblioregister/
├── app.py               # Aplicación Flask principal (rutas)
├── config.py            # Configuración
├── models.py            # Modelos de base de datos (Book, Student, Loan)
├── forms.py             # Formularios WTForms
├── seed_data.py         # Datos de ejemplo
├── requirements.txt     # Dependencias Python
├── static/
│   ├── css/style.css    # Estilos personalizados
│   └── js/app.js        # JavaScript frontend
└── templates/
    ├── base.html        # Template base (navbar, layout)
    ├── dashboard.html   # Panel principal
    ├── settings.html    # Configuración
    ├── reports.html     # Informes y estadísticas
    ├── books/
    │   ├── list.html    # Catálogo de libros
    │   ├── form.html    # Formulario añadir/editar libro
    │   └── detail.html  # Detalle de libro
    ├── students/
    │   ├── list.html    # Lista de alumnado
    │   ├── form.html    # Formulario añadir/editar alumno
    │   └── detail.html  # Detalle de alumno con historial
    └── loans/
        ├── list.html    # Lista de préstamos (filtrable)
        └── checkout.html # Nuevo préstamo (búsqueda AJAX)
```

## ⚙️ Configuración

Variables de entorno (opcionales):

| Variable | Defecto | Descripción |
|----------|---------|-------------|
| `SECRET_KEY` | auto | Clave secreta Flask |
| `DATABASE_URL` | `sqlite:///biblioregister.db` | URL de la base de datos |
| `MAX_LOANS_PER_STUDENT` | `3` | Máximo préstamos por alumno |
| `DEFAULT_LOAN_DAYS` | `14` | Días de préstamo por defecto |
| `MAX_RENEWALS` | `2` | Máximo renovaciones por préstamo |

Estos valores también se pueden modificar desde **Config** en la app.

## 📋 Uso

1. **Añadir libros** al catálogo (Libros → Añadir Libro)
2. **Registrar alumnos** (Alumnado → Añadir Alumno)
3. **Crear préstamos** buscando libro y alumno (Préstamos → Nuevo Préstamo)
4. **Devolver libros** desde la lista de préstamos o el detalle del alumno
5. **Consultar informes** para ver estadísticas de uso

## 📄 Licencia

MIT
