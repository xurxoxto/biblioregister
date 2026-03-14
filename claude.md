# BiblioRegister — Plan de Mejoras

## Resumen del proyecto
Sistema de gestión de biblioteca escolar con Flask + Firestore.
Interfaz web para préstamos, devoluciones, catálogo de libros y gestión de alumnos.

---

## 🐛 Bugs Críticos

### 1. Devoluciones no funcionan correctamente
- **Problema**: Al devolver un libro, se redirige forzosamente a la página de valoración (`/rate`). Esta página usa `student-focus` que oculta TODA la navegación. El usuario se queda "atrapado" sin feedback claro de que la devolución fue exitosa.
- **Solución**: 
  - La devolución siempre redirige de vuelta a donde estaba el usuario con flash de éxito
  - La valoración es opcional (link en el flash, no redirección forzada)
  - Se añade endpoint AJAX `POST /api/loans/<id>/return` para devoluciones sin recarga de página
- **Archivos**: `app.py` (ruta `loan_return`), `templates/loans/list.html`, `templates/base.html`

### 2. Autocompletado limitado
- **Problema**: Requiere 2 caracteres mínimo, no busca por nombre completo (ej. "Juan García" no encuentra si se busca así), y el scroll en el dropdown puede no funcionar bien en móvil.
- **Solución**:
  - Reducir mínimo a 1 carácter
  - Añadir búsqueda por `full_name` (nombre + apellidos combinados)
  - Mejorar CSS del dropdown (scroll táctil, mayor altura)
  - Búsqueda insensible a mayúsculas/minúsculas (ya lo es, pero se refuerza)
- **Archivos**: `models.py` (Student.search), `app.py` (APIs), `static/css/style.css`, JS en templates

---

## ✨ Nuevas Funcionalidades

### 3. Flujo combinado devolución + préstamo
- **Problema**: Si un alumno trae un libro y se lleva otro, hay que hacer dos operaciones separadas en páginas diferentes.
- **Solución**: Página unificada de **Circulación** (`/loans/checkout`):
  1. Buscar alumno (nombre, apellido o número)
  2. Ver sus préstamos activos con botón de devolver (AJAX, sin recarga)
  3. Buscar libro nuevo para prestar
  4. Todo en una sola página, un solo flujo
- **Archivos**: `templates/loans/checkout.html` (reescritura completa), `app.py` (nuevas APIs)

### 4. Préstamo directo tras registrar libro
- **Problema**: Al registrar un libro, no se puede hacer el préstamo directamente.
- **Solución**:
  - Tras crear un libro, redirigir al detalle con opción prominente "Prestar este libro"
  - Botón que lleva a la página de circulación con el libro preseleccionado
- **Archivos**: `app.py` (book_new redirect), `templates/books/detail.html`

---

## 🎨 Rediseño UI — Minimalista y Eficaz

### Principios
1. **Menos es más**: Reducir ruido visual, quitar sombras excesivas
2. **Flujo primario optimizado**: La acción más común (devolver + prestar) en 1 página
3. **Mobile-first**: Todo funciona perfecto en tablet/móvil
4. **Feedback inmediato**: AJAX para operaciones frecuentes, sin recargas innecesarias

### Cambios CSS
- Paleta más suave y limpia
- Cards sin sombras agresivas
- Tipografía más ligera
- Sidebar más compacta
- Autocomplete mejorado con scroll táctil
- Estilos específicos para la página de circulación

### Cambios de Navegación
- "Novo Préstamo" → "Circulación" (cubre préstamos Y devoluciones)
- Dashboard simplificado con accesos directos claros

---

## 📋 Estado de Implementación

| Cambio | Estado | Fecha |
|--------|--------|-------|
| Fix devoluciones | ✅ Completado | 2026-03-14 |
| Fix autocompletado | ✅ Completado | 2026-03-14 |
| Página de circulación | ✅ Completado | 2026-03-14 |
| Préstamo tras registro | ✅ Completado | 2026-03-14 |
| Rediseño UI | ✅ Completado | 2026-03-14 |

---

## 🗂 Archivos Modificados

- `app.py` — Nuevas rutas API, fix return, nuevos endpoints
- `models.py` — Student.search mejorado
- `templates/base.html` — Meta CSRF, navegación actualizada
- `templates/dashboard.html` — Acciones directas actualizadas
- `templates/loans/checkout.html` — Reescritura completa → Circulación
- `templates/loans/list.html` — Mejor UX de devoluciones
- `templates/loans/rate.html` — Flujo limpio sin student-focus forzado
- `templates/books/form.html` — Redirect post-creación
- `templates/books/detail.html` — Botón prestar directo
- `static/css/style.css` — Rediseño minimalista + circulación
- `static/js/app.js` — Autocompletado mejorado, AJAX returns
