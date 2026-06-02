#!/usr/bin/env bash
# =============================================================================
# setup-genomic-stack.sh
# Inicialización del stack de genómica — ejecutar UNA VEZ antes del primer
# docker compose up
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR"
ENV_FILE="$COMPOSE_DIR/.env"

# Colores
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; exit 1; }
info() { echo -e "   $*"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║    Setup — Laboratorio de Neuropediatría · Genomic Stack     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Cargar .env ─────────────────────────────────────────────────────────
source "$ENV_FILE" || err ".env no encontrado en $ENV_FILE"

NAS_BASE="${volumes_basedir:-/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/active/docker-volumes}"

# ── 2. Verificar NAS montado ────────────────────────────────────────────────
echo "📂 Verificando NAS..."
if ! mountpoint -q "$(dirname "$NAS_BASE")" 2>/dev/null; then
  if [[ -d "$NAS_BASE" ]]; then
    warn "Mountpoint no detectado, pero el directorio existe — continuando"
  else
    err "NAS no montado en $NAS_BASE. Monta el NAS primero."
  fi
fi
ok "NAS disponible"

# ── 3. Crear directorios en NAS para servicios nuevos ──────────────────────
echo ""
echo "📁 Creando directorios en NAS..."

dirs=(
  "$NAS_BASE/opencravat/data"
  "$NAS_BASE/variant-tracker/clinvar"
  "$NAS_BASE/variant-tracker/logs"
)

for d in "${dirs[@]}"; do
  if mkdir -p "$d" 2>/dev/null; then
    ok "$d"
  else
    warn "No se pudo crear $d (¿permisos NAS?)"
  fi
done

# ── 4. Leer contraseña de postgres desde secrets ────────────────────────────
echo ""
echo "🔑 Leyendo credenciales..."

SECRETS_DIR="${secrets_basedir:-$COMPOSE_DIR/secrets}"
PG_PASS_FILE="$SECRETS_DIR/db-password"

if [[ -f "$PG_PASS_FILE" ]]; then
  POSTGRES_PASSWORD_VAL=$(cat "$PG_PASS_FILE")
  ok "Contraseña de postgres leída desde $PG_PASS_FILE"
else
  err "No se encontró $PG_PASS_FILE. Verifica que el stack REEV esté configurado."
fi

# ── 5. Crear base de datos vartracker ──────────────────────────────────────
echo ""
echo "🗄️  Configurando PostgreSQL..."

# Intentar conectar al contenedor postgres en ejecución
if docker ps --format '{{.Names}}' | grep -q "^reev-postgres$"; then
  DB_EXISTS=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD_VAL" reev-postgres \
    psql -U "${POSTGRES_USER:-reev}" -tAc \
    "SELECT 1 FROM pg_database WHERE datname='vartracker'" 2>/dev/null || echo "")

  if [[ "$DB_EXISTS" == "1" ]]; then
    ok "Base de datos 'vartracker' ya existe"
  else
    docker exec -e PGPASSWORD="$POSTGRES_PASSWORD_VAL" reev-postgres \
      psql -U "${POSTGRES_USER:-reev}" -c \
      "CREATE DATABASE vartracker OWNER ${POSTGRES_USER:-reev};" 2>/dev/null \
      && ok "Base de datos 'vartracker' creada" \
      || warn "No se pudo crear vartracker (¿ya existe?)"
  fi
else
  warn "Contenedor reev-postgres no está corriendo — la DB se creará en el primer arranque"
  info "Ejecuta manualmente: docker exec reev-postgres psql -U reev -c 'CREATE DATABASE vartracker OWNER reev;'"
fi

# ── 6. Verificar/agregar variables al .env ─────────────────────────────────
echo ""
echo "⚙️  Verificando variables de entorno..."

add_env_var() {
  local key="$1" val="$2" comment="${3:-}"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    ok "$key ya está en .env"
  else
    echo "" >> "$ENV_FILE"
    [[ -n "$comment" ]] && echo "# $comment" >> "$ENV_FILE"
    echo "${key}=${val}" >> "$ENV_FILE"
    ok "$key añadido a .env"
  fi
}

add_env_var "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD_VAL" "Para variant-tracker (leída de secrets)"
add_env_var "LAB_NAME" "Laboratorio de Neuropediatría" "Nombre del laboratorio para alertas"
add_env_var "SMTP_HOST" "" "Servidor SMTP para alertas por email (ej: smtp.gmail.com)"
add_env_var "SMTP_PORT" "587" ""
add_env_var "SMTP_USER" "" "Usuario SMTP"
add_env_var "SMTP_PASSWORD" "" "Contraseña SMTP"
add_env_var "SMTP_FROM" "noreply@neuropedialab.org" ""
add_env_var "SMTP_TLS" "true" ""
add_env_var "ALERT_WEBHOOK_URL" "" "Webhook para alertas (ej: Slack/Teams/n8n)"
add_env_var "ALERT_EMAIL_TO" "" "Email destino para alertas (separar con comas)"

# ── 7. Resumen de puertos ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Servicios del Stack                         ║"
echo "╟──────────────────────────────────────────────────────────────╢"
echo "║  REEV                 https://reev.neuropedialab.org         ║"
echo "║  JBrowse2             http://localhost:3006                  ║"
echo "║  OpenCRAVAT           http://localhost:8402                  ║"
echo "║  Variant Tracker API  http://localhost:8403/docs             ║"
echo "║  Protein Viewer       http://localhost:8404                  ║"
echo "║  Exome Advisor        http://localhost:8401                  ║"
echo "║  REEV Monitor         http://localhost:8300                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── 8. Build de imágenes nuevas ─────────────────────────────────────────────
echo ""
read -p "¿Construir las imágenes Docker ahora? [s/N] " BUILD_NOW
if [[ "${BUILD_NOW,,}" == "s" ]]; then
  echo ""
  echo "🔨 Construyendo imágenes..."
  cd "$COMPOSE_DIR"
  docker compose build --no-cache variant-tracker variant-tracker-worker variant-tracker-beat protein-viewer \
    && ok "Imágenes construidas correctamente" \
    || err "Error en el build — revisa los logs"

  echo ""
  read -p "¿Arrancar los nuevos servicios ahora? [s/N] " START_NOW
  if [[ "${START_NOW,,}" == "s" ]]; then
    docker compose up -d opencravat variant-tracker variant-tracker-worker variant-tracker-beat protein-viewer \
      && ok "Servicios arrancados" \
      || err "Error arrancando servicios"

    echo ""
    echo "⏳ Esperando inicialización (15s)..."
    sleep 15

    echo "🔍 Estado de los nuevos servicios:"
    docker ps --filter "name=genomic-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  fi
fi

echo ""
ok "Setup completado"
echo ""
echo "📌 Recuerda configurar en .env:"
echo "   SMTP_HOST, SMTP_USER, SMTP_PASSWORD — para alertas por email"
echo "   ALERT_WEBHOOK_URL — para alertas por webhook (Slack/Teams/n8n)"
echo "   ALERT_EMAIL_TO — email(s) de destino de alertas"
echo ""
