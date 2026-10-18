# MedRoute na Hostinger

Painel: http://187.127.18.205/fase2/

O timer `medroute-update.timer` verifica a branch `main` do repositorio
`eniorodrigues/Tech_Challenge` a cada minuto. A construcao usa o Dockerfile
em `fase2/` e publica somente o painel dessa fase. O sistema de notas
continua no endereco principal, em outro conteiner.

Pastas persistentes: `/opt/medroute/data`, `/opt/medroute/reports` e
`/opt/medroute/cache`. Arquivos iniciais sao copiados sem sobrescrever os
existentes. A chave da OpenRouter, quando configurada, fica em
`/opt/medroute/runtime.env`, com permissao 600, fora do Git e da imagem.
O deploy carrega esse arquivo a cada atualizacao. Sem chave, usa modo offline.
O container tem limite de 1536 MB e uma CPU. Uma atualizacao reinicia as
sessoes abertas do painel. O acesso inicial e HTTP e nao possui login.

```bash
systemctl list-timers medroute-update.timer
journalctl -u medroute-update.service -n 60 --no-pager
docker logs --tail 60 medroute
```

Para suspender atualizacoes: `systemctl disable --now medroute-update.timer`.
A API REST, notebooks e geradores de video nao sao expostos por este deploy.
