#!/usr/bin/env bash
# Provisionamento de uma VPS Ubuntu 24.04 limpa para o MedRoute (como root):
#
#   apt-get install -y git
#   git clone --branch main https://github.com/eniorodrigues/Tech_Challenge.git /opt/medroute/repo
#   bash /opt/medroute/repo/fase2/deploy/provision.sh <IP público da VPS>
#
# Reproduz a VPS de produção na Hostinger: Docker + nginx, certificado
# Let's Encrypt para o IP (perfil shortlived), renovação por timer (6 h) e o
# deploy contínuo do painel (setup.sh: timer de 60 s → update.sh).
# Idempotente: numa VPS já provisionada não troca certificado nem site do nginx.
# A chave da OpenRouter não passa por aqui (ver HOSTINGER.md, runtime.env).
set -euo pipefail

IP="${1:-${IP:-}}"
[ -n "$IP" ] || { echo "uso: bash provision.sh <IP público da VPS>" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "execute como root" >&2; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
SITE=/etc/nginx/sites-available/default
CERT=/etc/letsencrypt/live/hostinger-ip/fullchain.pem

echo "== 1/5 pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io nginx git python3 curl ca-certificates
systemctl enable --now docker nginx
install -d /opt/medroute /var/www/letsencrypt /etc/letsencrypt /var/lib/letsencrypt /var/log/letsencrypt

echo "== 2/5 certificado Let's Encrypt para $IP"
if [ ! -s "$CERT" ]; then
    # nginx só em HTTP, para responder ao desafio ACME (o site final já exige o certificado)
    if [ -f "$SITE" ]; then cp "$SITE" "$SITE.before-provision"; fi
    cat > "$SITE" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name $IP;
    location ^~ /.well-known/acme-challenge/ { root /var/www/letsencrypt; }
    location / { return 404; }
}
EOF
    nginx -t
    systemctl reload nginx
    docker run --rm \
        -v /etc/letsencrypt:/etc/letsencrypt -v /var/lib/letsencrypt:/var/lib/letsencrypt \
        -v /var/log/letsencrypt:/var/log/letsencrypt -v /var/www/letsencrypt:/var/www/letsencrypt \
        certbot/certbot:latest certonly --non-interactive --agree-tos --register-unsafely-without-email \
        --preferred-profile shortlived --webroot --webroot-path /var/www/letsencrypt \
        --ip-address "$IP" --cert-name hostinger-ip
fi

echo "== 3/5 nginx: HTTP → HTTPS e /fase2/ → contêiner"
if ! grep -q "ssl_certificate " "$SITE" 2>/dev/null; then
    sed "s/__IP__/$IP/g" "$AQUI/nginx-site.conf" > "$SITE"
fi
nginx -t
systemctl reload nginx

echo "== 4/5 renovação automática do certificado (a cada 6 h)"
install -m 644 "$AQUI/renew-hostinger-https" /usr/local/sbin/renew-hostinger-https
install -m 644 "$AQUI/hostinger-https-renew.service" "$AQUI/hostinger-https-renew.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hostinger-https-renew.timer
bash /usr/local/sbin/renew-hostinger-https --dry-run

echo "== 5/5 deploy contínuo do painel"
bash "$AQUI/setup.sh"
echo "Pronto: https://$IP/fase2/ (o primeiro build leva alguns minutos;"
echo "acompanhe com: journalctl -u medroute-update.service -f)"
