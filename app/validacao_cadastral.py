import json

from app.alunos_client import buscar_aluno_por_ra
from app.services import caminho_leituras

def caminho_validacao_manual(nome_avaliacao: str):
    caminho_leitura = caminho_leituras(nome_avaliacao)
    pasta_processamento = caminho_leitura.parent

    return pasta_processamento / "validacao_manual.json"


def carregar_validacao_manual(nome_avaliacao: str):
    caminho = caminho_validacao_manual(nome_avaliacao)

    if not caminho.exists():
        return {}

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def caminho_pendencias_importacao(nome_avaliacao: str):
    caminho_leitura = caminho_leituras(nome_avaliacao)
    pasta_processamento = caminho_leitura.parent
    return pasta_processamento / "pendencias_importacao.json"


def carregar_pendencias_importacao(nome_avaliacao: str):
    caminho = caminho_pendencias_importacao(nome_avaliacao)

    if not caminho.exists():
        return {}

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_pendencias_importacao(nome_avaliacao: str, dados: dict):
    caminho = caminho_pendencias_importacao(nome_avaliacao)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

    return caminho


def registrar_pendencia_importacao(
    nome_avaliacao: str,
    nome_imagem: str,
    status_validacao: str,
    motivo: str,
    detalhes: dict | None = None,
):
    dados = carregar_pendencias_importacao(nome_avaliacao)
    dados[nome_imagem] = {
        "status_validacao": status_validacao,
        "motivo": str(motivo or "").strip(),
        "detalhes": detalhes or {},
    }
    salvar_pendencias_importacao(nome_avaliacao, dados)
    return dados[nome_imagem]


def limpar_pendencia_importacao(nome_avaliacao: str, nome_imagem: str):
    dados = carregar_pendencias_importacao(nome_avaliacao)

    if nome_imagem in dados:
        dados.pop(nome_imagem, None)
        salvar_pendencias_importacao(nome_avaliacao, dados)
        return True

    return False


