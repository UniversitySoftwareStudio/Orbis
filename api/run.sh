#!/usr/bin/env bash
set -euo pipefail
set -a
source .env
set +a
cd ..
EMBED_SERVICE="$(docker compose --profile "${EMBEDDING_MODEL}" config --services | grep '^embedding-' | grep -v '^embedding-lb$' | head -n1)"
[[ -n "${EMBED_SERVICE}" ]] || { echo "No embedding service found for profile ${EMBEDDING_MODEL}"; exit 1; }
docker compose --profile "${EMBEDDING_MODEL}" up -d embedding-lb "${EMBED_SERVICE}"

for _ in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7860/health || true)"
  [[ "$code" == "200" ]] && break
  sleep 2
done

[[ "${code:-}" == "200" ]] || { echo "Embedding service not ready"; exit 1; }

cd api
python3 -m embedding.scripts.verification
exec python3 -m uvicorn main:app --host 0.0.0.0 --port "${API_PORT:-8000}" --reload
