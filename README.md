# OMRCheck Web

Sistema web para leitura OMR de cartões-resposta, conferência visual das marcações, validação cadastral por RA e geração do CSV final no padrão KeepEdu.

## Visão Geral

O `OMRCheck Web` foi criado para transformar o processo de leitura de cartões-resposta em um fluxo operacional mais seguro e auditável.

O sistema permite:

- enviar imagens de cartões em lote
- processar a leitura OMR com template
- revisar visualmente as marcações detectadas
- validar a identificação do aluno por meio do RA e da API KeepEdu
- corrigir pendências manualmente quando necessário
- gerar o CSV final para importação

## Principais Funcionalidades

- Leitura OMR baseada em template `.xtmpl`
- Upload múltiplo de imagens `.jpg`, `.jpeg` e `.png`
- Painel web para revisão das marcações
- Validação cadastral com apoio da API KeepEdu
- Exportação do CSV final mesmo com pendências, mediante confirmação
- Healthcheck para monitoramento em `/healthz`
- Execução local e via Docker
- Autenticação HTTP básica opcional para acesso interno

## Stack Utilizada

- Python 3.11
- FastAPI
- Jinja2
- OpenCV
- NumPy
- Pandas
- Requests
- Docker / Docker Compose

## Estrutura Do Projeto

```text
OMRCheck-Web/
├── app/                    # Regras de negócio, rotas e serviços
├── assets/                 # Ícone e arquivos estáticos auxiliares
├── templates_omr/          # Template OMR do cartão
├── web/
│   ├── static/             # CSS e JavaScript
│   └── templates/          # Templates HTML
├── main.py                 # Inicialização do FastAPI
├── omr_reader.py           # Motor principal de leitura OMR
├── docker-compose.yml      # Orquestração principal com acesso direto
├── docker-compose.cloudflare.yml # Orquestração para deploy via Cloudflare Tunnel
├── Dockerfile              # Imagem Docker da aplicação
├── requirements-prod.txt   # Dependências de produção
├── scripts/                # Rotinas operacionais
├── CHECKLIST_IMPLANTACAO.md # Checklist curto de subida no setor
└── .env.example            # Exemplo de configuração do ambiente
```

## Requisitos

- Python 3.11+
- Docker Desktop, se for usar containers
- Template OMR disponível em `templates_omr/modelo_cartao.xtmpl`
- Credenciais válidas da integração KeepEdu

## Variáveis De Ambiente

Crie um arquivo `.env` na raiz do projeto com base no `.env.example`.

Exemplo:

```env
APP_ENV=production
APP_TIMEZONE=America/Sao_Paulo

KEEPEDU_BUSCAR_ID_URL=https://develop.keepedu.com.br/api/customers/buscar-id-aluno
KEEPEDU_API_KEY=
KEEPEDU_INSTITUTE=
ID_PROVA_KEEPEDU=
KEEPEDU_IMPORTAR_RESPOSTAS_URL=http://localhost/github-app/keepedu/api/avaliacoes/importar-respostas-presenciais
KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL=
KEEPEDU_IMPORTAR_DIA_AVAL=1
KEEPEDU_IMPORTAR_USUARIO_ID=0
KEEPEDU_IMPORTAR_TIMEOUT_SECONDS=30

BERNOULLI_USUARIOS_URL=http://api.bernoulli.com.br/api/gerenciar/acessos/usuarios/listar
BERNOULLI_AUTHORIZATION=
BERNOULLI_COOKIE=
BERNOULLI_PAGE_SIZE=10
BERNOULLI_GRUPO_USUARIO=5
BERNOULLI_FRONT_VERSION=4.25.72
BERNOULLI_PLATAFORMA=2
BERNOULLI_ORIGIN=https://mb4.bernoulli.com.br
BERNOULLI_REFERER=https://mb4.bernoulli.com.br/
BERNOULLI_LOGIN_URL=
BERNOULLI_LOGIN_METHOD=POST
BERNOULLI_LOGIN_USERNAME=
BERNOULLI_LOGIN_PASSWORD=
BERNOULLI_LOGIN_USERNAME_FIELD=usuario
BERNOULLI_LOGIN_PASSWORD_FIELD=senha
BERNOULLI_LOGIN_USE_FORM=false
BERNOULLI_LOGIN_EXTRA_PAYLOAD={}
BERNOULLI_LOGIN_HEADERS={}
BERNOULLI_LOGIN_TOKEN_PATH=token
BERNOULLI_LOGIN_COOKIE_NAMES=
BERNOULLI_PARAMETROS_URL=https://api.bernoulli.com.br/api/autenticado/parametros
BERNOULLI_PARAMETROS_METHOD=POST
BERNOULLI_PARAMETROS_USE_FORM=false
BERNOULLI_PARAMETROS_PAYLOAD={}
BERNOULLI_PARAMETROS_HEADERS={}
BERNOULLI_PARAMETROS_TOKEN_PATH=access_token
BERNOULLI_AUTH_HEADER_PREFIX=Bearer
BERNOULLI_AUTH_REFRESH_MARGIN_SECONDS=300
BERNOULLI_AUTH_CACHE_FILE=/data/runtime/bernoulli_auth.json

APP_DATA_DIR=/data
APP_LOG_DIR=/data/logs
APP_BACKUP_DIR=/data/backups
APP_PROCESSAMENTOS_DIR=/data/processamentos
APP_UPLOADS_TEMP_DIR=/data/uploads_temp
APP_RUNTIME_DIR=/data/runtime

HOST=0.0.0.0
PORT=8000
APP_ALLOWED_HOSTS=localhost,127.0.0.1,SEU_IP_OU_HOST_INTERNO
CLOUDFLARE_TUNNEL_TOKEN=

APP_ENABLE_AUTH=true
APP_BASIC_AUTH_USER=operador
APP_BASIC_AUTH_PASSWORD=troque-esta-senha

MAX_UPLOAD_FILES=300
MAX_FILE_SIZE_MB=15
MAX_TOTAL_UPLOAD_SIZE_MB=512

APP_LOG_LEVEL=INFO
APP_RETENTION_DAYS=45
APP_UPLOAD_TEMP_RETENTION_HOURS=24
APP_BACKUP_ENABLED=true
```

