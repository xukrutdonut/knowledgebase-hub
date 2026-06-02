# Exome Slicer - Docker Deployment

**NOTA:** Aplicación parcialmente funcional. Requiere compilación de frontend React.

Aplicación para evaluar la calidad de secuenciación al desarrollar un Exome Slice (panel virtual NGS).

## 🔗 Información Original

- **Repositorio:** https://github.com/genomics-geek/exome_slicer
- **Paper:** https://www.ncbi.nlm.nih.gov/pubmed/29936260
- **Demo original:** http://exomeslicer.chop.edu/

## ⚠️ Estado Actual

**Backend:** ✅ Funcionando (Django + PostgreSQL + Redis)  
**Frontend:** ❌ Requiere compilación (React/Node.js)  
**Error:** Template `index.html` no encontrado (frontend no compilado)

### Problema

La aplicación tiene un frontend en React que necesita ser compilado antes del deployment. Los archivos están en `/tmp/exome_slicer/frontend/` pero no se compilaron durante el build.

### Solución Pendiente

1. Instalar Node.js en el Dockerfile
2. Compilar frontend React durante el build
3. Copiar archivos compilados a templates/static

## 🚀 Despliegue Actual

### 1. Build y Start

```bash
cd /home/arkantu/workspace/medical/exome-slicer
docker compose up -d --build
```

### 2. Servicios Activos

- ✅ **PostgreSQL 12** - Base de datos funcionando
- ✅ **Redis 6** - Cache funcionando  
- ⚠️  **Exomeslicer** - Backend OK, frontend falta

### 3. Acceso

- **URL:** http://localhost:8300 (Error 500 - template faltante)
- **Admin:** http://localhost:8300/admin/ (debería funcionar)
- **GraphQL API:** http://localhost:8300/graphql/ (backend endpoint)
- **REST API:** http://localhost:8300/api/

**Credenciales Admin:**
- Usuario: `admin`
- Contraseña: `akelarre`

### 4. Logs

```bash
docker compose logs -f exomeslicer
```

### 5. Stop

```bash
docker compose down
```

## 📦 Servicios

- **exomeslicer:** Aplicación Django (Puerto 8300)
- **postgres:** PostgreSQL 12
- **redis:** Redis 6 (cache)

## 🔧 Para Completar la Instalación

Necesitas modificar el Dockerfile para incluir Node.js y compilar el frontend:

```dockerfile
# Añadir después de instalar dependencias del sistema
RUN curl -fsSL https://deb.nodesource.com/setup_14.x | bash - && \
    apt-get install -y nodejs

# Compilar frontend (después de clonar el repo)
WORKDIR /app/frontend
RUN npm install && npm run build

# Copiar archivos compilados
RUN cp -r /app/frontend/build/* /app/exome_slicer/templates/
```

## 📝 Alternativa

Usar la API directamente:
- GraphQL: http://localhost:8300/graphql/
- REST: http://localhost:8300/api/

## ⚠️ Notas

- Aplicación de 2019, puede requerir actualizaciones
- Django 2.1.13 y Python 3.7 (versiones antiguas con vulnerabilidades conocidas)
- Frontend React requiere compilación adicional
- Para producción: actualizar dependencias, cambiar SECRET_KEY, habilitar SSL

