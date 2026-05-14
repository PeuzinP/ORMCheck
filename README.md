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
├── docker-compose.yml      # Orquestração do container
├── Dockerfile              # Imagem Docker da aplicação
├── requirements-prod.txt   # Dependências de produção
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
KEEPEDU_BUSCAR_ID_URL=https://develop.keepedu.com.br/gestor/alunos/buscar-id-aluno
KEEPEDU_API_KEY=COLOQUE_SUA_API_KEY_AQUI
KEEPEDU_INSTITUTE=COLOQUE_O_INSTITUTE_AQUI
ID_PROVA_KEEPEDU=

APP_DATA_DIR=/data
HOST=0.0.0.0
PORT=8000

MAX_UPLOAD_FILES=300
MAX_FILE_SIZE_MB=15
MAX_TOTAL_UPLOAD_SIZE_MB=512
```

### Observações

- `KEEPEDU_API_KEY` e `KEEPEDU_INSTITUTE` são obrigatórios para a validação via API
- `APP_DATA_DIR` define onde uploads, processamentos e runtime serão persistidos
- em ambiente local sem Docker, você pode ajustar `APP_DATA_DIR` para um caminho local ou remover essa variável

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

### 2. Subir os containers

```powershell
docker compose up --build -d
```

### 3. Acessar a aplicação

- Aplicação: [http://localhost:8000](http://localhost:8000)
- Healthcheck: [http://localhost:8000/healthz](http://localhost:8000/healthz)

### 4. Comandos úteis

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

No Docker, esses dados ficam persistidos em `docker-data/`.

## Healthcheck

A rota `/healthz` retorna um JSON simples para monitoramento:

```json
{
  "status": "ok",
  "modelo_cartao_existe": true,
  "keepedu_api_configurada": true,
  "jobs_store_existe": true
}
```

## Segurança E Publicação

Antes de publicar ou compartilhar o projeto:

- nunca envie o arquivo `.env`
- nunca envie processamentos reais ou dados operacionais
- use apenas o `.env.example` como referência
- rotacione credenciais se houver suspeita de exposição anterior

## Situação Atual Do Projeto

O projeto está preparado para:

- uso local
- uso interno em equipe pequena
- deploy inicial com Docker

Ainda pode evoluir futuramente com:

- autenticação
- HTTPS com proxy reverso
- backup automatizado
- observabilidade mais robusta

## Licença

Defina a licença de uso conforme a estratégia do projeto antes de abrir colaboração externa.