### Observações

- `KEEPEDU_API_KEY` e `KEEPEDU_INSTITUTE` são obrigatórios para a validação via API
- `BERNOULLI_AUTHORIZATION` e `BERNOULLI_COOKIE` permitem autenticação manual, mas podem expirar
- `BERNOULLI_LOGIN_*` permite que o backend refaça login e mantenha a sessão Bernoulli de forma automática
- `BERNOULLI_PARAMETROS_*` permite executar o passo intermediário que troca o token inicial por um token autorizado para as APIs autenticadas
- `BERNOULLI_LOGIN_EXTRA_PAYLOAD` e `BERNOULLI_LOGIN_HEADERS` aceitam JSON para adaptar o payload/headers do login real observado no navegador
- `BERNOULLI_PARAMETROS_PAYLOAD` e `BERNOULLI_PARAMETROS_HEADERS` aceitam JSON para o POST em `/api/autenticado/parametros`
- `BERNOULLI_LOGIN_TOKEN_PATH` define onde o token vem na resposta JSON do login, por exemplo `token` ou `data.access_token`
- `BERNOULLI_PARAMETROS_TOKEN_PATH` define onde vem o token devolvido pela etapa `/api/autenticado/parametros`
- `BERNOULLI_LOGIN_COOKIE_NAMES` pode limitar quais cookies da resposta devem ser persistidos
- `BERNOULLI_AUTH_CACHE_FILE` guarda a sessão Bernoulli reaproveitável em arquivo local de runtime
- `APP_TIMEZONE` padroniza a exibição de datas e horários do sistema
- `APP_DATA_DIR` define onde uploads, processamentos e runtime serão persistidos
- `APP_LOG_DIR` define onde os logs operacionais serão gravados
- `APP_BACKUP_DIR` define onde os backups compactados serão salvos
- `APP_RUNTIME_DIR` define onde ficam arquivos transitórios do motor de jobs
- `APP_ALLOWED_HOSTS` limita quais hosts podem servir a aplicação
- `CLOUDFLARE_TUNNEL_TOKEN` é usado apenas no deploy com Cloudflare Tunnel
- `APP_ENABLE_AUTH`, `APP_BASIC_AUTH_USER` e `APP_BASIC_AUTH_PASSWORD` controlam a proteção por login HTTP básico
- `APP_RETENTION_DAYS` define a retenção de processamentos e logs antigos
- `APP_UPLOAD_TEMP_RETENTION_HOURS` define a retenção dos uploads temporários
- `APP_BACKUP_ENABLED` define se a rotina operacional deve gerar backup antes da limpeza
- em ambiente local sem Docker, você pode ajustar `APP_DATA_DIR` para um caminho local ou remover essa variável

### Autenticação Bernoulli

- Se você já tem um `Authorization` ou `Cookie` válido, pode continuar usando `BERNOULLI_AUTHORIZATION` e `BERNOULLI_COOKIE`
- Para evitar atualização manual, capture uma requisição de login bem-sucedida no navegador e preencha `BERNOULLI_LOGIN_URL`, campos de usuário/senha e, se necessário, `BERNOULLI_LOGIN_HEADERS`/`BERNOULLI_LOGIN_EXTRA_PAYLOAD`
- Se a Bernoulli devolver um novo `access_token` em `/api/autenticado/parametros`, preencha também `BERNOULLI_PARAMETROS_*` com o payload observado nessa chamada
- O backend passa a reaproveitar a sessão salva em `BERNOULLI_AUTH_CACHE_FILE` e tenta renovar automaticamente quando o JWT estiver perto de expirar ou quando a API responder com `401`, `403` ou HTML de sessão expirada
- Se o login do MB4 usar SSO externo, talvez seja necessário reproduzir no `.env` o endpoint interno que realmente entrega o token/cookies para a API

