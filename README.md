arquivo: README.md
conteudo: |
# OMRCheck Web

Sistema web para leitura OMR de cartões-resposta, conferência visual das marcações, validação cadastral por RA e geração de arquivos para importação nas plataformas KeepEdu e Bernoulli.

## Visão Geral

O `OMRCheck Web` foi criado para transformar o processo de leitura de cartões-resposta em um fluxo operacional mais seguro e auditável. O sistema permite:

- Enviar imagens de cartões em lote.
- Processar a leitura OMR com base em um template.
- Revisar visualmente as marcações detectadas em uma interface web.
- Validar a identificação do aluno por meio do RA e de APIs externas (KeepEdu, Bernoulli).
- Corrigir pendências de identificação e leitura manualmente.
- Gerar os arquivos finais para importação nos formatos esperados.

## Principais Funcionalidades

- **Leitura OMR:** Baseada em template `.xtmpl` do FormScanner.
- **Upload de Imagens:** Suporte a upload múltiplo de arquivos `.jpg`, `.jpeg` e `.png`.
- **Painel de Revisão:** Interface web para conferência e correção das leituras.
- **Validação Cadastral:** Integração com APIs KeepEdu e Bernoulli para validar alunos.
- **Exportação:** Geração de CSV para KeepEdu e XLSX para Bernoulli.
- **Processamento Assíncrono:** Tarefas longas (leitura OMR, importação) rodam em background.
- **Monitoramento:** Endpoint `/healthz` para verificação de saúde da aplicação.
- **Autenticação:** Acesso à interface protegido por login.

## Stack Utilizada

- **Backend:** Python 3.11+, FastAPI
- **Frontend:** Jinja2, HTML, CSS, JavaScript
- **Processamento de Imagem:** OpenCV, NumPy
- **Manipulação de Dados:** Pandas
- **Comunicação API:** Requests
- **Banco de Dados:** SQLAlchemy (com suporte a MySQL)
- **Deployment:** Docker/Docker Compose, Nginx, Systemd

## Estrutura do Projeto

```text
OMRCheck-Web/
├── app/                    # Lógica da aplicação, rotas e serviços
├── assets/                 # Ícone e arquivos estáticos auxiliares
├── deploy/                 # Arquivos de deploy para Linux (systemd, nginx)
├── templates_omr/          # Template OMR do cartão
├── web/
│   ├── static/             # CSS e JavaScript
│   └── templates/          # Templates HTML (Jinja2)
├── .env.example            # Exemplo de configuração de ambiente
├── main.py                 # Ponto de entrada da aplicação (FastAPI)
├── omr_reader.py           # Motor principal de leitura OMR
├── requirements-prod.txt   # Dependências de produção
└── scripts/                # Rotinas de manutenção e validação
```

## Requisitos

- Python 3.11+
- Docker Desktop (para execução em container)
- Template OMR (`modelo_cartao.xtmpl`) na pasta `templates_omr/`
- Credenciais válidas para as integrações (KeepEdu, Bernoulli)

## Configuração (Variáveis de Ambiente)

Crie um arquivo `.env` na raiz do projeto, utilizando o `.env.example` como base.

### Principais Variáveis

#### Gerais
- `APP_ENV`: Ambiente (`production` ou `development`).
- `APP_TIMEZONE`: Fuso horário (ex: `America/Sao_Paulo`).
- `APP_STORAGE_BACKEND`: Persistência dos jobs (`mysql` ou `file`).
- `HOST`, `PORT`: Endereço e porta do servidor web.
- `APP_ALLOWED_HOSTS`: Lista de hosts permitidos (ex: `localhost,127.0.0.1,meu-dominio.com`).
- `CLOUDFLARE_TUNNEL_TOKEN`: Token para publicação via Cloudflare Tunnel (opcional).

#### Autenticação
- `APP_ENABLE_AUTH`: Habilita (`true`) ou desabilita (`false`) a tela de login.
- `APP_SESSION_SECRET`: Chave secreta para a sessão do usuário.
- `APP_BASIC_AUTH_USER`, `APP_BASIC_AUTH_PASSWORD`: Credenciais de fallback se o login KeepEdu não estiver configurado.

