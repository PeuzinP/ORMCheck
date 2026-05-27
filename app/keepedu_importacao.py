import json
import mimetypes
from pathlib import Path
import re
import unicodedata

import requests

from app.gerador_csv import TOTAL_PERGUNTAS, carregar_leituras, nome_arquivo_keepedu, resposta
from app.services import limpar_pos_importacao_keepedu
from app.services import (
    caminho_leituras,
    localizar_imagem_original,
)
from app.settings import (
    ID_PROVA_KEEPEDU,
    KEEPEDU_API_KEY,
    KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL,
    KEEPEDU_IMPORTAR_RESPOSTAS_URL,
    KEEPEDU_IMPORTAR_TIMEOUT_SECONDS,
    KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL,
    KEEPEDU_INSTITUTE,
)
from app.validacao_cadastral import (
    carregar_validacao_cadastral_salva,
    gerar_validacao_cadastral,
    limpar_pendencia_importacao,
    registrar_pendencia_importacao,
)


def caminho_relatorio_importacao(nome_processamento: str, modo: str = "importacao") -> Path:
    caminho_leitura = caminho_leituras(nome_processamento)
    pasta_processamento = caminho_leitura.parent
    nome_arquivo = "simulacao_keepedu.json" if modo == "simulacao" else "importacao_keepedu.json"
    return pasta_processamento / nome_arquivo


