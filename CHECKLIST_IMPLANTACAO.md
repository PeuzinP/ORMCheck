# Checklist De Implantacao

## Antes De Subir

- Criar `.env` a partir de `.env.example`
- Definir `APP_ENV=production`
- Trocar `APP_BASIC_AUTH_USER` e `APP_BASIC_AUTH_PASSWORD`
- Ajustar `APP_ALLOWED_HOSTS` para incluir o dominio publico real no Cloudflare
- Preencher `KEEPEDU_API_KEY`
- Preencher `KEEPEDU_INSTITUTE`
- Preencher `CLOUDFLARE_TUNNEL_TOKEN`
- Confirmar presenca de `templates_omr/modelo_cartao.xtmpl`
- Criar o hostname publico no Cloudflare Tunnel apontando para `http://omrcheck-web:8000`

## Preflight

Executar:

```powershell
python scripts/preflight.py
```

O preflight valida:

- `.env`
- ambiente em `production`
- autenticacao habilitada
- senha nao padrao
- `APP_ALLOWED_HOSTS` ajustado para implantacao
- credenciais KeepEdu
- template OMR
- diretorios operacionais

## Subida

Executar:

```powershell
docker compose -f docker-compose.cloudflare.yml up --build -d
```

Validar:

```powershell
docker compose -f docker-compose.cloudflare.yml ps
docker compose -f docker-compose.cloudflare.yml logs -f
```

## Pos-Implantacao

- Abrir a aplicacao pelo dominio publicado no Cloudflare
- Conferir `https://SEU_DOMINIO/healthz`
- Fazer um processamento de teste com poucas imagens
- Validar geracao de CSV
- Validar login basico
- Validar escrita em `docker-data/processamentos`
- Gerar um backup manual inicial

## Operacao

Backup:

```powershell
python scripts/maintenance.py backup
```

Limpeza:

```powershell
python scripts/maintenance.py cleanup
```

Simulacao completa:

```powershell
python scripts/maintenance.py all --dry-run
```
