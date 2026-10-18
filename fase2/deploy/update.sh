#!/usr/bin/env bash
set -euo pipefail
exec 9>/run/medroute-deploy.lock
flock -n 9 || exit 0
cd /opt/medroute/repo
git fetch --quiet origin main
revision=$(git rev-parse origin/main)
previous=$(cat /opt/medroute/deployed-revision 2>/dev/null || true)
[ "$revision" != "$previous" ] || exit 0
stage=$(mktemp -d /opt/medroute/release.XXXXXX)
trap 'rm -rf "$stage"' EXIT
git archive "$revision" fase2 | tar -x -C "$stage"
echo "Construindo MedRoute $revision"
docker build -t medroute:local "$stage/fase2"
install -d -o 10002 -g 10002 /opt/medroute/data /opt/medroute/reports /opt/medroute/cache
cp -an "$stage/fase2/data/." /opt/medroute/data/
cp -an "$stage/fase2/reports/." /opt/medroute/reports/
chown -R 10002:10002 /opt/medroute/data /opt/medroute/reports /opt/medroute/cache
if docker inspect medroute >/dev/null 2>&1; then
 docker stop --timeout 30 medroute
 docker rm medroute
fi
docker run -d --name medroute --restart unless-stopped --memory=1536m --cpus=1 \
 --log-opt max-size=10m --log-opt max-file=3 \
 -p 127.0.0.1:8501:8501 \
 -v /opt/medroute/data:/app/data \
 -v /opt/medroute/reports:/app/reports \
 -v /opt/medroute/cache:/app/.cache medroute:local
for attempt in $(seq 1 40); do
 if curl --fail --silent http://127.0.0.1:8501/fase2/_stcore/health >/dev/null; then
  printf '%s\n' "$revision" > /opt/medroute/deployed-revision
  echo "MedRoute publicado: $revision"
  exit 0
 fi
 sleep 2
done
docker logs --tail 40 medroute
exit 1