def salvar_correcao_manual(
    nome_avaliacao: str = "",
    nome_imagem: str = "",
    valor_manual: str = "",
    nome_processamento: str | None = None,
):
    if nome_processamento and not nome_avaliacao:
        nome_avaliacao = nome_processamento

    valor_manual = str(valor_manual or "").strip()

    if not valor_manual:
        raise ValueError("Informe o ID do aluno ou o código completo.")

    leituras = carregar_leituras(nome_avaliacao)

    dados_cartao = leituras.get(nome_imagem)

    if not dados_cartao:
        for item in leituras.values():
            if item.get("arquivo_original") == nome_imagem:
                dados_cartao = item
                break

    if not dados_cartao:
        raise ValueError(f"Cartão não encontrado na avaliação: {nome_imagem}")

    codigo_barras_detectado = extrair_codigo_barras_possivel(dados_cartao)
    id_prova_detectado, _ = quebrar_codigo_barras(codigo_barras_detectado)

    # Caso 1: usuário digitou o código completo, exemplo 12479A29684
    if "A" in valor_manual:
        id_prova, id_aluno = quebrar_codigo_barras(valor_manual)

        if not id_prova or not id_aluno:
            raise ValueError(
                "Código de barras inválido. Use o formato IDPROVAAIDALUNO. Exemplo: 12479A29684"
            )

        codigo_barras_final = valor_manual
        id_final = id_aluno

    # Caso 2: usuário digitou só o ID do aluno
    else:
        id_final = valor_manual

        # Se o cartão já trouxe apenas o ID da prova, exemplo 12479, usa ele.
        if codigo_barras_detectado and codigo_barras_detectado.isdigit():
            id_prova = codigo_barras_detectado

        # Se por algum motivo o código veio completo, usa a parte antes do A.
        elif id_prova_detectado:
            id_prova = id_prova_detectado

        else:
            raise ValueError(
                "Não foi possível identificar o ID da prova para este cartão. "
                "Informe o código completo no formato 12479A29684."
            )

        codigo_barras_final = f"{id_prova}A{id_final}"

    caminho = caminho_validacao_manual(nome_avaliacao)
    dados = carregar_validacao_manual(nome_avaliacao)

    dados[nome_imagem] = {
        "id_final": id_final,
        "codigo_barras_final": codigo_barras_final,
        "origem_id": "VALIDACAO_MANUAL",
        "status_validacao": "VALIDADO_MANUAL",
        "motivo": "ID informado manualmente na Validação Cadastral."
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

    limpar_pendencia_importacao(nome_avaliacao, nome_imagem)
    return dados[nome_imagem]

def carregar_leituras(nome_avaliacao: str):
    caminho = caminho_leituras(nome_avaliacao)

    if not caminho.exists():
        return {}

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_validacao(nome_avaliacao: str, dados_validacao: dict):
    caminho_leitura = caminho_leituras(nome_avaliacao)
    pasta_processamento = caminho_leitura.parent
    caminho_saida = pasta_processamento / "validacao_cadastral.json"
    pasta_processamento.mkdir(parents=True, exist_ok=True)

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(dados_validacao, f, ensure_ascii=False, indent=4)

    return caminho_saida


def caminho_validacao_cadastral(nome_avaliacao: str):
    caminho_leitura = caminho_leituras(nome_avaliacao)
    pasta_processamento = caminho_leitura.parent
    return pasta_processamento / "validacao_cadastral.json"


def carregar_validacao_cadastral_salva(nome_avaliacao: str):
    caminho = caminho_validacao_cadastral(nome_avaliacao)

    if not caminho.exists():
        return None

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def caminho_validacao_manual(nome_avaliacao: str):
    caminho_leitura = caminho_leituras(nome_avaliacao)
    pasta_processamento = caminho_leitura.parent

    return pasta_processamento / "validacao_manual.json"


def carregar_validacao_manual(nome_avaliacao: str):
    caminho = caminho_validacao_manual(nome_avaliacao)

    if not caminho.exists():
        return {}

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_correcao_manual(
    nome_avaliacao: str = "",
    nome_imagem: str = "",
    valor_manual: str = "",
    nome_processamento: str | None = None,
):
    if nome_processamento and not nome_avaliacao:
        nome_avaliacao = nome_processamento

    valor_manual = str(valor_manual or "").strip()

    if not valor_manual:
        raise ValueError("Informe o ID do aluno ou o código completo.")

    leituras = carregar_leituras(nome_avaliacao)
    id_prova_processamento = detectar_id_prova_do_processamento(leituras)

    if "A" in valor_manual:
        id_prova, id_aluno = quebrar_codigo_barras(valor_manual)

        if not id_prova or not id_aluno:
            raise ValueError(
                "Código de barras inválido. Use o formato IDPROVAAIDALUNO. Exemplo: 12347A38121"
            )

        codigo_barras_final = valor_manual
        id_final = id_aluno

    else:
        id_final = valor_manual

        if not id_prova_processamento:
            raise ValueError(
                "Não foi possível identificar o ID da prova na avaliação. "
                "Informe o código completo no formato 12347A38121."
            )

        codigo_barras_final = f"{id_prova_processamento}A{id_final}"

    caminho = caminho_validacao_manual(nome_avaliacao)
    dados = carregar_validacao_manual(nome_avaliacao)

    dados[nome_imagem] = {
        "id_final": id_final,
        "codigo_barras_final": codigo_barras_final,
        "origem_id": "VALIDACAO_MANUAL",
        "status_validacao": "VALIDADO_MANUAL",
        "motivo": "ID informado manualmente na Validação Cadastral."
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

    limpar_pendencia_importacao(nome_avaliacao, nome_imagem)
    return dados[nome_imagem]

def extrair_codigo_barras_possivel(dados_cartao: dict):
    possiveis_campos = [
        "codigo_barras",
        "codigo_de_barras",
        "barcode",
        "qrcode",
        "codigo_barras_qrcode",
        "Código de Barras/QRCode001"
    ]

    for campo in possiveis_campos:
        valor = dados_cartao.get(campo)

        if valor:
            return str(valor).strip()

    return ""


def quebrar_codigo_barras(codigo_barras: str):
    """
    Formato esperado:
    ID_PROVA + A + ID_ALUNO

    Exemplo:
    12345A38121
    """

    codigo_barras = str(codigo_barras or "").strip()

    if "A" not in codigo_barras:
        return "", ""

    partes = codigo_barras.split("A", 1)

    id_prova = partes[0].strip()
    id_aluno = partes[1].strip()

    return id_prova, id_aluno


def extrair_ra_possivel(dados_cartao: dict):
    """
    Tenta recuperar o RA lido no cartão.

    Primeiro procura campos diretos.
    Se não encontrar, monta o RA pelas Perguntas001 a 006,
    que correspondem aos dígitos do Registro Acadêmico.
    """

    possiveis_campos = [
        "registro_academico",
        "ra",
        "RA",
        "codigo_ra",
        "id_aluno_ra"
    ]

    for campo in possiveis_campos:
        valor = dados_cartao.get(campo)

        if valor:
            ra = "".join(ch for ch in str(valor).strip() if ch.isdigit())

            if len(ra) >= 5 and ra != "000000":
                return ra

    respostas = dados_cartao.get("respostas", {})

    if isinstance(respostas, dict):
        digitos = []

        for numero in range(1, 7):
            chave = f"Pergunta{numero:03d}"
            valor = respostas.get(chave, "")

            valor = str(valor or "").strip()

            if valor.isdigit():
                digitos.append(valor)
            else:
                digitos.append("")

        ra_montado = "".join(digitos).strip()

        if len(ra_montado) >= 5 and ra_montado != "000000":
            return ra_montado

    return ""


def extrair_nome_possivel(dados_cartao: dict):
    possiveis_campos = [
        "nome",
        "nome_aluno",
        "aluno",
        "nome_completo"
    ]

    for campo in possiveis_campos:
        valor = dados_cartao.get(campo)

        if valor:
            return str(valor).strip()

    return ""


def detectar_id_prova_do_processamento(leituras: dict):
    """
    Procura em qualquer cartão processado um código de barras válido
    para descobrir o ID da prova daquela avaliação.
    """

    for dados_cartao in leituras.values():
        codigo_barras = extrair_codigo_barras_possivel(dados_cartao)
        id_prova, _ = quebrar_codigo_barras(codigo_barras)

        if id_prova:
            return id_prova

    return ""


def _aplicar_pendencia_importacao(resultado: dict, pendencia_importacao: dict | None):
    if not pendencia_importacao:
        return resultado

    status_validacao = str(pendencia_importacao.get("status_validacao") or "").strip()
    motivo = str(pendencia_importacao.get("motivo") or "").strip()

    if not status_validacao and not motivo:
        return resultado

    if status_validacao:
        resultado["status_validacao"] = status_validacao

    if motivo:
        resultado["motivo"] = motivo

    resultado["pendencia_importacao"] = pendencia_importacao
    resultado["precisa_validacao_manual"] = True
    return resultado


def validar_cartao(
    nome_imagem: str,
    dados_cartao: dict,
    id_prova_avaliacao: str,
    validacoes_manuais: dict,
    pendencias_importacao: dict,
):
    codigo_barras_detectado = extrair_codigo_barras_possivel(dados_cartao)
    id_prova_detectado, id_aluno_detectado = quebrar_codigo_barras(codigo_barras_detectado)

    ra_detectado = extrair_ra_possivel(dados_cartao)
    nome_detectado = extrair_nome_possivel(dados_cartao)

    resultado = {
        "imagem": nome_imagem,
        "arquivo_original": dados_cartao.get("arquivo_original", nome_imagem),

        "codigo_barras_detectado": codigo_barras_detectado,
        "id_prova_detectado": id_prova_detectado,
        "id_aluno_detectado": id_aluno_detectado,

        "ra_detectado": ra_detectado,
        "nome_detectado": nome_detectado,

        "id_final": "",
        "codigo_barras_final": "",
        "origem_id": "",

        "status_validacao": "",
        "motivo": "",
        "aluno_api": None,
        "pendencia_importacao": None,
        "precisa_validacao_manual": False
    }

    manual = validacoes_manuais.get(nome_imagem)
    pendencia_importacao = pendencias_importacao.get(nome_imagem)

    if not manual:
        arquivo_original = dados_cartao.get("arquivo_original", "")
        manual = validacoes_manuais.get(arquivo_original)
        if not pendencia_importacao:
            pendencia_importacao = pendencias_importacao.get(arquivo_original)

    if manual:
        resultado["id_final"] = manual.get("id_final", "")
        resultado["codigo_barras_final"] = manual.get("codigo_barras_final", "")
        resultado["origem_id"] = "VALIDACAO_MANUAL"
        resultado["status_validacao"] = "VALIDADO_MANUAL"
        resultado["motivo"] = manual.get("motivo", "ID informado manualmente.")
        resultado["precisa_validacao_manual"] = False
        return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

    if not manual:
        arquivo_original = dados_cartao.get("arquivo_original", "")
        manual = validacoes_manuais.get(arquivo_original)

    if manual:
        resultado["id_final"] = manual.get("id_final", "")
        resultado["codigo_barras_final"] = manual.get("codigo_barras_final", "")
        resultado["origem_id"] = "VALIDACAO_MANUAL"
        resultado["status_validacao"] = "VALIDADO_MANUAL"
        resultado["motivo"] = manual.get("motivo", "ID informado manualmente.")
        resultado["precisa_validacao_manual"] = False
        return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

    # 1. Se o cartão já tem código de barras válido, ele é a fonte principal.
    if codigo_barras_detectado and id_prova_detectado and id_aluno_detectado:
        resultado["id_final"] = id_aluno_detectado
        resultado["codigo_barras_final"] = codigo_barras_detectado
        resultado["origem_id"] = "CODIGO_BARRAS_CARTAO"
        resultado["status_validacao"] = "VALIDADO_CODIGO_BARRAS"
        resultado["motivo"] = "Código de barras lido diretamente do cartão."
        resultado["precisa_validacao_manual"] = False
        return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

    # 2. Se não tem código de barras, mas tem RA, busca o ID do aluno pela API.
    if ra_detectado:
        aluno = buscar_aluno_por_ra(ra_detectado)

        if aluno.get("encontrado") and aluno.get("id"):
            id_final = str(aluno.get("id"))

            if not id_prova_avaliacao:
                resultado["id_final"] = id_final
                resultado["origem_id"] = "API_RA"
                resultado["status_validacao"] = "PENDENTE_SEM_ID_PROVA"
                resultado["motivo"] = (
                    "ID do aluno localizado pela API, mas não foi possível identificar "
                    "o ID da prova em nenhum código de barras do processamento."
                )
                resultado["aluno_api"] = aluno
                resultado["precisa_validacao_manual"] = True
                return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

            resultado["id_final"] = id_final
            resultado["codigo_barras_final"] = f"{id_prova_avaliacao}A{id_final}"
            resultado["origem_id"] = "API_RA"
            resultado["status_validacao"] = "VALIDADO_API_RA"
            resultado["motivo"] = "ID do aluno localizado pela API a partir do RA e código final montado com o ID da prova detectado."
            resultado["aluno_api"] = aluno
            resultado["precisa_validacao_manual"] = False
            return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

        resultado["status_validacao"] = "PENDENTE_RA_NAO_ENCONTRADO"
        resultado["motivo"] = aluno.get("motivo", "RA informado, mas ID não foi localizado pela API.")
        resultado["aluno_api"] = aluno
        resultado["precisa_validacao_manual"] = True
        return _aplicar_pendencia_importacao(resultado, pendencia_importacao)

    # 3. Sem código de barras e sem RA.
    resultado["status_validacao"] = "PENDENTE_SEM_IDENTIFICACAO"
    resultado["motivo"] = "Cartão sem código de barras válido e sem RA preenchido."
    resultado["precisa_validacao_manual"] = True

    return _aplicar_pendencia_importacao(resultado, pendencia_importacao)


def gerar_validacao_cadastral(nome_avaliacao: str):
    leituras = carregar_leituras(nome_avaliacao)

    id_prova_avaliacao = detectar_id_prova_do_processamento(leituras)
    validacoes_manuais = carregar_validacao_manual(nome_avaliacao)
    pendencias_importacao = carregar_pendencias_importacao(nome_avaliacao)

    validacoes = {}
    resumo = {
        "total": 0,
        "validados": 0,
        "pendentes": 0,
        "com_codigo_barras": 0,
        "com_id_api": 0,
        "sem_identificacao": 0,
        "sem_id_prova": 0,
        "fora_avaliacao": 0,
        "id_prova_processamento": id_prova_avaliacao
    }

    for nome_imagem, dados_cartao in leituras.items():
        validacao = validar_cartao(
        nome_imagem,
        dados_cartao,
        id_prova_avaliacao,
        validacoes_manuais,
        pendencias_importacao
    )

        validacoes[nome_imagem] = validacao
        resumo["total"] += 1

        if validacao["precisa_validacao_manual"]:
            resumo["pendentes"] += 1
        else:
            resumo["validados"] += 1

        if validacao["status_validacao"] == "VALIDADO_CODIGO_BARRAS":
            resumo["com_codigo_barras"] += 1

        if validacao["status_validacao"] == "VALIDADO_API_RA":
            resumo["com_id_api"] += 1

        if validacao["status_validacao"] == "PENDENTE_SEM_IDENTIFICACAO":
            resumo["sem_identificacao"] += 1

        if validacao["status_validacao"] == "PENDENTE_SEM_ID_PROVA":
            resumo["sem_id_prova"] += 1

        if validacao["status_validacao"] == "PENDENTE_ALUNO_FORA_AVALIACAO":
            resumo["fora_avaliacao"] += 1

    dados_saida = {
        "nome_avaliacao": nome_avaliacao,
        "resumo": resumo,
        "validacoes": validacoes
    }

    salvar_validacao(nome_avaliacao, dados_saida)

    return dados_saida
