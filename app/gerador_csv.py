import csv
import json

from app.services import caminho_leituras
from app.validacao_cadastral import gerar_validacao_cadastral


TOTAL_PERGUNTAS = 98


def caminho_csv_final(nome_processamento: str):
    caminho_leitura = caminho_leituras(nome_processamento)
    pasta_processamento = caminho_leitura.parent

    return pasta_processamento / "csv_final_keepedu.csv"


def carregar_leituras(nome_processamento: str):
    caminho = caminho_leituras(nome_processamento)

    if not caminho.exists():
        raise FileNotFoundError("Arquivo leituras_omr.json não encontrado.")

    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def montar_cabecalho_keepedu():
    cabecalho = ["Nome do arquivo"]

    cabecalho.append("group001.Pergunta001")
    cabecalho.append("group002.Pergunta002")
    cabecalho.append("group003.Pergunta003")
    cabecalho.append("group004.Pergunta004")
    cabecalho.append("group005.Pergunta005")
    cabecalho.append("group006.Pergunta006")

    cabecalho.append("group006.Código de Barras/QRCode001")

    cabecalho.append("group008.Pergunta007")
    cabecalho.append("group009.Pergunta008")

    for numero in range(9, TOTAL_PERGUNTAS + 1):
        cabecalho.append(f"group010.Pergunta{numero:03d}")

    return cabecalho


def resposta(respostas: dict, numero: int):
    valor = respostas.get(f"Pergunta{numero:03d}", "")

    if valor is None:
        return ""

    valor = str(valor).strip()

    correcoes = {
        "Inglês": "Ingles",
        "inglês": "Ingles",
        "INGLÊS": "Ingles",
        "Espanhol": "Espanhol",
        "espanhol": "Espanhol",
        "ESPANHOL": "Espanhol"
    }

    return correcoes.get(valor, valor)


def gerar_csv_final(nome_processamento: str, forcar: bool = False):
    leituras = carregar_leituras(nome_processamento)
    dados_validacao = gerar_validacao_cadastral(nome_processamento)

    validacoes = dados_validacao["validacoes"]
    pendentes = []

    for nome_imagem, item in validacoes.items():
        if not item.get("codigo_barras_final"):
            pendentes.append({
                "imagem": nome_imagem,
                "motivo": item.get("motivo", "Sem código de barras final.")
            })

    if pendentes and not forcar:
        return {
            "status": "bloqueado",
            "motivo": "Existem cartões sem código de barras final.",
            "pendentes": pendentes
        }

    caminho_saida = caminho_csv_final(nome_processamento)
    cabecalho = montar_cabecalho_keepedu()

    with open(caminho_saida, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(cabecalho)

        for nome_imagem, dados_cartao in leituras.items():
            respostas = dados_cartao.get("respostas", {})
            validacao = validacoes.get(nome_imagem, {})

            arquivo_original = dados_cartao.get("arquivo_original", nome_imagem)
            codigo_barras_final = validacao.get("codigo_barras_final", "") or ""

            linha = [arquivo_original]

            # RA, Pergunta001 até Pergunta006
            for numero in range(1, 7):
                linha.append(resposta(respostas, numero))

            # Código de barras final no padrão KeepEdu:
            # ID_PROVA + A + ID_ALUNO
            linha.append(codigo_barras_final)

            # Idioma e cor da capa
            linha.append(resposta(respostas, 7))
            linha.append(resposta(respostas, 8))

            # Respostas objetivas, Pergunta009 até Pergunta098
            for numero in range(9, TOTAL_PERGUNTAS + 1):
                linha.append(resposta(respostas, numero))

            escritor.writerow(linha)

    return {
        "status": "ok",
        "arquivo": str(caminho_saida),
        "nome_arquivo": caminho_saida.name,
        "gerado_com_pendencias": bool(pendentes),
        "total_pendencias": len(pendentes)
    }
