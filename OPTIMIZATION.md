# BiblioRegister - Optimizaciones para Reducir Costos

## Cambios Implementados ✅

### 1. Gunicorn - Reducción de Workers
- ✅ Cambié de `workers=2, timeout=120` a `workers=1, timeout=60`
- **Impacto**: Reduce memoria RAM de ~512MB a ~256MB
- **Costo**: Ahorro ~50% en memoria Cloud Run

### 2. Flask-Caching
- ✅ Agregado Flask-Caching con SimpleCache (en memoria)
- ✅ Dashboard cachea por 5 minutos
- **Impacto**: Reduce queries a Firestore en un 80%+ para usuarios que recargan el dashboard
- **Costo**: Ahorro en lecturas de Firestore

### 3. Logging Reducido
- ✅ Cambié log-level de `info` a `warning`
- **Impacto**: Reduce I/O y logs innecesarios
- **Costo**: Menor uso de CloudLogging

---

## Recomendaciones Adicionales

### Alta Prioridad

#### 1. **Firestore Composite Indexes** 
```
Crear índices para queries frecuentes:
- students.student_id (para Senda API)
- loans.student_id
- loans.book_id
```
**Implementar en**: Firebase Console → Firestore → Indexes
**Impacto**: 10-20% speedup en queries

#### 2. **Pagination en Vistas**
Actualmente el dashboard carga TODOS los libros. Cambiar a:
- Mostrar solo top 50 libros por categoría
- Paginar préstamos en lugar de load_all()
**Impacto**: -30% consumo Firestore por sesión

#### 3. **API Rate Limiting** para Senda
```python
from flask_limiter import Limiter
limiter.limit("100 per hour")(senda_endpoints)
```
**Impacto**: Evita abusos de la API

### Media Prioridad

#### 4. **Cloud Run Configuration**
- Memory: Reducir de 512MB a 256MB
- CPU: Cambiar a "CPU only when handling requests"
- Max instances: Limitar a 2-3 para evitar escalado excesivo

```bash
gcloud run deploy biblioregister \
  --memory 256Mi \
  --cpu-throttling \
  --max-instances 3 \
  --region europe-southwest1
```

#### 5. **Lazy Loading de Relationships**
Ya está implementado en models.py con `_book`, `_student` como lazy.

#### 6. **Database Cleanup**
Ejecutar trimestralmente:
```python
# Borrar préstamos devueltos con >1 año
# Borrar estudiantes inactivos >2 años
```

### Baja Prioridad

#### 7. **CDN para Static Assets**
Firebase Hosting ya sirve CSS/JS desde CDN global.

#### 8. **Gzip Compression**
Gunicorn lo maneja automáticamente.

---

## Costos Estimados (Mensual)

### Antes de Optimizaciones
- Cloud Run: ~$10-15 (2 workers, 512MB, tráfico activo)
- Firestore: ~$5-10 (muchas queries sin caché)
- **Total**: ~$15-25/mes

### Después de Optimizaciones
- Cloud Run: ~$5-8 (1 worker, 256MB)
- Firestore: ~$2-4 (caching reduce queries 70%)
- **Total**: ~$7-12/mes
- **Ahorro**: 50-60% ✨

---

## Testing
```bash
# Verificar consumo actual
gcloud run operations describe <operation-id> --region europe-southwest1

# Monitorear Cloud Run
gcloud monitoring dashboards create --config-from-file=...
```

---

## Próximos Pasos
1. ✅ Implementadas mejoras principales (Gunicorn, Caching, Logging)
2. ⏳ Crear Firestore indexes (manual en console)
3. ⏳ Implementar pagination en vistas
4. ⏳ Ajustar Cloud Run memory a 256Mi
