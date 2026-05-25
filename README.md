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
├── deploy/                 # Arquivos de deploy para Linux (systemd e nginx)
├── templates_omr/          # Template OMR do cartão
├── web/
│   ├── static/             # CSS e JavaScript
│   └── templates/          # Templates HTML
├── main.py                 # Inicialização do FastAPI
├── omr_reader.py           # Motor principal de leitura OMR
├── requirements-prod.txt   # Dependências de produção
├── scripts/                # Rotinas operacionais
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
APP_STORAGE_BACKEND=mysql

DATABASE_URL=
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=omrcheck
MYSQL_USER=omrcheck
MYSQL_PASSWORD=troque-esta-senha
MYSQL_ROOT_PASSWORD=troque-a-senha-root
MYSQL_SQL_ECHO=false

KEEPEDU_API_BASE_URL=https://proposito.keepedu.com.br/api
KEEPEDU_BUSCAR_ID_URL=
KEEPEDU_API_KEY=
KEEPEDU_INSTITUTE=
ID_PROVA_KEEPEDU=
KEEPEDU_IMPORTAR_RESPOSTAS_URL=
KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL=
KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL=
KEEPEDU_LOGIN_URL=
KEEPEDU_LOGIN_SCHOOL=proposito
KEEPEDU_IMPORTAR_DIA_AVAL=1
KEEPEDU_IMPORTAR_USUARIO_ID=0
KEEPEDU_IMPORTAR_TIMEOUT_SECONDS=30

BERNOULLI_USUARIOS_URL=ROTA_USUARIOS_URL
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
BERNOULLI_PARAMETROS_URL=ROTA_PARAMETROS_URL
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

APP_ENABLE_AUTH=true
APP_SESSION_SECRET=troque-esta-chave-de-sessao
APP_SESSION_COOKIE_NAME=omrcheck_session
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
- `KEEPEDU_API_BASE_URL` permite centralizar a base da API Keep e derivar rotas como login, busca de aluno, importação de respostas e upload da folha
- `KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL` ativa um segundo envio `multipart/form-data` com a imagem original do cartão logo após o envio bem-sucedido do JSON
- `KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL` aceita rota fixa ou placeholders como `{idAval}` e `:idAval` para APIs que exigem o ID da avaliação no path
- `KEEPEDU_LOGIN_URL` e `KEEPEDU_LOGIN_SCHOOL` habilitam o login web pela API da Keep
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
- `APP_STORAGE_BACKEND=mysql` move o estado operacional do app para o MySQL; use `file` apenas como fallback local
- `DATABASE_URL` pode sobrescrever toda a montagem da conexão, se você preferir informar a string completa
- `MYSQL_*` define host, porta e credenciais do banco usado pelo app
- `APP_DATA_DIR` define onde uploads, processamentos e runtime serão persistidos
- `APP_LOG_DIR` define onde os logs operacionais serão gravados
- `APP_BACKUP_DIR` define onde os backups compactados serão salvos
- `APP_RUNTIME_DIR` define onde ficam arquivos transitórios do motor de jobs
- `APP_ALLOWED_HOSTS` limita quais hosts podem servir a aplicação
- `APP_ENABLE_AUTH`, `APP_SESSION_SECRET` e `APP_SESSION_COOKIE_NAME` controlam a proteção por sessão web
- `APP_BASIC_AUTH_USER` e `APP_BASIC_AUTH_PASSWORD` permanecem como fallback local quando a rota Keep de login não estiver configurada
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
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`

Sem proxy reverso, inclua em `APP_ALLOWED_HOSTS` o IP interno ou host real que sera usado para acessar a aplicacao.

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

## Implantacao Sem Docker

Esta e a forma recomendada quando a aplicacao vai rodar diretamente em um servidor Linux com MySQL local ou remoto.

### 1. Preparar o servidor

- instale Python 3.11+
- instale MySQL Server ou aponte para um MySQL ja existente
- crie um usuario de sistema para a aplicacao, por exemplo `omrcheck`
- copie o projeto para um caminho como `/opt/omrcheck-web`

### 2. Criar ambiente virtual

```bash
cd /opt/omrcheck-web
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-prod.txt
```

### 3. Preparar o `.env`

Exemplo minimo para MySQL local no mesmo servidor:

```env
APP_ENV=production
APP_STORAGE_BACKEND=mysql
APP_TIMEZONE=America/Sao_Paulo

DATABASE_URL=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=omrcheck
MYSQL_USER=omrcheck
MYSQL_PASSWORD=troque-esta-senha
MYSQL_SQL_ECHO=false

HOST=127.0.0.1
PORT=8000
APP_ALLOWED_HOSTS=127.0.0.1,localhost,omr.seudominio.com.br
APP_ENABLE_AUTH=true
APP_SESSION_SECRET=troque-esta-chave-de-sessao
APP_SESSION_COOKIE_NAME=omrcheck_session
APP_BASIC_AUTH_USER=operador
APP_BASIC_AUTH_PASSWORD=troque-esta-senha
```

Observacoes:

- use `MYSQL_HOST=127.0.0.1` quando o banco estiver no mesmo servidor
- use IP ou dominio real em `MYSQL_HOST` quando o banco estiver em outro servidor
- `MYSQL_ROOT_PASSWORD` nao e usado pela aplicacao fora do Docker; ele serve apenas para administracao manual

### 4. Inicializar o schema

```bash
cd /opt/omrcheck-web
source .venv/bin/activate
python -c "from app.db import init_db; init_db(); print('db ok')"
```

### 5. Validar antes da subida

```bash
python scripts/preflight.py
```

### 6. Rodar manualmente para teste

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### 7. Instalar como servico systemd

O projeto inclui um exemplo pronto em `deploy/systemd/omrcheck-web.service`.

Copie o arquivo para o servidor e ajuste estes campos, se necessario:

- `User`
- `Group`
- `WorkingDirectory`
- `ExecStart`

Depois instale o servico:

```bash
sudo cp deploy/systemd/omrcheck-web.service /etc/systemd/system/omrcheck-web.service
sudo systemctl daemon-reload
sudo systemctl enable omrcheck-web
sudo systemctl start omrcheck-web
sudo systemctl status omrcheck-web
```

Ver logs:

```bash
sudo journalctl -u omrcheck-web -f
```

### 8. Publicar com Nginx

O projeto inclui um exemplo pronto em `deploy/nginx/omrcheck-web.conf`.

Passos tipicos:

```bash
sudo cp deploy/nginx/omrcheck-web.conf /etc/nginx/sites-available/omrcheck-web.conf
sudo ln -s /etc/nginx/sites-available/omrcheck-web.conf /etc/nginx/sites-enabled/omrcheck-web.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 9. Validar

- acesse `http://127.0.0.1:8000/healthz` localmente no servidor
- se estiver usando Nginx, acesse o dominio publicado
- confirme no `healthz` que `storage_backend` esta como `mysql`
- execute um processamento pequeno de teste
- confira criacao de registros em `jobs`

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
- `runtime/`
- `logs/`
- `backups/`

No Docker, os arquivos operacionais continuam em `docker-data/` e o estado de `jobs` pode ficar em MySQL quando `APP_STORAGE_BACKEND=mysql`.

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
