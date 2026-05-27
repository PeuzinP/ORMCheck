import secrets
from datetime import datetime, timedelta
import mysql.connector  # Ou o módulo que seu projeto usa para conectar (ex: SQLAlchemy)
from fastapi import Request, Response
from datetime import datetime, timedelta, timezone # <--- Importe o timezone

# ... (restante dos imports)

def gerenciar_lembre_me(response: Response, usuario_id: int):
    token = secrets.token_hex(32)
    # Agora usamos timezone.utc para garantir que o datetime seja "aware"
    expira_em = datetime.now(timezone.utc) + timedelta(days=DIAS_VALIDADE)
    
    conexao = obter_conexao_banco()
    cursor = conexao.cursor()
    try:
        query = """
            INSERT INTO tokens_lembre_me (usuario_id, token, expira_em) 
            VALUES (%s, %s, %s);
        """
        cursor.execute(query, (usuario_id, token, expira_em))
        conexao.commit()
        
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            expires=expira_em, # O Starlette agora aceitará este valor com UTC
            httponly=True,
            secure=False,
            samesite="lax"
        )
    finally:
        cursor.close()
        conexao.close()

# Configurações do Cookie de Segurança
COOKIE_NAME = "remember_token"
DIAS_VALIDADE = 30

def obter_conexao_banco():
    """
    Função auxiliar. Ajuste os dados de conexão (.env) 
    conforme o padrão que você já usa no resto do projeto.
    """
    import os
    # Pega as variáveis do seu .env. Se não achar, usa os fallbacks informados.
    # ALTERE "sua_senha_aqui" para a senha real do seu MySQL root local (Ex: "root", "1234", etc.)
    senha_banco = os.getenv("DB_PASSWORD", "Pensar2026@root") 
    
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=senha_banco,
        database=os.getenv("DB_NAME", "omrcheck")
    )

from datetime import datetime, timedelta, timezone # <--- Importe o timezone

# ... (restante dos imports)

def gerenciar_lembre_me(response: Response, usuario_id: int):
    token = secrets.token_hex(32)
    # Agora usamos timezone.utc para garantir que o datetime seja "aware"
    expira_em = datetime.now(timezone.utc) + timedelta(days=DIAS_VALIDADE)
    
    conexao = obter_conexao_banco()
    cursor = conexao.cursor()
    try:
        query = """
            INSERT INTO tokens_lembre_me (usuario_id, token, expira_em) 
            VALUES (%s, %s, %s);
        """
        cursor.execute(query, (usuario_id, token, expira_em))
        conexao.commit()
        
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            expires=expira_em, # O Starlette agora aceitará este valor com UTC
            httponly=True,
            secure=False,
            samesite="lax"
        )
    finally:
        cursor.close()
        conexao.close()
        
def verificar_autologin_cookie(request: Request) -> int | None:
    """
    Lê o cookie do navegador, checa no banco de dados se o token
    existe e se ainda está no prazo de validade. Retorna o usuario_id.
    """
    token_cookie = request.cookies.get(COOKIE_NAME)
    if not token_cookie:
        return None
        
    conexao = obter_conexao_banco()
    cursor = conexao.cursor(dictionary=True)
    try:
        query = """
            SELECT usuario_id, expira_em FROM tokens_lembre_me 
            WHERE token = %s;
        """
        cursor.execute(query, (token_cookie,))
        resultado = cursor.fetchone()
        
        if resultado:
            # Se o token venceu, apaga ele
            if datetime.now() > resultado["expira_em"]:
                remover_token_banco(token_cookie)
                return None
            return resultado["usuario_id"]
    finally:
        cursor.close()
        conexao.close()
    return None

def remover_token_banco(token: str):
    """Remove o token do MySQL (usado no logout ou token vencido)"""
    conexao = obter_conexao_banco()
    cursor = conexao.cursor()
    try:
        query = "DELETE FROM tokens_lembre_me WHERE token = %s;"
        cursor.execute(query, (token,))
        conexao.commit()
    finally:
        cursor.close()
        conexao.close()