def _texto_limpo(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _montar_respostas_objetivas(dados_cartao: dict) -> list[str]:
    respostas = dados_cartao.get("respostas", {})
    return [resposta(respostas, numero) for numero in range(9, TOTAL_PERGUNTAS + 1)]


def _detectar_id_aval(dados_validacao: dict, id_aval_informado) -> str:
    id_aval = _texto_limpo(id_aval_informado)
    if id_aval:
        return id_aval
    resumo = dados_validacao.get("resumo", {})
    id_aval = _texto_limpo(resumo.get("id_prova_processamento"))
    if id_aval:
        return id_aval
    return _texto_limpo(ID_PROVA_KEEPEDU)


def _cabecalhos_keepedu() -> dict:
    return {
        "ApiKey": KEEPEDU_API_KEY,
        "Institute": KEEPEDU_INSTITUTE,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _cabecalhos_keepedu_upload() -> dict:
    return {
        "ApiKey": KEEPEDU_API_KEY,
        "Institute": KEEPEDU_INSTITUTE,
        "Accept": "application/json",
    }


def _payload_base(id_aval: str) -> dict:
    id_aval_payload = int(id_aval) if id_aval.isdigit() else id_aval
    return {"idAval": id_aval_payload}


def _montar_aluno_payload(
    nome_imagem: str,
    dados_cartao: dict,
    validacao: dict,
    id_aval: str,
    nome_arquivo: str,
    modelo_ia : str,
) -> dict:
    barcode = _texto_limpo(validacao.get("codigo_barras_final"))
    id_aluno = _texto_limpo(validacao.get("id_final"))

    if barcode and "A" in barcode:
        id_aval_barcode = barcode.split("A", 1)[0].strip()
        if id_aval and id_aval_barcode and id_aval_barcode != id_aval:
            raise ValueError(
                f"O barcode do cartão {nome_imagem} usa idAval {id_aval_barcode}, "
                f"mas o envio foi configurado com {id_aval}."
            )

    if not barcode and not id_aluno:
        raise ValueError(f"O cartão {nome_imagem} não possui barcode final nem idAluno final.")

    # >>> ADICIONE O BLOCO EXATAMENTE AQUI DAQUI <<<
    # === CORREÇÃO DA EXTENSÃO ESTRETA .JPG ===
    nome_arquivo_final = nome_arquivo
    
    # Se terminar com .jpeg, substitui por .jpgpayload_aluno
    if nome_arquivo_final.lower().endswith(".jpeg"):
        nome_arquivo_final = re.sub(r"\.jpeg$", ".jpg", nome_arquivo_final, flags=re.IGNORECASE)
    # Se não tiver extensão nenhuma, adiciona o .jpg padrão
    elif not nome_arquivo_final.lower().endswith(".jpg") and not nome_arquivo_final.lower().endswith(".png"):
        nome_arquivo_final = f"{nome_arquivo_final}.jpg"
    # =========================================

    respostas = dados_cartao.get("respostas", {})
    aluno = {
        "nomeArquivo": nome_arquivo_final,  # <--- Mude aqui para usar a variável corrigida!
        "lingua": resposta(respostas, 7),
        "respostas": _montar_respostas_objetivas(dados_cartao),
        "modelo_ia": modelo_ia or "KEEPEDU_AI",
    }

    if barcode:
        aluno["barcode"] = barcode
    else:
        aluno["idAluno"] = id_aluno

    return aluno


def _salvar_relatorio(nome_processamento: str, relatorio: dict, modo: str) -> str:
    caminho_saida = caminho_relatorio_importacao(nome_processamento, modo=modo)
    with open(caminho_saida, "w", encoding="utf-8") as arquivo:
        json.dump(relatorio, arquivo, ensure_ascii=False, indent=4)
    return str(caminho_saida)


def _normalizar_texto_busca(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def _resposta_indica_aluno_fora_avaliacao(corpo_resposta: dict) -> bool:
    texto_resposta = _normalizar_texto_busca(json.dumps(corpo_resposta or {}, ensure_ascii=False))
    padroes = (
        "nao pertence a avaliacao",
        "nao pertence a esta avaliacao",
        "nao esta vinculado a avaliacao",
        "nao esta vinculado nesta avaliacao",
        "nao esta incluido na avaliacao",
        "nao esta incluso na avaliacao",
        "nao participa da avaliacao",
        "aluno nao pertence a avaliacao",
        "aluno nao esta na avaliacao",
        "aluno nao cadastrado na avaliacao",
        "aluno nao localizado na avaliacao",
        "nao encontrado na avaliacao",
    )
    return any(padrao in texto_resposta for padrao in padroes)


def _mensagens_resposta(corpo_resposta: dict) -> list[str]:
    mensagens = []
    for chave in ("mensagem", "arquivoErros"):
        valor = corpo_resposta.get(chave)
        if isinstance(valor, list):
            mensagens.extend(str(item).strip() for item in valor if str(item).strip())
        elif valor:
            mensagens.append(str(valor).strip())
    return mensagens


def _resumir_resposta_http_nao_json(status_code: int, resposta_api: requests.Response, contexto: str) -> str:
    texto = str(resposta_api.text or "").strip()
    texto_compacto = " ".join(texto.split())

    if not texto_compacto:
        return f"{contexto}: HTTP {status_code} sem corpo JSON."
    if "<html" in texto_compacto.lower() or "<!doctype" in texto_compacto.lower():
        return f"{contexto}: HTTP {status_code} retornou HTML em vez de JSON."

    texto_limpo = re.sub(r"<[^>]+>", " ", texto_compacto)
    texto_limpo = " ".join(texto_limpo.split())

    if not texto_limpo:
        return f"{contexto}: HTTP {status_code} sem JSON válido."
    if len(texto_limpo) > 220:
        return f"{texto_limpo[:217]}..."

    return f"{contexto}: HTTP {status_code} - {texto_limpo}"


def _post_keepedu(url_destino: str, payload_envio: dict, cabecalhos: dict) -> tuple[int, dict]:
    resposta_api = requests.post(
        url_destino,
        json=payload_envio,
        headers=cabecalhos,
        timeout=KEEPEDU_IMPORTAR_TIMEOUT_SECONDS,
    )
    status_code = resposta_api.status_code
    try:
        corpo_resposta = resposta_api.json()
    except ValueError:
        corpo_resposta = {
            "success": False,
            "mensagem": [_resumir_resposta_http_nao_json(status_code, resposta_api, "Importação de respostas")],
        }
    return status_code, corpo_resposta


def _post_keepedu_folha_resposta(
    url_destino: str,
    caminho_imagem: Path,
    id_aval,
    cabecalhos: dict,
    nome_arquivo_limpo: str = None  # <--- ADICIONE ESTE PARÂMETRO
) -> tuple[int, dict]:
    content_type = mimetypes.guess_type(caminho_imagem.name)[0] or "application/octet-stream"
    # Se não passarmos o nome limpo, usa o do arquivo físico
    nome_final_envio = nome_arquivo_limpo or caminho_imagem.name 

    with open(caminho_imagem, "rb") as arquivo_imagem:
        resposta_api = requests.post(
            url_destino,
            data={"idAval": str(id_aval)},
            files={
                "imagem_folha_resposta": (
                    nome_final_envio,  # <--- USA O NOME LIMPO SEM 'template_'
                    arquivo_imagem,
                    content_type,
                )
            },
            headers=cabecalhos,
            timeout=KEEPEDU_IMPORTAR_TIMEOUT_SECONDS,
        )
    # ... resto da função permanece igual
    status_code = resposta_api.status_code
    try:
        corpo_resposta = resposta_api.json()
    except ValueError:
        corpo_resposta = {
            "success": 200 <= status_code < 300,
            "mensagem": [_resumir_resposta_http_nao_json(status_code, resposta_api, "Upload da folha-resposta")],
        }
    return status_code, corpo_resposta


def _montar_url_folha_resposta(url_base: str, id_aval) -> str:
    url = str(url_base or "").strip()
    id_aval_texto = str(id_aval).strip()
    if not url or not id_aval_texto:
        return url
    return (
        url.replace("{idAval}", id_aval_texto)
        .replace("{id_aval}", id_aval_texto)
        .replace(":idAval", id_aval_texto)
        .replace(":id_digest", id_aval_texto)
    )


def _sucesso_resposta_generica(status_code: int, corpo_resposta: dict) -> bool:
    if not (200 <= status_code < 300):
        return False
    if isinstance(corpo_resposta, dict) and "success" in corpo_resposta:
        return bool(corpo_resposta.get("success"))
    return True


def _motivo_pendencia_avaliacao(corpo_resposta: dict, nome_arquivo: str) -> str:
    mensagens = _mensagens_resposta(corpo_resposta)
    if mensagens:
        return " | ".join(mensagens[:3])
    return f"O aluno do cartão {nome_arquivo} não pertence à avaliação informada."


def _emitir_progresso_importacao(
    progresso_callback,
    percentual: int,
    mensagem: str,
    arquivo_atual: str = "",
    resultado: dict | None = None,
    tipo: str | None = None,
    titulo: str | None = None,
    descricao: str = "",
):
    if not progresso_callback:
        return
    progresso_callback(
        percentual,
        mensagem,
        arquivo_atual=arquivo_atual,
        resultado=resultado,
        tipo=tipo,
        titulo=titulo,
        descricao=descricao,
    )


def _selecionar_itens_importacao(leituras: dict, validacoes: dict, id_aluno=None) -> tuple[list[tuple[str, dict, dict]], str]:
    id_aluno_filtrado = _texto_limpo(id_aluno)
    itens = []
    for nome_imagem, dados_cartao in leituras.items():
        validacao = validacoes.get(nome_imagem, {})
        id_final = _texto_limpo(validacao.get("id_final"))
        if id_aluno_filtrado and id_final != id_aluno_filtrado:
            continue
        itens.append((nome_imagem, dados_cartao, validacao))
    return itens, id_aluno_filtrado


def contar_alunos_importacao(nome_processamento: str, id_aluno=None) -> int:
    leituras = carregar_leituras(nome_processamento)
    dados_validacao = carregar_validacao_cadastral_salva(nome_processamento)
    if not dados_validacao:
        dados_validacao = gerar_validacao_cadastral(nome_processamento)
    validacoes = dados_validacao.get("validacoes", {})
    itens, _ = _selecionar_itens_importacao(leituras, validacoes, id_aluno=id_aluno)
    return len(itens)


def processar_mock_importacao_keepedu(dados: dict) -> tuple[int, dict]:
    if not isinstance(dados, dict):
        return 400, {"success": False, "mensagem": ["Corpo inválido."], "arquivoErros": []}
    alunos = dados.get("alunos", [])
    return 200, {
        "success": True,
        "idAval": dados.get("idAval"),
        "total": len(alunos),
        "importadas": len(alunos),
        "erros": 0,
        "mensagem": ["Sucesso textual."],
        "arquivoErros": []
    }


def _executar_importacao_respostas_presenciais(
    nome_processamento: str,
    url_destino: str,
    modo: str,
    id_aval=None,
    dia_aval=None,
    usuario_id=None,
    id_aluno=None,
    progresso_callback=None,
    modelo_ia=None,
):
    if not url_destino:
        return {"status": "erro", "mensagem": "URL não configurada no .env."}
    if not KEEPEDU_API_KEY or not KEEPEDU_INSTITUTE:
        return {"status": "erro", "mensagem": "Credenciais da KeepEdu ausentes no .env."}

    leituras = carregar_leituras(nome_processamento)
    dados_validacao = carregar_validacao_cadastral_salva(nome_processamento) or gerar_validacao_cadastral(nome_processamento)

    validacoes = dados_validacao.get("validacoes", {})
    itens_envio, id_aluno_filtrado = _selecionar_itens_importacao(leituras, validacoes, id_aluno=id_aluno)
    total_itens = len(itens_envio)

    id_aval_final = _detectar_id_aval(dados_validacao, id_aval)
    if not id_aval_final:
        return {"status": "erro", "mensagem": "Informe o ID da avaliação."}

    cabecalhos = _cabecalhos_keepedu()
    payload_base = _payload_base(id_aval_final)
    detalhes = []
    total, importadas = 0, 0
    mensagens, arquivos_erros, pendencias_avaliacao = [], [], []
    validacao_atualizada = False

    _emitir_progresso_importacao(
        progresso_callback,
        percentual=5,
        mensagem="Preparando envio de VETORES (JSON)...",
        resultado={"modo": modo, "id_aluno": id_aluno_filtrado},
        tipo="info",
        titulo="Envio de Vetores iniciado",
    )

    for indice, (nome_imagem, dados_cartao, validacao) in enumerate(itens_envio, start=1):
        total += 1
        try:
            nome_arquivo = _obter_nome_original_limpo(nome_imagem, dados_cartao)
            aluno = _montar_aluno_payload(nome_imagem, dados_cartao, validacao, id_aval_final, nome_arquivo, modelo_ia)
            
            payload_envio = {**payload_base, "alunos": [aluno]}

            # SEPARAÇÃO AQUI: Envia estritamente os dados textuais (Passo 1)
            if modo == "simulacao":
                status_code, corpo_resposta = processar_mock_importacao_keepedu(payload_envio)
            else:
                status_code, corpo_resposta = _post_keepedu(url_destino, payload_envio, cabecalhos)

            sucesso = (200 <= status_code < 300) and bool(corpo_resposta.get("success"))
            fora_avaliacao = _whitespace_indica = _resposta_indica_aluno_fora_avaliacao(corpo_resposta)

            if fora_avaliacao:
                motivo_pendencia = _motivo_pendencia_avaliacao(corpo_resposta, nome_arquivo)
                registrar_pendencia_importacao(
                    nome_processamento=nome_processamento,
                    nome_imagem=nome_imagem,
                    status_validacao="PENDENTE_ALUNO_FORA_AVALIACAO",
                    motivo=motivo_pendencia,
                    detalhes={"idAval": id_aval_final, "resposta": corpo_resposta, "modelo_ia": modelo_ia},
                )
                validacao_atualizada = True
                pendencias_avaliacao.append({"imagem": nome_imagem, "nomeArquivo": nome_arquivo, "motivo": motivo_pendencia})
            elif sucesso and limpar_pendencia_importacao(nome_processamento, nome_imagem):
                validacao_atualizada = True

            detalhe = {
                "imagem": nome_imagem,
                "nomeArquivo": nome_arquivo,
                "barcode": aluno.get("barcode", ""),
                "idAluno": aluno.get("idAluno", ""),
                "payload": payload_envio,
                "status_code": status_code,
                "resposta": corpo_resposta,
                "sucesso": sucesso,
                "pendencia_avaliacao": fora_avaliacao,
                "modelo_ia": modelo_ia,
            }
            detalhes.append(detalhe)

            if sucesso:
                importadas += 1

        except Exception as exc:
            mensagens.append(f"Erro ao processar {nome_imagem}: {exc}")

    erros = total - importadas
    status = "ok" if erros == 0 else "parcial"

    relatorio = {
        "status": status,
        "success": status == "ok",
        "modo": modo,
        "url_destino": url_destino,
        "idAval": id_aval_final,
        "total": total,
        "importadas": importadas,
        "erros": erros,
        "mensagem": mensagens,
        "arquivoErros": arquivos_erros,
        "pendencias_avaliacao": pendencias_avaliacao,
        "validacao_atualizada": validacao_atualizada,
        "detalhes": detalhes,
    }
    
    _emitir_progresso_importacao(
        progresso_callback,
        percentual=100,
        mensagem=f"Envio de vetores concluído: {importadas}/{total} com sucesso.",
        resultado=relatorio,
        tipo="success" if status == "ok" else "warning",
    )
    relatorio["arquivo_relatorio"] = _salvar_relatorio(nome_processamento, relatorio, modo=modo)
    
    return relatorio

def _obter_nome_original_limpo(nome_imagem: str, dados_cartao: dict) -> str:
    """
    Garante o retorno do nome do arquivo original limpo,
    removendo 'template_' e forçando a extensão estrita para .jpg
    """
    if not isinstance(dados_cartao, dict):
        dados_cartao = {}
        
    nome_base = dados_cartao.get("arquivo_original") or dados_cartao.get("nome_arquivo")
    
    if not nome_base:
        nome_base = re.sub(r"^template_", "", nome_imagem, flags=re.IGNORECASE)
        
    # FORÇA A EXTENSÃO .JPG
    if nome_base.lower().endswith(".jpeg"):
        nome_base = re.sub(r"\.jpeg$", ".jpg", nome_base, flags=re.IGNORECASE)
        
    return nome_base


def _executar_importacao_respostas_presenciais(
    nome_processamento: str,
    url_destino: str,
    modo: str,
    id_aval=None,
    dia_aval=None,
    usuario_id=None,
    id_aluno=None,
    progresso_callback=None,
    modelo_ia=None,
):
    if not url_destino:
        return {"status": "erro", "mensagem": "URL não configurada no .env."}
    if not KEEPEDU_API_KEY or not KEEPEDU_INSTITUTE:
        return {"status": "erro", "mensagem": "Credenciais da KeepEdu ausentes no .env."}

    leituras = carregar_leituras(nome_processamento)
    dados_validacao = carregar_validacao_cadastral_salva(nome_processamento) or gerar_validacao_cadastral(nome_processamento)

    validacoes = dados_validacao.get("validacoes", {})
    itens_envio, id_aluno_filtrado = _selecionar_itens_importacao(leituras, validacoes, id_aluno=id_aluno)
    total_itens = len(itens_envio)

    id_aval_final = _detectar_id_aval(dados_validacao, id_aval)
    if not id_aval_final:
        return {"status": "erro", "mensagem": "Informe o ID da avaliação."}

    cabecalhos = _cabecalhos_keepedu()
    payload_base = _payload_base(id_aval_final)
    detalhes = []
    total, importadas = 0, 0
    mensagens, arquivos_erros, pendencias_avaliacao = [], [], []
    validacao_atualizada = False

    _emitir_progresso_importacao(
        progresso_callback,
        percentual=5,
        mensagem="Preparando envio de VETORES (JSON)...",
        resultado={"modo": modo, "id_aluno": id_aluno_filtrado},
        tipo="info",
        titulo="Envio de Vetores iniciado",
    )

    for indice, (nome_imagem, dados_cartao, validacao) in enumerate(itens_envio, start=1):
        total += 1
        try:
            # CORREÇÃO AQUI: Garante que o payload textual receba o nome limpo do arquivo, sem 'template_'
            nome_original_real = _obter_nome_original_limpo(nome_imagem, dados_cartao)
            nome_arquivo = nome_arquivo_keepedu(nome_original_real)
            
            aluno = _montar_aluno_payload(nome_imagem, dados_cartao, validacao, id_aval_final, nome_arquivo, modelo_ia)
            payload_envio = {**payload_base, "alunos": [aluno]}

            if modo == "simulacao":
                status_code, corpo_resposta = processar_mock_importacao_keepedu(payload_envio)
            else:
                status_code, corpo_resposta = _post_keepedu(url_destino, payload_envio, cabecalhos)

            sucesso = _sucesso_resposta_generica(status_code, corpo_resposta)
            fora_avaliacao = _resposta_indica_aluno_fora_avaliacao(corpo_resposta)

            if fora_avaliacao:
                motivo_pendencia = _motivo_pendencia_avaliacao(corpo_resposta, nome_arquivo)
                registrar_pendencia_importacao(
                    nome_processamento=nome_processamento,
                    nome_imagem=nome_imagem,
                    status_validacao="PENDENTE_ALUNO_FORA_AVALIACAO",
                    motivo=motivo_pendencia,
                    detalhes={"idAval": id_aval_final, "resposta": corpo_resposta},
                )
                validacao_atualizada = True
                pendencias_avaliacao.append({"imagem": nome_imagem, "nomeArquivo": nome_arquivo, "motivo": motivo_pendencia})
            elif sucesso and limpar_pendencia_importacao(nome_processamento, nome_imagem):
                validacao_atualizada = True

            detalhes.append({
                "imagem": nome_imagem,
                "nomeArquivo": nome_arquivo,
                "barcode": aluno.get("barcode", ""),
                "idAluno": aluno.get("idAluno", ""),
                "payload": payload_envio,
                "status_code": status_code,
                "resposta": corpo_resposta,
                "sucesso": sucesso,
                "pendencia_avaliacao": fora_avaliacao,
                "modelo_ia": modelo_ia,
            })

            if sucesso:
                importadas += 1

        except Exception as exc:
            mensagens.append(f"Erro ao processar {nome_imagem}: {exc}")

    erros = total - importadas
    status = "ok" if erros == 0 else "parcial"

    relatorio = {
        "status": status,
        "success": status == "ok",
        "modo": modo,
        "url_destino": url_destino,
        "idAval": id_aval_final,
        "total": total,
        "importadas": importadas,
        "erros": erros,
        "mensagem": mensagens,
        "arquivoErros": arquivos_erros,
        "pendencias_avaliacao": pendencias_avaliacao,
        "validacao_atualizada": validacao_atualizada,
        "detalhes": detalhes,
        "modelo_ia": modelo_ia,
    }
    
    _emitir_progresso_importacao(
        progresso_callback,
        percentual=100,
        mensagem=f"Envio de vetores concluído: {importadas}/{total} com sucesso.",
        resultado=relatorio,
        tipo="success" if status == "ok" else "warning",
    )
    relatorio["arquivo_relatorio"] = _salvar_relatorio(nome_processamento, relatorio, modo=modo)
    return relatorio


# Função de Upload Binário Corrigida para injetar o Form-Data sem o prefixo do OMR
def importar_imagens_folha_resposta(nome_processamento: str, id_aval=None, progresso_callback=None):
    if not KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL:
        return {"status": "erro", "mensagem": "URL de envio de imagem não configurada no .env."}

    leituras = carregar_leituras(nome_processamento)
    dados_validacao = carregar_validacao_cadastral_salva(nome_processamento) or gerar_validacao_cadastral(nome_processamento)
    id_aval_final = _detectar_id_aval(dados_validacao, id_aval)

    cabecalhos_upload = _cabecalhos_keepedu_upload()
    url_folha_resposta = _montar_url_folha_resposta(KEEPEDU_IMPORTAR_FOLHA_RESPOSTA_URL, id_aval_final)
    
    total, importadas, erros = 0, 0, 0
    mensagens = []
    imagens_enviadas_com_sucesso = []

    _emitir_progresso_importacao(progresso_callback, percentual=5, mensagem="Iniciando upload das imagens originais...", tipo="info")

    # Descobre o caminho base da pasta do processamento atual (ex: .../processamento_20260526_084451)
    caminho_leitura = caminho_leituras(nome_processamento)
    pasta_processamento = caminho_leitura.parent
    
    # FORÇA O CAMINHO EXATO PARA A PASTA 'originais'
    pasta_originais = pasta_processamento / "originais"

    for indice, nome_imagem in enumerate(leituras.keys(), start=1):
        total += 1
        
        # Formata o nome como a KeepEdu quer (ex: "CARMEM LÚCIA.jpg")
        nome_original_real = _obter_nome_original_limpo(nome_imagem, leituras.get(nome_imagem, {}))
        nome_arquivo_formatado = nome_arquivo_keepedu(nome_original_real)

        # Monta as possibilidades de arquivo físico direto dentro da pasta 'originais'
        # Remove o 'template_' e testa as extensões reais que podem estar no seu HD
        nome_sem_prefixo = re.sub(r"^template_", "", nome_imagem, flags=re.IGNORECASE)
        
        caminho_imagem_original = pasta_originais / nome_sem_prefixo
        
        # Fallbacks inteligentes caso a extensão física no HD seja diferente da chave do OMR
        if not caminho_imagem_original.exists():
            nome_puro = re.sub(r"\.(jpeg|jpg|png)$", "", nome_sem_prefixo, flags=re.IGNORECASE)
            opcao_jpg = pasta_originais / f"{nome_puro}.jpg"
            opcao_jpeg = pasta_originais / f"{nome_puro}.jpeg"
            
            if opcao_jpg.exists():
                caminho_imagem_original = opcao_jpg
            elif opcao_jpeg.exists():
                caminho_imagem_original = opcao_jpeg

        # Se encontrou o arquivo físico dentro da pasta 'originais', faz o upload
        if caminho_imagem_original and caminho_imagem_original.exists():
            status_code, corpo_resposta = _post_keepedu_folha_resposta(
                url_folha_resposta, 
                caminho_imagem_original, 
                id_aval_final, 
                cabecalhos_upload,
                nome_arquivo_limpo=nome_arquivo_formatado  # Envia para a API mascarado como .jpg
            )
            
            if 200 <= status_code < 300:
                importadas += 1
                imagens_enviadas_com_sucesso.append(nome_original_real)
            else:
                erros += 1
                mensagens.append(f"Erro na imagem {nome_arquivo_formatado}: HTTP {status_code}")
        else:
            erros += 1
            mensagens.append(f"Arquivo físico original não localizado em {pasta_originais} para: {nome_arquivo_formatado}")
    
    if imagens_enviadas_com_sucesso:
        limpar_pos_importacao_keepedu(nome_processamento, imagens_enviadas=imagens_enviadas_com_sucesso)
    return {"status": "ok" if erros == 0 else "parcial", "total": total, "importadas": importadas, "erros": erros, "mensagem": mensagens}


def importar_respostas_presenciais(nome_processamento: str, id_aval=None, dia_aval=None, usuario_id=None, id_aluno=None, progresso_callback=None):
    return _executar_importacao_respostas_presenciais(
        nome_processamento=nome_processamento, url_destino=KEEPEDU_IMPORTAR_RESPOSTAS_URL, modo="importacao",
        id_aval=id_aval, dia_aval=dia_aval, usuario_id=usuario_id, id_aluno=id_aluno, progresso_callback=progresso_callback,
    )


def simular_importacao_respostas_presenciais(nome_processamento: str, id_aval=None, dia_aval=None, usuario_id=None, id_aluno=None, progresso_callback=None):
    return _executar_importacao_respostas_presenciais(
        nome_processamento=nome_processamento, url_destino=KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL, modo="simulacao",
        id_aval=id_aval, dia_aval=dia_aval, usuario_id=usuario_id, id_aluno=id_aluno, progresso_callback=progresso_callback,
    )