import os
import json
from datetime import datetime


def validar_questao_com_ia_simulada(dados_questao):
    """
    Validação simulada por IA.

    Esta função ainda NÃO chama Llama/Ollama/API.
    Ela apenas cria uma estrutura padrão para o projeto já ficar preparado.

    Depois vamos substituir a lógica interna pela chamada real da IA.
    """

    pergunta = dados_questao.get("pergunta", "")
    resposta_omr = dados_questao.get("resposta", "")
    status_confianca = dados_questao.get("status", "")
    scores = dados_questao.get("scores", {})

    if not scores:
        return {
            "pergunta": pergunta,
            "resposta_omr": resposta_omr,
            "resposta_ia": "",
            "confianca_ia": "baixa",
            "status_ia": "NAO_AVALIADO",
            "observacao_ia": "Sem scores disponíveis para validação.",
            "validado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    ordenados = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    melhor_alt, melhor_score = ordenados[0]
    segundo_score = ordenados[1][1] if len(ordenados) > 1 else 0
    diferenca = melhor_score - segundo_score

    # Por enquanto, esta é apenas uma simulação conservadora.
    if status_confianca == "EM_BRANCO":
        resposta_ia = ""
        confianca_ia = "media"
        status_ia = "POSSIVEL_EM_BRANCO"
        observacao = "A leitura OMR não identificou marcação. Recomenda-se conferência visual."

    elif status_confianca == "MULTIPLA_MARCACAO":
        resposta_ia = melhor_alt
        confianca_ia = "baixa"
        status_ia = "MULTIPLA_PARA_REVISAR"
        observacao = "Há mais de uma alternativa com score relevante. Conferência manual recomendada."

    elif status_confianca == "DUVIDOSA":
        resposta_ia = melhor_alt

        if diferenca <= 5:
            confianca_ia = "baixa"
            observacao = "A diferença entre as alternativas é pequena. Pode haver falso positivo."
        else:
            confianca_ia = "media"
            observacao = "A IA simulada sugere a alternativa com maior score, mas recomenda revisão."

        status_ia = "SUGESTAO"

    else:
        resposta_ia = resposta_omr
        confianca_ia = "alta"
        status_ia = "CONFIRMA_OMR"
        observacao = "A leitura parece consistente pelos critérios atuais."

    return {
        "pergunta": pergunta,
        "resposta_omr": resposta_omr,
        "resposta_ia": resposta_ia,
        "confianca_ia": confianca_ia,
        "status_ia": status_ia,
        "observacao_ia": observacao,
        "validado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def validar_pendencias_com_ia(leituras_omr):
    """
    Percorre o leituras_omr.json e valida apenas pendências de confiança.

    Retorna uma nova estrutura com os resultados de IA adicionados.
    """

    total_validadas = 0

    for nome_imagem, dados in leituras_omr.items():
        pendencias = dados.get("pendencias_confianca", [])

        validacoes_ia = []

        for pendencia in pendencias:
            resultado_ia = validar_questao_com_ia_simulada(pendencia)
            validacoes_ia.append(resultado_ia)
            total_validadas += 1

        dados["validacoes_ia"] = validacoes_ia
        dados["total_validacoes_ia"] = len(validacoes_ia)

    return leituras_omr, total_validadas


def validar_arquivo_leituras_com_ia(caminho_leituras_omr):
    """
    Abre o leituras_omr.json, aplica validação IA simulada e salva de volta.
    """

    if not os.path.exists(caminho_leituras_omr):
        raise FileNotFoundError(
            f"Arquivo leituras_omr.json não encontrado: {caminho_leituras_omr}"
        )

    with open(caminho_leituras_omr, "r", encoding="utf-8") as f:
        leituras_omr = json.load(f)

    leituras_atualizadas, total_validadas = validar_pendencias_com_ia(
        leituras_omr
    )

    with open(caminho_leituras_omr, "w", encoding="utf-8") as f:
        json.dump(
            leituras_atualizadas,
            f,
            ensure_ascii=False,
            indent=4
        )

    return {
        "arquivo": caminho_leituras_omr,
        "total_validadas": total_validadas
    }