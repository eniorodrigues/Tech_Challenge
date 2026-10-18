#!/usr/bin/env bash
set -euo pipefail
install -d /opt/medroute
if [ ! -d /opt/medroute/repo/.git ]; then
    git clone --branch main --single-branch https://github.com/eniorodrigues/Tech_Challenge.git /opt/medroute/repo
fi
git -C /opt/medroute/repo fetch origin main
git -C /opt/medroute/repo checkout --detach origin/main
cp /opt/medroute/repo/fase2/deploy/update.sh /opt/medroute/update.sh
cp /opt/medroute/repo/fase2/deploy/medroute-update.service /etc/systemd/system/
cp /opt/medroute/repo/fase2/deploy/medroute-update.timer /etc/systemd/system/
bash -n /opt/medroute/update.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/etc/nginx/sites-available/default')
s = p.read_text()
if 'location /fase2/' not in s:
    p.with_suffix('.before-medroute').write_text(s)
    location = Path('/opt/medroute/repo/fase2/deploy/nginx-location.conf').read_text()
    p.write_text(s.replace('    location / {', location + '\n    location / {'))
PY
nginx -t
systemctl reload nginx
systemctl daemon-reload
systemctl enable --now medroute-update.timer
systemctl start --no-block medroute-update.service