#### Banco de Dados (se `APP_STORAGE_BACKEND=mysql`)
- `DATABASE_URL`: String de conexão completa (alternativa ao preenchimento individual).
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`: Credenciais do MySQL.

#### Integração KeepEdu
- `KEEPEDU_API_KEY`, `KEEPEDU_INSTITUTE`: Credenciais para a API.
- `KEEPEDU_BUSCAR_ID_URL`: Endpoint para buscar alunos por RA.
- `KEEPEDU_IMPORTAR_RESPOSTAS_URL`: Endpoint para enviar as respostas.
- `KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL`: Endpoint para enviar a imagem do cartão.
- `KEEPEDU_LOGIN_URL`, `KEEPEDU_LOGIN_SCHOOL`: Habilitam o login na interface web via API KeepEdu.

#### Integração Bernoulli
- `BERNOULLI_USUARIOS_URL`: Endpoint para buscar usuários (alunos).
- **Autenticação Automática (Recomendado):**
  - `BERNOULLI_LOGIN_URL`, `BERNOULLI_LOGIN_USERNAME`, `BERNOULLI_LOGIN_PASSWORD`: Permitem que o backend renove a sessão automaticamente.
  - `BERNOULLI_PARAMETROS_URL`: Endpoint secundário para troca de token, se necessário.
  - `BERNOULLI_AUTH_CACHE_FILE`: Caminho para salvar a sessão autenticada.
- **Autenticação Manual (Alternativa):**
  - `BERNOULLI_AUTHORIZATION`, `BERNOULLI_COOKIE`: Token e cookie estáticos, que podem expirar.

#### Limites e Retenção
- `MAX_UPLOAD_FILES`, `MAX_FILE_SIZE_MB`, `MAX_TOTAL_UPLOAD_SIZE_MB`: Limites para upload de imagens.
- `APP_RETENTION_DAYS`: Período para retenção de processamentos antigos.

## Execução Local

1.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # No Linux/macOS
    # .\.venv\Scripts\Activate.ps1  # No Windows (PowerShell)
    ```

2.  **Instale as dependências:**
    ```bash
    pip install -r requirements-prod.txt
    ```

3.  **Configure o `.env`:**
    Copie o `.env.example` para `.env` e preencha as variáveis necessárias para o seu ambiente.

4.  **Inicie o servidor:**
    ```bash
    uvicorn main:app --reload --host 127.0.0.1 --port 8000
    ```

5.  **Acesse a aplicação:**
    - **Aplicação:** http://127.0.0.1:8000
    - **Healthcheck:** http://127.0.0.1:8000/healthz

## Implantação

### Opção 1: Docker (Recomendado)

O projeto está configurado para rodar com Docker Compose.

- **Construir e iniciar os containers:**
  ```bash
  docker compose up -d --build
  ```
- **Verificar o status:**
  ```bash
  docker compose ps
  ```
- **Ver logs em tempo real:**
  ```bash
  docker compose logs -f
  ```
- **Parar os containers:**
  ```bash
  docker compose down
  ```

### Opção 2: Servidor Linux (sem Docker)

Esta abordagem é ideal para rodar a aplicação diretamente em um servidor Linux.

1.  **Prepare o Servidor:**
    - Instale Python 3.11+.
    - Configure um servidor MySQL (local ou remoto).
    - Clone o projeto (ex: em `/opt/omrcheck-web`).

2.  **Configure o Ambiente:**
    - Crie e ative um ambiente virtual e instale as dependências, como na execução local.
    - Configure o arquivo `.env` com as variáveis de produção, apontando para o banco de dados e definindo os hosts permitidos.

3.  **Inicialize o Banco de Dados:**
    Se estiver usando MySQL, crie o schema da aplicação:
    ```bash
    # Ative o ambiente virtual antes
    python -c "from app.db import init_db; init_db(); print('Schema do DB inicializado.')"
    ```

4.  **Valide a Configuração:**
    Execute o script de pre-flight para checar as configurações críticas:
    ```bash
    python scripts/preflight.py
    ```