## Execução Local

### 1. Criar e ativar ambiente virtual

No Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Instalar dependências

Para ambiente de produção/local enxuto:

```powershell
pip install -r requirements-prod.txt
```

Se quiser usar o conjunto completo do projeto:

```powershell
pip install -r requirements.txt
```

### 3. Configurar o `.env`

Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

Depois preencha os valores reais.

### 4. Subir o servidor

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Acessar a aplicação

- Aplicação: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Healthcheck: [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)

## Execução Com Docker

### 1. Criar o `.env`

```powershell
Copy-Item .env.example .env
```

Preencha os valores reais antes de subir.

### 2. Ajustar credenciais e acesso

Antes de subir em servidor, preencha no `.env`:

- `APP_BASIC_AUTH_USER`
- `APP_BASIC_AUTH_PASSWORD`
- `APP_ALLOWED_HOSTS`

Sem proxy reverso, inclua em `APP_ALLOWED_HOSTS` o IP interno ou host real que sera usado para acessar a aplicacao.
Com Cloudflare Tunnel, inclua o dominio publico real, por exemplo `omr.suaempresa.com.br`.

### 3. Executar preflight

Antes da subida, rode:

```powershell
python scripts/preflight.py
```

Esse script valida:

- `.env`
- `APP_ENV=production`
- autenticação habilitada
- senha não padrão
- `APP_ALLOWED_HOSTS` ajustado para implantação
- credenciais KeepEdu
- template OMR
- diretórios operacionais

### 4. Subir os containers

```powershell
docker compose up --build -d
```

### 5. Acessar a aplicação

- Aplicação no servidor: `http://IP_DO_SERVIDOR:8000`
- Aplicação local: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Healthcheck: `http://IP_DO_SERVIDOR:8000/healthz`

### 6. Comandos úteis

Ver status:

```powershell
docker compose ps
```

Ver logs:

```powershell
docker compose logs -f
```

Parar:

```powershell
docker compose down
```

Rebuild completo:

```powershell
docker compose build --no-cache
docker compose up -d
```

### 7. Arquitetura de produção

No modo atual, o projeto sobe com um servico:

- `omrcheck-web`: aplicação FastAPI/Uvicorn acessível diretamente na porta `8000`

## Implantacao Com Cloudflare Tunnel

Essa e a forma recomendada quando o dominio da empresa ja esta no Cloudflare.

### 1. Preparar o `.env`

Preencha no `.env`:

- `APP_ALLOWED_HOSTS` com o dominio publico real, por exemplo `omr.suaempresa.com.br`
- `APP_BASIC_AUTH_USER` e `APP_BASIC_AUTH_PASSWORD`
- `CLOUDFLARE_TUNNEL_TOKEN` com o token do tunnel criado no painel do Cloudflare

Exemplo:

```env
APP_ALLOWED_HOSTS=localhost,127.0.0.1,omr.suaempresa.com.br
CLOUDFLARE_TUNNEL_TOKEN=SEU_TOKEN_DO_TUNNEL
```

### 2. Criar o Tunnel no Cloudflare

No painel do Cloudflare:

- crie um `Cloudflare Tunnel`
- publique um hostname como `omr.suaempresa.com.br`
- aponte o servico para `http://omrcheck-web:8000`
- copie o token gerado pelo Cloudflare para `CLOUDFLARE_TUNNEL_TOKEN`

### 3. Executar preflight

Antes da subida, rode:

```powershell
python scripts/preflight.py
```

### 4. Subir a stack com Cloudflare

```powershell
docker compose -f docker-compose.cloudflare.yml up --build -d
```

### 5. Validar

- acesse o dominio publicado no Cloudflare
- confira `https://SEU_DOMINIO/healthz`
- valide o login basico
- execute um processamento pequeno de teste
- confira escrita em `docker-data/processamentos`

Comandos uteis:

```powershell
docker compose -f docker-compose.cloudflare.yml ps
docker compose -f docker-compose.cloudflare.yml logs -f
docker compose -f docker-compose.cloudflare.yml down
```

### 6. Observacoes

- nesse modo a aplicacao nao expoe a porta `8000` publicamente no servidor
- o trafego externo entra pelo Cloudflare e chega ao container via `cloudflared`
- se precisar acesso local temporario para testes, use o `docker-compose.yml` tradicional

