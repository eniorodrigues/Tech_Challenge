# MedRoute na Hostinger

Painel publicado: **https://187.127.18.205/fase2/** (HTTP redireciona para HTTPS).

![Implantação](reports/figures/00e_implantacao.png)

## Como está montado

| Peça | O que faz | Arquivo no repositório |
|---|---|---|
| VPS | Hostinger, Ubuntu 24.04, criada pelo painel da Hostinger (cloud-init padrão da Hostinger: senha de root e SSH) | — |
| Provisionamento | instala Docker e nginx, emite o certificado, liga a renovação e o deploy contínuo | [`deploy/provision.sh`](deploy/provision.sh) |
| nginx | HTTP 80 → HTTPS 443; `/fase2/` → contêiner em `127.0.0.1:8501` (com WebSocket); `/` atende outro sistema (contêiner `nfe-scrap`) | [`deploy/nginx-site.conf`](deploy/nginx-site.conf) (site completo) · [`deploy/nginx-location.conf`](deploy/nginx-location.conf) (só o bloco `/fase2/`) |
| Certificado | Let's Encrypt para o **endereço IP** (perfil `shortlived`, validade de ~6,5 dias), desafio `webroot` em `/var/www/letsencrypt` | emitido pelo `provision.sh` |
| Renovação | `hostinger-https-renew.timer` a cada 6 h → `certbot renew` (imagem Docker `certbot/certbot`) → `nginx -t` e reload | [`deploy/renew-hostinger-https`](deploy/renew-hostinger-https) · [`.service`](deploy/hostinger-https-renew.service) · [`.timer`](deploy/hostinger-https-renew.timer) |
| Deploy contínuo | `medroute-update.timer` a cada 60 s → `update.sh`: `git fetch` da `main`; se houver commit novo, `git archive` da `fase2/`, `docker build`, troca do contêiner e *health check* em `/fase2/_stcore/health` (a revisão só é gravada se o painel responder) | [`deploy/setup.sh`](deploy/setup.sh) · [`deploy/update.sh`](deploy/update.sh) · [`.service`](deploy/medroute-update.service) · [`.timer`](deploy/medroute-update.timer) |
| Contêiner | imagem do [`Dockerfile`](Dockerfile) (Python 3.12 slim), só o painel Streamlit (`baseUrlPath=fase2`), usuário sem privilégio (uid 10002), 1 CPU, 1536 MB, `restart unless-stopped`, porta só em `127.0.0.1` | [`Dockerfile`](Dockerfile) · [`.dockerignore`](.dockerignore) · [`.streamlit/config.toml`](.streamlit/config.toml) |

Pastas persistentes: `/opt/medroute/data`, `/opt/medroute/reports` e `/opt/medroute/cache`
(inclui o cache das respostas da LLM). Arquivos iniciais são copiados sem sobrescrever os existentes.

**Chave da OpenRouter**: fica só em `/opt/medroute/runtime.env` (permissão 600), fora do Git e da
imagem; o `update.sh` a passa ao contêiner com `--env-file` a cada atualização. Sem o arquivo, o
painel usa o modo offline da LLM. Para criar ou trocar a chave:

```bash
install -m 600 /dev/null /opt/medroute/runtime.env
nano /opt/medroute/runtime.env          # OPENROUTER_API_KEY=...
rm /opt/medroute/deployed-revision      # força o próximo ciclo a recriar o contêiner
```

Não são expostos por este deploy: a API REST, o notebook e o gerador de vídeo (rodam localmente).

## Recriar numa VPS nova

Ubuntu 24.04 limpa, portas 80 e 443 liberadas, como root:

```bash
apt-get install -y git
git clone --branch main https://github.com/eniorodrigues/Tech_Challenge.git /opt/medroute/repo
bash /opt/medroute/repo/fase2/deploy/provision.sh <IP-da-VPS>
```

O script é idempotente: numa VPS já provisionada ele não troca o certificado nem o site do nginx.
Ele foi montado a partir da VPS em produção (arquivos copiados de lá; o site do nginx difere só na
raiz `/`, que em produção atende o outro sistema) e não foi reexecutado numa VPS limpa.

## Operação

```bash
systemctl list-timers medroute-update.timer hostinger-https-renew.timer
journalctl -u medroute-update.service -n 60 --no-pager
journalctl -u hostinger-https-renew.service -n 20 --no-pager
docker logs --tail 60 medroute
openssl x509 -in /etc/letsencrypt/live/hostinger-ip/cert.pem -noout -enddate
```

* Suspender as atualizações: `systemctl disable --now medroute-update.timer`.
* Uma atualização reinicia as sessões abertas do painel.
* O painel não tem login (demonstração com dados sintéticos).

## Segurança

* Nenhum segredo no repositório nem na imagem; a porta do contêiner só escuta em `127.0.0.1`.
* Próximo passo recomendado: SSH só por chave (desligar login por senha) e um usuário de deploy
  sem root; firewall liberando apenas 22, 80 e 443.
