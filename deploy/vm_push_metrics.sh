#!/usr/bin/env bash
# NEKKO — publica las métricas del colector al repo; el sitio se rebuildea solo
# (GitHub Actions). Corre por cron en la VM. Es INDEPENDIENTE del colector: si
# algo falla, loguea y sale — NUNCA toca ni reinicia el colector.
#
# Requiere (paso de Jordi, una vez): deploy key con write access en el repo y su
# clave privada en ~/.ssh/nekko_deploy. Ver docs/STATUS.md para los comandos.
set -uo pipefail

REPO=/home/ubuntu/9-NEKKO       # código + venv + DB viva del colector
SITE=/home/ubuntu/nekko-site    # clone dedicado SOLO para publicar datos
DB="$REPO/nekko.sqlite"
TMP=/tmp/nekko_export.db
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/nekko_deploy -o IdentitiesOnly=yes"

log() { echo "$(date -u +%FT%TZ) $*"; }

# 1) copia consistente de la DB (no leer la DB caliente en pleno write)
sqlite3 "$DB" ".backup $TMP" || { log "backup fallo"; exit 1; }

# 2) generar los JSON dentro del clone (usando el código + venv del colector)
cd "$REPO" || exit 1
.venv/bin/python -m analysis.export_metrics --db "$TMP" --out "$SITE/docs/data" \
  || { log "export fallo"; rm -f "$TMP"; exit 1; }
rm -f "$TMP"

# 3) traer cambios remotos (solo la VM escribe docs/data → rebase limpio)
cd "$SITE" || exit 1
git pull --rebase -q origin main || { log "pull fallo"; exit 1; }

# 4) stagear SOLO los JSON de datos
git add docs/data/collector_status.json docs/data/paper_kpis.json

# 5) FAIL-CLOSED: si se coló algo prohibido en el stage, abortar sin commitear
#    (el repo es PÚBLICO: nunca la DB, WAL/SHM ni snapshots crudos)
STAGED=$(git diff --cached --name-only)
if echo "$STAGED" | grep -qiE '\.(sqlite|sqlite3|db|sqlite-wal|sqlite-shm|shm|wal)$|snapshot'; then
  log "ABORT: archivo prohibido en el stage -> $STAGED"
  git reset -q
  exit 2
fi

# 6) saltar commits vacíos
if git diff --cached --quiet; then
  log "sin cambios, nada que pushear"
  exit 0
fi

# 7) commit + push (si el push falla, se loguea; el colector no se entera)
git commit -q -m "data: metricas del colector $(date -u +%FT%TZ)" || { log "commit fallo"; exit 1; }
if git push -q origin main; then
  log "push OK"
else
  log "push fallo (deploy key sin write access todavia?)"
  exit 1
fi