5.  **Instale como Serviço (Systemd):**
    - Edite o arquivo `deploy/systemd/omrcheck-web.service` para ajustar os caminhos (`WorkingDirectory`, `ExecStart`) e o usuário (`User`).
    - Copie o serviço, habilite e inicie:
      ```bash
      sudo cp deploy/systemd/omrcheck-web.service /etc/systemd/system/
      sudo systemctl daemon-reload
      sudo systemctl enable --now omrcheck-web
      sudo systemctl status omrcheck-web
      ```

6.  **Configure um Proxy Reverso (Nginx):**
    - Edite o arquivo `deploy/nginx/omrcheck-web.conf` para ajustar o `server_name` para o seu domínio.
    - Crie o link simbólico, teste a configuração e recarregue o Nginx:
      ```bash
      sudo cp deploy/nginx/omrcheck-web.conf /etc/nginx/sites-available/
      sudo ln -s /etc/nginx/sites-available/omrcheck-web.conf /etc/nginx/sites-enabled/
      sudo nginx -t
      sudo systemctl reload nginx
      ```

## Fluxo de Uso

1.  **Nova Avaliação:** Na tela inicial, envie as imagens dos cartões-resposta. O sistema iniciará um job em background.
2.  **Leitura OMR:** O sistema processa os cartões da avaliação, gerando as leituras, imagens de debug e logs.
3.  **Painel de Correção:** Acesse a avaliação para revisar as marcações, ampliar imagens e corrigir leituras duvidosas.
4.  **Validação Cadastral:** O sistema cruza o RA lido com a API externa para obter o ID do aluno. Pendências podem ser resolvidas manualmente pelo operador.
5.  **Geração de Arquivos:** Após a validação, gere o CSV (KeepEdu) ou XLSX (Bernoulli) para importação.

## Persistência de Dados

Os artefatos gerados são armazenados em pastas definidas pelas variáveis de ambiente (`APP_DATA_DIR`, etc.).
- `processamentos/`: Contém os resultados de cada lote de leitura (internamente chamado de "processamento").
- `uploads_temp/`: Armazenamento temporário para uploads.
- `runtime/`: Arquivos de estado, como cache de autenticação.
- `logs/`: Logs da aplicação.
- `backups/`: Backups gerados pela rotina de manutenção.

Quando `APP_STORAGE_BACKEND=mysql`, o estado dos jobs é persistido no banco de dados, garantindo maior robustez.

## Rotinas de Manutenção

O script `scripts/maintenance.py` ajuda a gerenciar o armazenamento.

- **Gerar backup:**
  ```bash
  python scripts/maintenance.py backup
  ```
- **Executar limpeza de arquivos antigos:**
  ```bash
  python scripts/maintenance.py cleanup
  ```
- **Executar ambos (backup e limpeza):**
  ```bash
  python scripts/maintenance.py all
  ```

A retenção é controlada pelas variáveis `APP_RETENTION_DAYS` e `APP_UPLOAD_TEMP_RETENTION_HOURS`.

## Monitoramento (Healthcheck)

A rota `/healthz` retorna um JSON com o status da aplicação, útil para sistemas de monitoramento.

```json
{
  "status": "ok",
  "app_env": "production",
  "auth_enabled": true,
  "storage_backend": "mysql",
  "modelo_cartao_existe": true,
  "keepedu_api_configurada": true
}
```

## Segurança

- **Nunca versione o arquivo `.env`!** Ele contém credenciais e segredos.
- Utilize senhas fortes para `APP_BASIC_AUTH_PASSWORD` e para o banco de dados.
- Troque a `APP_SESSION_SECRET` por um valor longo e aleatório.
- Configure `APP_ALLOWED_HOSTS` para permitir acesso apenas dos domínios corretos.
- Revise o `git status` antes de cada commit para garantir que nenhum dado sensível ou operacional seja enviado ao repositório.

## Licença

Defina a licença de uso do projeto conforme a sua estratégia antes de distribuí-lo ou abrir para colaboração.