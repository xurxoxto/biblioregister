#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  BiblioRegister — Deploy to Firebase Hosting + Cloud Run
# ═══════════════════════════════════════════════════════════════════
#
#  Prerequisitos (instalar una sola vez):
#    brew install --cask google-cloud-sdk
#    brew install firebase-cli        # o:  npm install -g firebase-tools
#    gcloud auth login
#    gcloud config set project biblioutes
#    firebase login
#
#  Uso:
#    chmod +x deploy.sh
#    ./deploy.sh
#
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_ID="biblioutes"
REGION="europe-southwest1"          # Madrid — lo más cerca de Galicia
SERVICE_NAME="biblioregister"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo ""
echo "📚 BiblioRegister — Desplegando en Firebase + Cloud Run"
echo "══════════════════════════════════════════════════════════"

# ── 1. Asegurar proyecto activo ──────────────────────────────────
echo ""
echo "🔧 Configurando proyecto GCP: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

# ── 2. Activar APIs necesarias (solo la primera vez) ─────────────
echo ""
echo "🔌 Activando APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    firebasehosting.googleapis.com \
    2>/dev/null || true

# ── 3. Construir imagen Docker con Cloud Build ──────────────────
echo ""
echo "🐳 Construyendo imagen Docker..."
gcloud builds submit --tag "${IMAGE}" .

# ── 4. Desplegar en Cloud Run ────────────────────────────────────
echo ""
echo "🚀 Desplegando en Cloud Run (${REGION})..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --memory 256Mi \
    --min-instances 0 \
    --max-instances 2 \
    --set-env-vars "SECRET_KEY=$(openssl rand -hex 32)" \
    --set-env-vars "MAX_LOANS_PER_STUDENT=3" \
    --set-env-vars "DEFAULT_LOAN_DAYS=14" \
    --set-env-vars "MAX_RENEWALS=2"

# ── 5. Desplegar Firebase Hosting (proxy → Cloud Run) ───────────
echo ""
echo "🌐 Desplegando Firebase Hosting..."
firebase deploy --only hosting --project "${PROJECT_ID}"

# ── 6. Mostrar URLs ─────────────────────────────────────────────
CLOUD_RUN_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region "${REGION}" --format="value(status.url)" 2>/dev/null || echo "")
echo ""
echo "══════════════════════════════════════════════════════════"
echo "✅ ¡Desplegue completado!"
echo ""
echo "   🔗 Firebase:   https://${PROJECT_ID}.web.app"
echo "   🔗 Cloud Run:  ${CLOUD_RUN_URL}"
echo ""
echo "══════════════════════════════════════════════════════════"