## Fluxo De Uso

### 1. Novo processamento

Na tela inicial, envie as imagens dos cartões-resposta.

### 2. Leitura OMR

O sistema processa os cartões com base no template e gera:

- leituras
- imagens de debug
- log de processamento

### 3. Painel de correção

No painel de correção, é possível:

- navegar entre os cartões
- ampliar a visualização
- revisar as marcações
- salvar correções manuais

### 4. Validação cadastral

O sistema usa:

- ID lido diretamente do cartão, quando existir
- RA detectado no cartão para buscar o ID via API KeepEdu

Se necessário, o operador pode informar o ID manualmente.

### 5. Geração do CSV final

Após a validação:

- o CSV final pode ser gerado normalmente
- se houver pendências, o sistema pode gerar o CSV mesmo assim mediante confirmação

## Persistência De Dados

Os principais artefatos gerados pelo sistema são:

- `processamentos/`
- `uploads_temp/`
- `runtime/jobs.json`
- `logs/`
- `backups/`

No Docker, esses dados ficam persistidos em `docker-data/`.

## Dados Sensíveis E Arquivos Não Versionados

Para evitar vazamento de credenciais ou dados operacionais, o repositório deve manter fora do commit:

- `.env` e qualquer variante local de ambiente
- diretórios operacionais como `docker-data/`, `processamentos/`, `uploads_temp/`, `logs/`, `backups/`, `base/` e `runtime/`
- certificados, chaves e arquivos de banco local como `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.pfx`, `*.db` e `*.sqlite*`
- caches locais e ambientes de desenvolvimento como `.venv/`, `venv/`, `.pytest_cache/`, `.mypy_cache/` e `.ruff_cache/`

Integrações que exigem atenção especial:

- `KEEPEDU_API_KEY`
- `KEEPEDU_INSTITUTE`
- `BERNOULLI_AUTHORIZATION`
- `BERNOULLI_COOKIE`
- `APP_BASIC_AUTH_PASSWORD`

Se algum desses arquivos já tiver sido versionado no passado, remova do índice antes do próximo push:

```powershell
git rm --cached -r .env docker-data processamentos uploads_temp logs backups base runtime
```

Depois disso, confirme se o `.gitignore` cobre os caminhos corretos antes de gerar novo commit.

## Backup E Retenção

O projeto possui uma rotina operacional em `scripts/maintenance.py`.

Gerar backup:

```powershell
python scripts/maintenance.py backup
```

Executar limpeza:

```powershell
python scripts/maintenance.py cleanup
```

Executar backup e limpeza:

```powershell
python scripts/maintenance.py all
```

Executar apenas simulação:

```powershell
python scripts/maintenance.py all --dry-run
```

Essa rotina usa:

- `APP_RETENTION_DAYS`
- `APP_UPLOAD_TEMP_RETENTION_HOURS`
- `APP_BACKUP_ENABLED`

## Checklist Rápido

Existe também um checklist resumido em [CHECKLIST_IMPLANTACAO.md](./CHECKLIST_IMPLANTACAO.md) para a subida do ambiente do setor.

## Healthcheck

A rota `/healthz` retorna um JSON simples para monitoramento:

```json
{
  "status": "ok",
  "app_env": "production",
  "auth_enabled": true,
  "modelo_cartao_existe": true,
  "keepedu_api_configurada": true,
  "jobs_store_existe": true,
  "logs_dir": "/data/logs",
  "backups_dir": "/data/backups",
  "backup_enabled": true
}
```

## Observabilidade E Suporte

Além do store de jobs, a aplicação grava log rotativo em `APP_LOG_DIR`.

Exemplo:

- `/data/logs/omrcheck-production.log`

Isso facilita suporte, conferência de startup e diagnóstico básico do ambiente.

## Segurança E Publicação

Antes de publicar ou compartilhar o projeto:

- nunca envie o arquivo `.env`
- nunca envie tokens da integração Bernoulli ou credenciais KeepEdu em texto puro
- nunca envie processamentos reais ou dados operacionais
- use apenas o `.env.example` como referência
- rotacione credenciais se houver suspeita de exposição anterior
- troque a senha padrão de `APP_BASIC_AUTH_PASSWORD` antes de qualquer deploy
- configure `APP_ALLOWED_HOSTS` com o IP ou host real do servidor
- revise o `git status` antes de cada commit para garantir que nenhum dado do diretório operacional entrou por engano

## Situação Atual Do Projeto

O projeto está preparado para:

- uso local
- uso interno em equipe pequena
- deploy inicial com Docker

Ainda pode evoluir futuramente com:

- backup automatizado
- observabilidade mais robusta
- fila de processamento separada da aplicação web

## Licença

Defina a licença de uso conforme a estratégia do projeto antes de abrir colaboração externa.
