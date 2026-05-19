import os
import cv2
import csv
import json
import re
import glob
import shutil
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET

from app.time_utils import agora_local

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
except Exception:
    pyzbar_decode = None


EXTENSOES_IMAGEM = [".jpg", ".jpeg", ".png"]


def listar_imagens(pasta_imagens):
    imagens = []

    for arquivo in os.listdir(pasta_imagens):
        if arquivo.lower().endswith(tuple(EXTENSOES_IMAGEM)):
            imagens.append(arquivo)

    return sorted(imagens)


def ler_imagem(caminho_imagem):
    """
    Le imagem com suporte a caminhos com acento no Windows.
    """
    dados = np.fromfile(caminho_imagem, dtype=np.uint8)
    imagem = cv2.imdecode(dados, cv2.IMREAD_COLOR)
    return imagem


def salvar_imagem(caminho_saida, imagem):
    """
    Salva imagem com suporte a caminhos com acento no Windows.
    """
    extensao = os.path.splitext(caminho_saida)[1]
    sucesso, buffer = cv2.imencode(extensao, imagem)

    if sucesso:
        buffer.tofile(caminho_saida)
        return True

    return False


def salvar_debug_falha_leitura(caminho_imagem, pasta_debug, mensagem="Falha na leitura"):
    os.makedirs(pasta_debug, exist_ok=True)

    nome_base = os.path.basename(caminho_imagem)
    caminho_saida = os.path.join(pasta_debug, "template_" + nome_base)
    imagem = ler_imagem(caminho_imagem)

    if imagem is None:
        return caminho_saida

    debug = imagem.copy()
    altura, largura = debug.shape[:2]
    faixa_altura = min(120, max(76, altura // 8))

    overlay = debug.copy()
    cv2.rectangle(
        overlay,
        (0, 0),
        (largura, faixa_altura),
        (255, 245, 245),
        -1
    )
    cv2.addWeighted(overlay, 0.88, debug, 0.12, 0, debug)

    cv2.putText(
        debug,
        "CORRECAO MANUAL NECESSARIA",
        (22, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (25, 25, 180),
        2
    )

    texto = str(mensagem or "Falha na leitura")
    if len(texto) > 70:
        texto = texto[:67] + "..."

    cv2.putText(
        debug,
        texto,
        (22, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (60, 60, 60),
        2
    )

    cv2.rectangle(
        debug,
        (8, 8),
        (largura - 8, altura - 8),
        (0, 0, 255),
        2
    )

    salvar_imagem(caminho_saida, debug)
    return caminho_saida


def registrar_imagem_para_correcao_manual(
    leituras_omr,
    pasta_debug,
    pasta_manual,
    pasta_pendencias,
    caminho_imagem,
    caminho_original_processamento,
    imagem,
    respostas=None,
    erros=None,
    pontos_mapeados=None,
    pontos_cantos=None,
    origem_cantos="AUTO",
    registro_academico="",
    codigo_barras="",
    debug_bolhas="",
    debug_cantos="",
    confianca_questoes=None,
    pendencias_confianca=None,
    total_pendencias_confianca=0
):
    respostas = respostas or {}
    erros = erros or []
    pontos_mapeados = pontos_mapeados or {}
    pontos_cantos = pontos_cantos or []
    confianca_questoes = confianca_questoes or {}
    pendencias_confianca = pendencias_confianca or []

    nome_debug = "template_" + os.path.basename(caminho_imagem)

    if not debug_bolhas:
        debug_bolhas = salvar_debug_falha_leitura(
            caminho_imagem,
            pasta_debug,
            "Falha na leitura"
        )

    if not debug_cantos:
        caminho_debug_cantos = os.path.join(
            pasta_debug,
            "cantos_" + os.path.basename(caminho_imagem)
        )
        debug_cantos = caminho_debug_cantos if os.path.exists(caminho_debug_cantos) else ""

    leituras_omr[nome_debug] = {
        "arquivo_original": os.path.basename(caminho_imagem),
        "caminho_original_processamento": caminho_original_processamento,
        "respostas": respostas,
        "pontos_mapeados": pontos_mapeados,
        "pontos_cantos": pontos_cantos,
        "origem_cantos": origem_cantos,
        "registro_academico": registro_academico,
        "codigo_barras": codigo_barras,
        "debug_bolhas": debug_bolhas,
        "debug_cantos": debug_cantos,
        "erros": erros,
        "confianca_questoes": confianca_questoes,
        "pendencias_confianca": pendencias_confianca,
        "total_pendencias_confianca": total_pendencias_confianca
    }

    nome_sem_extensao = os.path.splitext(imagem)[0]
    caminho_imagem_pendencia = os.path.join(pasta_pendencias, imagem)

    try:
        shutil.copy2(caminho_imagem, caminho_imagem_pendencia)
    except Exception:
        caminho_imagem_pendencia = caminho_imagem

    caminho_json_manual = os.path.join(
        pasta_manual,
        nome_sem_extensao + ".json"
    )

    dados_manual = {
        "arquivo": imagem,
        "caminho_imagem": caminho_imagem,
        "caminho_imagem_pendencia": caminho_imagem_pendencia,
        "registro_academico": registro_academico,
        "codigo_barras": codigo_barras,
        "respostas": respostas,
        "erros": erros,
        "pontos_mapeados": pontos_mapeados,
        "corrigido_manualmente": origem_cantos == "MANUAL"
    }

    with open(caminho_json_manual, "w", encoding="utf-8") as f:
        json.dump(dados_manual, f, ensure_ascii=False, indent=4)

    return {
        "nome_debug": nome_debug,
        "debug_bolhas": debug_bolhas,
        "debug_cantos": debug_cantos,
        "caminho_json_manual": caminho_json_manual
    }


def carregar_modelo_xtmpl_completo(caminho_modelo):
    """
    Lê o modelo .xtmpl completo do FormScanner.

    Mantém:
    - corners principais do cartão
    - perguntas Pergunta001, Pergunta002, etc.
    - áreas, como Código de Barras/QRCode001
    """

    tree = ET.parse(caminho_modelo)
    root = tree.getroot()

    modelo = {
        "corners": {},
        "questions": {},
        "areas": {}
    }

    # 1. Cantos principais do template
    # IMPORTANTE: usar somente ./corners, e não .//corners,
    # para não pegar os cantos da área do código de barras.
    corners_node = root.find("./corners")

    if corners_node is None:
        raise ValueError("Nenhum bloco principal <corners> encontrado no .xtmpl.")

    for corner in corners_node.findall("corner"):
        position = corner.attrib.get("position")
        point = corner.find("point")

        if not position or point is None:
            continue

        x = float(point.attrib.get("x", 0))
        y = float(point.attrib.get("y", 0))

        modelo["corners"][position] = (x, y)

    # 2. Perguntas
    fields_node = root.find("./fields")

    if fields_node is None:
        raise ValueError("Nenhum bloco <fields> encontrado no .xtmpl.")

    for group in fields_node.findall("group"):
        group_name = group.attrib.get("name", "")

        for question in group.findall("question"):
            nome_pergunta = question.attrib.get("question", "").strip()
            tipo = question.attrib.get("type", "").strip()
            multiple = question.attrib.get("multiple", "false").strip()

            if not nome_pergunta:
                continue

            values_node = question.find("values")

            if values_node is None:
                continue

            values = {}

            for value in values_node.findall("value"):
                resposta = (
                    value.attrib.get("response")
                    or value.attrib.get("value")
                    or value.attrib.get("name")
                    or ""
                ).strip()

                point = value.find("point")

                if not resposta or point is None:
                    continue

                x = float(point.attrib.get("x", 0))
                y = float(point.attrib.get("y", 0))

                values[resposta] = (x, y)

            if values:
                modelo["questions"][nome_pergunta] = {
                    "group": group_name,
                    "type": tipo,
                    "multiple": multiple,
                    "values": values
                }

        # 3. Áreas, como código de barras
        for area in group.findall("area"):
            nome_area = area.attrib.get("name", "").strip()
            tipo_area = area.attrib.get("type", "").strip()

            if not nome_area:
                continue

            pontos = {}

            area_corners_node = area.find("corners")

            if area_corners_node is not None:
                for corner in area_corners_node.findall("corner"):
                    position = corner.attrib.get("position")
                    point = corner.find("point")

                    if not position or point is None:
                        continue

                    x = float(point.attrib.get("x", 0))
                    y = float(point.attrib.get("y", 0))

                    pontos[position] = (x, y)

            modelo["areas"][nome_area] = {
                "type": tipo_area,
                "points": pontos
            }

    return modelo


def ordenar_cantos_template(corners):
    """
    Retorna os cantos na ordem:
    TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT.
    """
    obrigatorios = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]

    for item in obrigatorios:
        if item not in corners:
            raise ValueError(f"Canto {item} nao encontrado no template .xtmpl.")

    return np.array([
        corners["TOP_LEFT"],
        corners["TOP_RIGHT"],
        corners["BOTTOM_LEFT"],
        corners["BOTTOM_RIGHT"]
    ], dtype=np.float32)


def detectar_cantos_na_imagem(imagem):
    """
    Detecta os quatro marcadores pretos da folha na imagem escaneada.

    Retorna:
    pontos_imagem, debug

    Ordem:
    TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT.
    """
    debug = imagem.copy()
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(
        cinza,
        90,
        255,
        cv2.THRESH_BINARY_INV
    )

    kernel = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contornos, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    h_img, w_img = cinza.shape[:2]
    area_total = h_img * w_img

    candidatos = []

    for cnt in contornos:
        area = cv2.contourArea(cnt)

        if area < area_total * 0.00035:
            continue

        if area > area_total * 0.06:
            continue

        x, y, w, h = cv2.boundingRect(cnt)

        if h == 0:
            continue

        proporcao = w / float(h)

        if not (0.40 <= proporcao <= 2.50):
            continue

        cx = x + w / 2
        cy = y + h / 2

        esta_em_canto = (
            (cx < w_img * 0.35 and cy < h_img * 0.35) or
            (cx > w_img * 0.65 and cy < h_img * 0.35) or
            (cx < w_img * 0.35 and cy > h_img * 0.65) or
            (cx > w_img * 0.65 and cy > h_img * 0.65)
        )

        if not esta_em_canto:
            continue

        candidatos.append({
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "cx": cx,
            "cy": cy,
            "area": area
        })

    if len(candidatos) < 4:
        cv2.putText(
            debug,
            "FALHA AO DETECTAR 4 CANTOS",
            (50, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            3
        )

        return None, debug

    sup_esq = min(candidatos, key=lambda p: p["cx"] + p["cy"])
    sup_dir = min(candidatos, key=lambda p: (w_img - p["cx"]) + p["cy"])
    inf_esq = min(candidatos, key=lambda p: p["cx"] + (h_img - p["cy"]))
    inf_dir = min(candidatos, key=lambda p: (w_img - p["cx"]) + (h_img - p["cy"]))

    # Usa os cantos externos dos marcadores, nao o centro.
    pontos_imagem = np.array([
        [sup_esq["x"], sup_esq["y"]],
        [sup_dir["x"] + sup_dir["w"], sup_dir["y"]],
        [inf_esq["x"], inf_esq["y"] + inf_esq["h"]],
        [inf_dir["x"] + inf_dir["w"], inf_dir["y"] + inf_dir["h"]],
    ], dtype=np.float32)

    for item in [sup_esq, sup_dir, inf_esq, inf_dir]:
        cv2.rectangle(
            debug,
            (int(item["x"]), int(item["y"])),
            (int(item["x"] + item["w"]), int(item["y"] + item["h"])),
            (0, 255, 0),
            4
        )

        cv2.circle(
            debug,
            (int(item["cx"]), int(item["cy"])),
            12,
            (0, 0, 255),
            -1
        )

    cv2.putText(
        debug,
        "CANTOS DETECTADOS",
        (50, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        3
    )

    return pontos_imagem, debug


def desenhar_cantos_na_imagem(imagem, pontos, titulo="CANTOS AJUSTADOS MANUALMENTE"):
    debug = imagem.copy()

    if pontos is None:
        cv2.putText(
            debug,
            "CANTOS NAO INFORMADOS",
            (50, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            3
        )
        return debug

    pontos = np.array(pontos, dtype=np.float32)
    rotulos = ["SE", "SD", "IE", "ID"]

    for indice, (x, y) in enumerate(pontos):
        cv2.circle(
            debug,
            (int(x), int(y)),
            14,
            (0, 255, 255),
            -1
        )
        cv2.circle(
            debug,
            (int(x), int(y)),
            20,
            (0, 0, 255),
            3
        )
        cv2.putText(
            debug,
            rotulos[indice],
            (int(x) + 8, int(y) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )

    cv2.polylines(
        debug,
        [np.array([
            pontos[0],
            pontos[1],
            pontos[3],
            pontos[2]
        ], dtype=np.int32)],
        isClosed=True,
        color=(0, 255, 0),
        thickness=3
    )

    cv2.putText(
        debug,
        titulo,
        (50, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        3
    )

    return debug


def caminho_modelo_omr_padrao():
    pasta_projeto = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(
        pasta_projeto,
        "templates",
        "modelo_cartao.xtmpl"
    )


def transformar_ponto(matriz, x, y):
    """
    Aplica homografia em um ponto do template para encontrar sua posicao na imagem.
    """
    ponto = np.array([[[x, y]]], dtype=np.float32)
    transformado = cv2.perspectiveTransform(ponto, matriz)

    return float(transformado[0][0][0]), float(transformado[0][0][1])

def ordenar_perguntas_formscanner(questions):
    """
    Ordena Pergunta001, Pergunta002, Pergunta003...
    """
    def chave(item):
        nome = item[0]

        try:
            return int(nome.replace("Pergunta", ""))
        except Exception:
            return 99999

    return dict(sorted(questions.items(), key=chave))


def analisar_bolha_por_ponto(imagem_cinza, x, y, raio=10):
    """
    Analisa uma bolha considerando:
    - percentual de área escura;
    - maior componente escuro conectado;
    - escurecimento médio.

    Esta foi a versão mais equilibrada antes das tentativas com núcleo,
    anel, patches e limite global.
    """

    altura, largura = imagem_cinza.shape[:2]

    x = int(round(x))
    y = int(round(y))

    raio_leitura = max(8, int(raio * 0.95))

    x1 = max(0, x - raio_leitura)
    x2 = min(largura, x + raio_leitura)
    y1 = max(0, y - raio_leitura)
    y2 = min(altura, y + raio_leitura)

    recorte = imagem_cinza[y1:y2, x1:x2]

    if recorte.size == 0:
        return {
            "score": 0,
            "percentual_escuro": 0,
            "maior_componente": 0,
            "percentual_componente": 0,
            "escurecimento_medio": 0,
            "percentual_nucleo_escuro": 0,
            "percentual_anel_escuro": 0
        }

    recorte = cv2.GaussianBlur(recorte, (3, 3), 0)

    h, w = recorte.shape[:2]
    cx = w // 2
    cy = h // 2

    yy, xx = np.ogrid[:h, :w]

    dist2 = ((xx - cx) ** 2 + (yy - cy) ** 2)
    mascara = dist2 <= raio_leitura ** 2
    raio_nucleo = max(4, int(raio_leitura * 0.55))
    mascara_nucleo = dist2 <= raio_nucleo ** 2
    mascara_anel = mascara & (~mascara_nucleo)

    pixels = recorte[mascara]

    if pixels.size == 0:
        return {
            "score": 0,
            "percentual_escuro": 0,
            "maior_componente": 0,
            "percentual_componente": 0,
            "escurecimento_medio": 0
        }

    binaria = np.zeros_like(recorte, dtype=np.uint8)
    binaria[(recorte < 100) & mascara] = 255  # Reduzido de 105 para ser mais criterioso com o que é "preto"

    # Remove traços finos da impressão antes de unir a massa real do preenchimento.
    kernel = np.ones((2, 2), np.uint8)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, kernel)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binaria,
        connectivity=8
    )

    area_mascara = np.count_nonzero(mascara)

    maior_componente = 0

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]

        if area > maior_componente:
            maior_componente = area

    percentual_escuro = (
        np.count_nonzero(binaria[mascara]) / area_mascara
    ) * 100 if area_mascara else 0

    area_nucleo = np.count_nonzero(mascara_nucleo)
    percentual_nucleo_escuro = (
        np.count_nonzero(binaria[mascara_nucleo]) / area_nucleo
    ) * 100 if area_nucleo else 0

    area_anel = np.count_nonzero(mascara_anel)
    percentual_anel_escuro = (
        np.count_nonzero(binaria[mascara_anel]) / area_anel
    ) * 100 if area_anel else 0

    percentual_componente = (
        maior_componente / area_mascara
    ) * 100 if area_mascara else 0

    escurecimento_medio = 255 - np.mean(pixels)

    score = (
        percentual_escuro * 0.45
        + percentual_componente * 0.35
        + escurecimento_medio * 0.20
    )

    return {
        "score": float(score),
        "percentual_escuro": float(percentual_escuro),
        "maior_componente": float(maior_componente),
        "percentual_componente": float(percentual_componente),
        "escurecimento_medio": float(escurecimento_medio),
        "percentual_nucleo_escuro": float(percentual_nucleo_escuro),
        "percentual_anel_escuro": float(percentual_anel_escuro)
    }

def analisar_question_por_template(question_data, cinza, matriz, raio=10):
    values = question_data["values"]
    analises = {}

    for resposta, ponto in values.items():
        x_template, y_template = ponto
        x_img, y_img = transformar_ponto(matriz, x_template, y_template)

        analises[resposta] = analisar_bolha_por_ponto(
            cinza,
            x_img,
            y_img,
            raio=raio
        )

    return analises

def estimar_compensacao_por_alternativa(analises_por_pergunta):
    """
    Calcula uma compensação leve por alternativa para neutralizar
    o viés da impressão do próprio gabarito.

    Ex.: se a letra B impressa gera score base maior que as demais,
    o excesso é subtraído apenas na comparação entre alternativas.
    """
    scores_por_alternativa = {}

    for analises in analises_por_pergunta.values():
        for alternativa, dados in analises.items():
            scores_por_alternativa.setdefault(alternativa, []).append(
                float(dados.get("score", 0))
            )

    if not scores_por_alternativa:
        return {}

    baseline_por_alternativa = {}

    for alternativa, valores in scores_por_alternativa.items():
        if not valores:
            baseline_por_alternativa[alternativa] = 0.0
            continue

        valores_array = np.array(valores, dtype=np.float32)
        percentile = 30 if len(valores_array) >= 10 else 50
        baseline_por_alternativa[alternativa] = float(
            np.percentile(valores_array, percentile)
        )

    baseline_referencia = min(baseline_por_alternativa.values()) if baseline_por_alternativa else 0.0

    compensacao = {}

    for alternativa, baseline in baseline_por_alternativa.items():
        excesso = max(0.0, baseline - baseline_referencia)
        compensacao[alternativa] = min(excesso, 12.0)

    # Algumas letras impressas podem herdar viés estrutural em certos cartões.
    # A compensação extra precisa ser pequena para não inviabilizar marcações reais.
    if "A" in compensacao and compensacao["A"] > 0:
        compensacao["A"] = min(compensacao["A"] + 1.5, 13.0)

    if "B" in compensacao and compensacao["B"] > 0:
        compensacao["B"] = min(compensacao["B"] + 2.5, 14.0)

    return compensacao
    
def calcular_limite_global_marcacao(todos_scores):
    """
    Calcula um limite dinâmico para o cartão inteiro.

    A ideia é separar automaticamente:
    - bolhas vazias/letras impressas
    - bolhas realmente preenchidas
    """

    valores = np.array(
        [s for s in todos_scores if s is not None and s > 0],
        dtype=np.float32
    )

    if len(valores) < 20:
        return 999

    # Remove extremos absurdos
    p10 = np.percentile(valores, 10)
    p90 = np.percentile(valores, 90)

    valores_filtrados = valores[
        (valores >= p10) & (valores <= p90)
    ]

    if len(valores_filtrados) < 20:
        valores_filtrados = valores

    # K-means simples com 2 grupos: vazio x marcado
    centro_baixo = np.percentile(valores_filtrados, 35)
    centro_alto = np.percentile(valores_filtrados, 90)

    for _ in range(20):
        dist_baixo = np.abs(valores - centro_baixo)
        dist_alto = np.abs(valores - centro_alto)

        grupo_baixo = valores[dist_baixo <= dist_alto]
        grupo_alto = valores[dist_baixo > dist_alto]

        if len(grupo_baixo) == 0 or len(grupo_alto) == 0:
            break

        novo_baixo = np.mean(grupo_baixo)
        novo_alto = np.mean(grupo_alto)

        if abs(novo_baixo - centro_baixo) < 0.1 and abs(novo_alto - centro_alto) < 0.1:
            break

        centro_baixo = novo_baixo
        centro_alto = novo_alto

    separacao = centro_alto - centro_baixo

    # Se não há separação real, considera que o cartão está muito duvidoso
    if separacao < 8:
        return 999

    limite = centro_baixo + (separacao * 0.65)

    # Piso de segurança para não aceitar letra impressa
    limite = max(limite, 28)

    return float(limite)

def decidir_resposta_por_limite_global(analises, limite_global=None):
    """
    Decide a resposta de forma conservadora.

    Se não tiver marcação muito clara, deixa em branco.
    """

    scores = {
        alt: dados["score"]
        for alt, dados in analises.items()
    }

    ordenados = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    if not ordenados:
        return "", scores, "sem coordenadas"

    melhor_alt, melhor_score = ordenados[0]
    segundo_score = ordenados[1][1] if len(ordenados) > 1 else 0

    melhor = analises[melhor_alt]

    outros = [
        score for alt, score in scores.items()
        if alt != melhor_alt
    ]

    media_outros = sum(outros) / len(outros) if outros else 0

    diferenca_segundo = melhor_score - segundo_score
    diferenca_media = melhor_score - media_outros

    # Regras mais conservadoras para evitar falsos positivos
    percentual_preto_minimo = 34  # Aumentado de 25 para evitar falsos positivos
    maior_componente_minimo = 38  # Aumentado de 28
    score_minimo = 35  # Aumentado de 28

    diferenca_segundo_minima = 12  # Aumentado de 8
    diferenca_media_minima = 15  # Aumentado de 10

    tem_preenchimento_real = (
        melhor["percentual_preto"] >= percentual_preto_minimo
        and melhor["maior_componente"] >= maior_componente_minimo
        and melhor["score"] >= score_minimo
    )

    tem_destaque = (
        diferenca_segundo >= diferenca_segundo_minima
        and diferenca_media >= diferenca_media_minima
    )

    if tem_preenchimento_real and tem_destaque:
        return melhor_alt, scores, ""

    return "", scores, "vazia ou ilegivel"

def ler_question_por_template(question_data, cinza, matriz, raio=10, analises=None, compensacao_por_alternativa=None):
    """
    Lê uma pergunta comparando as alternativas da própria questão.

    Essa versão é conservadora, mas não usa núcleo, anel ou limite global.
    """
    if analises is None:
        analises = analisar_question_por_template(
            question_data,
            cinza,
            matriz,
            raio=raio
        )

    compensacao_por_alternativa = compensacao_por_alternativa or {}

    scores = {}

    for resposta, analise in analises.items():
        score_bruto = float(analise.get("score", 0))
        compensacao = float(compensacao_por_alternativa.get(resposta, 0))
        scores[resposta] = max(0.0, score_bruto - compensacao)

    if not scores:
        return "", scores, "sem coordenadas"

    ordenados = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    melhor_resposta, melhor_score = ordenados[0]
    segundo_score = ordenados[1][1] if len(ordenados) > 1 else 0

    melhor = analises[melhor_resposta]
    melhor_score_bruto = float(melhor.get("score", 0))

    outros_scores = [
        valor for alt, valor in scores.items()
        if alt != melhor_resposta
    ]

    media_outros = sum(outros_scores) / len(outros_scores) if outros_scores else 0

    diferenca_segundo = melhor_score - segundo_score
    diferenca_media = melhor_score - media_outros

    score_minimo = 35  # Aumentado de 28 para evitar falsos positivos
    percentual_escuro_minimo = 22  # Aumentado de 18
    maior_componente_minimo = 32  # Aumentado de 25
    percentual_componente_minimo = 9  # Aumentado de 7

    diferenca_minima_segundo = 14  # Aumentado de 10
    diferenca_minima_media = 16  # Aumentado de 12

    # A alternativa A também pode herdar viés do impresso, mas em grau menor que B.
    if melhor_resposta == "A":
        score_minimo += 2
        percentual_escuro_minimo += 1
        maior_componente_minimo += 2
        percentual_componente_minimo += 1
        diferenca_minima_segundo += 2
        diferenca_minima_media += 2

    # A alternativa B tem mostrado viés estrutural mais forte no impresso.
    # Para reduzir falso positivo, ela precisa de evidência um pouco mais forte.
    if melhor_resposta == "B":
        score_minimo += 3
        percentual_escuro_minimo += 2
        maior_componente_minimo += 4
        percentual_componente_minimo += 1
        diferenca_minima_segundo += 4
        diferenca_minima_media += 4

    percentual_anel = float(melhor.get("percentual_anel_escuro", 0))
    percentual_nucleo = float(melhor.get("percentual_nucleo_escuro", 0))

    massa_real = (
        melhor_score_bruto >= score_minimo
        and melhor["percentual_escuro"] >= percentual_escuro_minimo
        and melhor["maior_componente"] >= maior_componente_minimo
        and melhor["percentual_componente"] >= percentual_componente_minimo
    )

    destaque_real = (
        diferenca_segundo >= diferenca_minima_segundo
        and diferenca_media >= diferenca_minima_media
    )

    dispersao_real = True

    if melhor_resposta == "A":
        # O "A" impresso às vezes concentra mais massa no núcleo do círculo.
        # Exige alguma presença fora do miolo para reduzir falso positivo.
        dispersao_real = (
            percentual_anel >= 5.0
            and percentual_anel >= (percentual_nucleo * 0.16)
        )

    if melhor_resposta == "B":
        # O "B" impresso costuma concentrar escurecimento no miolo.
        # Exigimos alguma massa também fora do núcleo para reduzir falsos positivos.
        dispersao_real = (
            percentual_anel >= 6.5
            and percentual_anel >= (percentual_nucleo * 0.22)
        )

    if massa_real and destaque_real and dispersao_real:
        return melhor_resposta, scores, ""

    return "", scores, "vazia ou ilegivel"


def desenhar_debug_pergunta(debug, question_data, matriz, resposta_detectada, raio=10):
    """
    Desenha os pontos do template na imagem original.
    """
    values = question_data["values"]

    for resposta, ponto in values.items():
        x_template, y_template = ponto
        x_img, y_img = transformar_ponto(matriz, x_template, y_template)

        x = int(round(x_img))
        y = int(round(y_img))

        if resposta == resposta_detectada and resposta_detectada:
            cor = (0, 255, 0)
        else:
            cor = (0, 0, 255)

        # Desenha uma marca mais limpa, sem halo branco, para manter
        # verde/vermelho evidentes e mais proximos da leitura impressa.
        cv2.circle(debug, (x, y), raio, cor, 2)
        cv2.circle(debug, (x, y), max(3, raio // 2), (18, 18, 18), -1)


def montar_ra(respostas):
    """
    Monta RA usando Pergunta001 a Pergunta006.
    """
    partes = []

    for i in range(1, 7):
        chave = f"Pergunta{i:03d}"
        partes.append(str(respostas.get(chave, "")))

    return "".join(partes)

def ler_codigo_barras_por_template(imagem, modelo, matriz, pasta_debug=None, nome_base=""):
    """
    Tenta ler o Código de Barras/QRCode001 usando a área definida no .xtmpl.
    Retorna o texto lido, por exemplo: 12479A10425.
    Também salva um debug do recorte do código de barras.
    """

    areas = modelo.get("areas", {})

    nome_area = None

    for nome in areas.keys():
        nome_limpo = nome.lower()

        if (
            "qrcode" in nome_limpo
            or "qr" in nome_limpo
            or "barras" in nome_limpo
            or "barcode" in nome_limpo
            or "codigo" in nome_limpo
            or "código" in nome_limpo
        ):
            nome_area = nome
            break

    if not nome_area:
        return ""

    pontos_area = areas[nome_area].get("points", {})

    obrigatorios = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"]

    for item in obrigatorios:
        if item not in pontos_area:
            return ""

    pontos_template = np.array([
        pontos_area["TOP_LEFT"],
        pontos_area["TOP_RIGHT"],
        pontos_area["BOTTOM_LEFT"],
        pontos_area["BOTTOM_RIGHT"]
    ], dtype=np.float32)

    pontos_imagem = cv2.perspectiveTransform(
        pontos_template.reshape(-1, 1, 2),
        matriz
    ).reshape(-1, 2)

    xs = pontos_imagem[:, 0]
    ys = pontos_imagem[:, 1]

    # Margem aumentada para melhor captura do código de barras
    margem_x = 80  # Aumentado de 60 para 80
    margem_y = 50  # Aumentado de 35 para 50

    x1 = int(max(0, min(xs) - margem_x))
    y1 = int(max(0, min(ys) - margem_y))
    x2 = int(min(imagem.shape[1], max(xs) + margem_x))
    y2 = int(min(imagem.shape[0], max(ys) + margem_y))

    recorte = imagem[y1:y2, x1:x2]

    if recorte.size == 0:
        return ""

    if pasta_debug:
        os.makedirs(pasta_debug, exist_ok=True)

        caminho_debug_codigo = os.path.join(
            pasta_debug,
            "codigo_barras_" + nome_base
        )

        salvar_imagem(caminho_debug_codigo, recorte)

    # Aumenta bastante o recorte
    recorte_ampliado = cv2.resize(
        recorte,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )

    cinza = cv2.cvtColor(recorte_ampliado, cv2.COLOR_BGR2GRAY)

    # Variações para tentar melhorar a decodificação
    tentativas = []

    tentativas.append(recorte_ampliado)

    _, otsu = cv2.threshold(
        cinza,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    tentativas.append(cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))

    adaptativa = cv2.adaptiveThreshold(
        cinza,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        5
    )

    tentativas.append(cv2.cvtColor(adaptativa, cv2.COLOR_GRAY2BGR))

    # 1. Tenta com pyzbar
    if pyzbar_decode is not None:
        for img_teste in tentativas:
            try:
                resultados = pyzbar_decode(img_teste)

                for r in resultados:
                    texto = r.data.decode("utf-8", errors="ignore").strip()

                    if texto:
                        return texto
            except Exception:
                pass

    # 2. Tenta com OpenCV BarcodeDetector
    if hasattr(cv2, "barcode"):
        try:
            detector = cv2.barcode.BarcodeDetector()

            for img_teste in tentativas:
                resultado = detector.detectAndDecode(img_teste)

                textos = []

                if isinstance(resultado, tuple):
                    for item in resultado:
                        if isinstance(item, str) and item.strip():
                            textos.append(item.strip())

                        elif isinstance(item, (list, tuple)):
                            for subitem in item:
                                if isinstance(subitem, str) and subitem.strip():
                                    textos.append(subitem.strip())

                elif isinstance(resultado, str) and resultado.strip():
                    textos.append(resultado.strip())

                for texto in textos:
                    if texto:
                        return texto

        except Exception:
            pass

    return ""

def extrair_numero_pergunta(nome_pergunta):
    match = re.search(r"(\d+)$", str(nome_pergunta))

    if not match:
        return None

    return int(match.group(1))


def classificar_confianca_questao(pergunta, question_data, resposta, scores, erro):
    """
    Camada de auditoria da leitura OMR.

    Esta função NÃO altera a resposta lida.
    Ela apenas classifica a questão para facilitar a conferência manual.
    """

    grupo = str((question_data or {}).get("group", "")).strip().lower()
    eh_questao_objetiva = grupo == "group010"

    if not eh_questao_objetiva:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "CAMPO_AUXILIAR",
            "pendencia": False,
            "motivo": "Campo auxiliar fora do group010 do CSV.",
            "group": grupo,
            "scores": scores or {}
        }

    if not scores:
        return {
            "pergunta": pergunta,
            "resposta": "",
            "status": "SEM_COORDENADAS",
            "pendencia": True,
            "motivo": "Não foi possível obter scores da questão.",
            "group": grupo,
            "melhor_alternativa": "",
            "melhor_score": 0,
            "segunda_alternativa": "",
            "segundo_score": 0,
            "diferenca": 0,
            "scores": {}
        }

    ordenados = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    melhor_alt, melhor_score = ordenados[0]
    segunda_alt, segundo_score = ordenados[1] if len(ordenados) > 1 else ("", 0)

    diferenca = melhor_score - segundo_score

    # Limites apenas para auditoria, não mudam a leitura principal.
    LIMITE_RESPOSTA_FORTE = 30
    LIMITE_RESPOSTA_FRACA = 18
    DIFERENCA_SEGURA = 10
    DIFERENCA_DUVIDOSA = 7

    alternativas_fortes = [
        alt for alt, score in scores.items()
        if score >= LIMITE_RESPOSTA_FORTE
    ]

    if not resposta:
        return {
            "pergunta": pergunta,
            "resposta": "",
            "status": "EM_BRANCO",
            "pendencia": True,
            "motivo": "A leitura principal não identificou alternativa marcada.",
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    if len(alternativas_fortes) >= 2:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "MULTIPLA_MARCACAO",
            "pendencia": True,
            "motivo": "Duas ou mais alternativas tiveram score alto.",
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    if melhor_score < LIMITE_RESPOSTA_FRACA:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "DUVIDOSA",
            "pendencia": True,
            "motivo": "Resposta lida com score baixo. Possível falso positivo.",
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    if diferenca <= DIFERENCA_DUVIDOSA:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "DUVIDOSA",
            "pendencia": True,
            "motivo": "A melhor alternativa ficou próxima da segunda.",
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    if erro:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "DUVIDOSA",
            "pendencia": True,
            "motivo": str(erro),
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    if melhor_score >= LIMITE_RESPOSTA_FORTE and diferenca >= DIFERENCA_SEGURA:
        return {
            "pergunta": pergunta,
            "resposta": resposta,
            "status": "CONFIAVEL",
            "pendencia": False,
            "motivo": "Leitura considerada segura.",
            "group": grupo,
            "melhor_alternativa": melhor_alt,
            "melhor_score": float(melhor_score),
            "segunda_alternativa": segunda_alt,
            "segundo_score": float(segundo_score),
            "diferenca": float(diferenca),
            "scores": scores
        }

    return {
        "pergunta": pergunta,
        "resposta": resposta,
        "status": "DUVIDOSA",
        "pendencia": True,
        "motivo": "Leitura intermediária. Recomendada conferência manual.",
        "group": grupo,
        "melhor_alternativa": melhor_alt,
        "melhor_score": float(melhor_score),
        "segunda_alternativa": segunda_alt,
        "segundo_score": float(segundo_score),
        "diferenca": float(diferenca),
        "scores": scores
    }

def detectar_respostas_por_template(
    caminho_imagem,
    caminho_modelo,
    pasta_debug,
    pontos_imagem_override=None
):
    """
    Le o cartao usando o .xtmpl completo, no padrao FormScanner:
    - Pergunta001 a Pergunta006 = RA
    - Pergunta007 = idioma
    - Pergunta008 = cor da capa
    - Pergunta009 em diante = respostas
    """
    os.makedirs(pasta_debug, exist_ok=True)

    modelo = carregar_modelo_xtmpl_completo(caminho_modelo)
    perguntas = ordenar_perguntas_formscanner(modelo["questions"])

    if not perguntas:
        raise ValueError("Nenhuma pergunta encontrada no modelo .xtmpl.")

    imagem = ler_imagem(caminho_imagem)

    if imagem is None:
        return None, "Nao foi possivel abrir a imagem"

    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    debug = imagem.copy()

    pontos_template = ordenar_cantos_template(modelo["corners"])

    if pontos_imagem_override is not None:
        pontos_imagem = np.array(pontos_imagem_override, dtype=np.float32)
        debug_cantos = desenhar_cantos_na_imagem(imagem, pontos_imagem)
        detalhe_cantos = "Leitura por template com cantos ajustados manualmente"
    else:
        pontos_imagem, debug_cantos = detectar_cantos_na_imagem(imagem)
        detalhe_cantos = "Leitura por template completo concluida"

    nome_base = os.path.basename(caminho_imagem)

    caminho_debug_cantos = os.path.join(
        pasta_debug,
        "cantos_" + nome_base
    )

    salvar_imagem(caminho_debug_cantos, debug_cantos)

    if pontos_imagem is None:
        return None, "Nao foi possivel detectar os cantos na imagem."

    matriz = cv2.getPerspectiveTransform(
        pontos_template,
        pontos_imagem
    )

    codigo_barras = ler_codigo_barras_por_template(
        imagem,
        modelo,
        matriz,
        pasta_debug=pasta_debug,
        nome_base=nome_base
    )

    respostas = {}
    erros = []
    pontos_mapeados = {}
    confianca_questoes = {}
    pendencias_confianca = []
    analises_por_pergunta = {}

    for pergunta, question_data in perguntas.items():
        pontos_mapeados[pergunta] = {}

        for alternativa, ponto in question_data["values"].items():
            x_template, y_template = ponto
            x_img, y_img = transformar_ponto(matriz, x_template, y_template)

            pontos_mapeados[pergunta][alternativa] = {
                "x": float(x_img),
                "y": float(y_img)
            }

        analises_por_pergunta[pergunta] = analisar_question_por_template(
            question_data,
            cinza,
            matriz,
            raio=10
        )

    compensacao_por_alternativa = estimar_compensacao_por_alternativa(
        analises_por_pergunta
    )

    for pergunta, question_data in perguntas.items():
        resposta, scores, erro = ler_question_por_template(
            question_data,
            cinza,
            matriz,
            raio=10,
            analises=analises_por_pergunta.get(pergunta),
            compensacao_por_alternativa=compensacao_por_alternativa
        )

        respostas[pergunta] = resposta

        analise_confianca = classificar_confianca_questao(
            pergunta,
            question_data,
            resposta,
            scores,
            erro
        )

        confianca_questoes[pergunta] = analise_confianca

        if analise_confianca.get("pendencia"):
            pendencias_confianca.append(analise_confianca)

        if erro:
            erro_texto = str(erro).lower()

            erros_que_nao_sao_tecnicos = [
                "questão em branco",
                "questao em branco",
                "vazia",
                "em branco"
            ]

            if not any(item in erro_texto for item in erros_que_nao_sao_tecnicos):
                erros.append(f"{pergunta}: {erro}") 

        desenhar_debug_pergunta(
            debug,
            question_data,
            matriz,
            resposta,
            raio=10
        )

        if resposta:
            ponto_ref = question_data["values"][resposta]
            x_ref, y_ref = transformar_ponto(matriz, ponto_ref[0], ponto_ref[1])

            cv2.putText(
                debug,
                f"{pergunta}:{resposta}",
                (int(x_ref) - 30, int(y_ref) - 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 0),
                1
            )

    ra = montar_ra(respostas)

    respostas["Registro Academico"] = ra
    respostas["Codigo de Barras/QRCode001"] = codigo_barras

    caminho_saida = os.path.join(
        pasta_debug,
        "template_" + nome_base
    )

    salvar_imagem(caminho_saida, debug)

    return {
        "registro_academico": ra,
        "codigo_barras": codigo_barras,
        "total_perguntas_modelo": len(perguntas),
        "total_respostas_lidas": len(respostas),
        "total_erros": len(erros),
        "respostas": respostas,
        "erros": erros,
        "pontos_mapeados": pontos_mapeados,
        "pontos_cantos": {
            "TOP_LEFT": {"x": float(pontos_imagem[0][0]), "y": float(pontos_imagem[0][1])},
            "TOP_RIGHT": {"x": float(pontos_imagem[1][0]), "y": float(pontos_imagem[1][1])},
            "BOTTOM_LEFT": {"x": float(pontos_imagem[2][0]), "y": float(pontos_imagem[2][1])},
            "BOTTOM_RIGHT": {"x": float(pontos_imagem[3][0]), "y": float(pontos_imagem[3][1])}
        },
        "origem_cantos": "MANUAL" if pontos_imagem_override is not None else "AUTO",
        "confianca_questoes": confianca_questoes,
        "pendencias_confianca": pendencias_confianca,
        "total_pendencias_confianca": len(pendencias_confianca),
        "debug_bolhas": caminho_saida,
        "debug_cantos": caminho_debug_cantos,
    }, detalhe_cantos

def ordenar_chaves_pergunta(chaves):
    """
    Ordena Pergunta001, Pergunta002, Pergunta003...
    """
    def extrair_numero(chave):
        match = re.search(r"(\d+)$", str(chave))
        return int(match.group(1)) if match else 999999

    return sorted(chaves, key=extrair_numero)

def extrair_id_aluno_do_codigo(codigo_barras):
    codigo_barras = str(codigo_barras).strip()

    if "A" in codigo_barras:
        return codigo_barras.split("A")[-1].strip()

    return ""

def salvar_csv_padrao_formscanner(resultados, caminho_saida_csv):
    """
    Salva o CSV no mesmo formato esperado pelo FormScanner.

    Colunas:
    Nome do arquivo
    group001 a group006 = Registro Acadêmico separado
    Código de Barras/QRCode001
    group008 = idioma
    group009 = cor da capa
    group010 repetido = respostas objetivas
    """

    if not resultados:
        return

    todas_perguntas = set()

    for item in resultados:
        respostas = item.get("respostas", {})
        todas_perguntas.update(respostas.keys())

    perguntas_ordenadas = ordenar_chaves_pergunta(todas_perguntas)

    perguntas_objetivas = []

    for pergunta in perguntas_ordenadas:
        match = re.search(r"(\d+)$", pergunta)

        if not match:
            continue

        numero = int(match.group(1))

        # Pergunta001 a Pergunta006 = RA
        # Pergunta007 = idioma
        # Pergunta008 = cor da capa
        # Pergunta009 em diante = respostas objetivas
        if numero >= 9:
            perguntas_objetivas.append(pergunta)

    cabecalho = [
        "Nome do arquivo",
        "group001",
        "group002",
        "group003",
        "group004",
        "group005",
        "group006",
        "Código de Barras/QRCode001",
        "group008",
        "group009",
    ] + (["group010"] * len(perguntas_objetivas))

    linhas = []

    for item in resultados:
        arquivo = item.get("arquivo", "")
        nome_arquivo = os.path.splitext(os.path.basename(arquivo))[0]

        respostas = item.get("respostas", {})

        registro_academico = str(
            item.get("registro_academico", "")
        ).strip()

        if not registro_academico:
            partes_ra = []

            for i in range(1, 7):
                chave = f"Pergunta{i:03d}"
                partes_ra.append(str(respostas.get(chave, "")).strip())

            registro_academico = "".join(partes_ra)

        registro_academico = re.sub(r"[^A-Za-z0-9]", "", registro_academico)

        ra_digitos = list(registro_academico[:6])

        while len(ra_digitos) < 6:
            ra_digitos.append("")

        codigo_barras = str(
            item.get("codigo_barras", "")
        ).strip()

        if not codigo_barras:
            codigo_barras = str(
                respostas.get("Codigo de Barras/QRCode001", "")
            ).strip()

        if not codigo_barras:
            codigo_barras = str(
                respostas.get("Código de Barras/QRCode001", "")
            ).strip()

        idioma = respostas.get("Pergunta007", "")
        cor_capa = respostas.get("Pergunta008", "")

        linha = [
            nome_arquivo,
            ra_digitos[0],
            ra_digitos[1],
            ra_digitos[2],
            ra_digitos[3],
            ra_digitos[4],
            ra_digitos[5],
            codigo_barras,
            idioma,
            cor_capa,
        ]

        for pergunta in perguntas_objetivas:
            linha.append(respostas.get(pergunta, ""))

        linhas.append(linha)

    with open(caminho_saida_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(cabecalho)
        writer.writerows(linhas)

def normalizar_numero(valor):
    """
    Normaliza RA ou ID removendo ponto, vírgula, espaço e .0 do Excel.
    Exemplo:
    229635.0 -> 229635
    220803.0 -> 220803
    """
    valor = str(valor).strip()

    if valor.lower() in ["nan", "none", ""]:
        return ""

    valor = valor.replace(",", ".")
    
    if valor.endswith(".0"):
        valor = valor[:-2]

    valor = re.sub(r"\D", "", valor)

    return valor

def codigo_barras_completo(codigo_barras):
    """
    Retorna True somente se o código estiver no formato:
    12479A9914
    """
    codigo_barras = str(codigo_barras).strip().upper()
    return bool(re.fullmatch(r"\d+A\d+", codigo_barras))


def extrair_codigo_prova_do_codigo_ou_padrao(codigo_barras, codigo_padrao="12479"):
    """
    Se o leitor conseguiu ler só o código da prova, exemplo 12480,
    usa esse valor como prefixo.
    Se leu 12480A12345, usa a parte antes do A.
    Se não leu nada, usa o padrão.
    """
    codigo_barras = str(codigo_barras).strip().upper()

    if "A" in codigo_barras:
        parte_prova = codigo_barras.split("A")[0]
        parte_prova = normalizar_numero(parte_prova)
        return parte_prova if parte_prova else codigo_padrao

    somente_numero = normalizar_numero(codigo_barras)

    if somente_numero:
        return somente_numero

    return codigo_padrao

def carregar_base_alunos(pasta_projeto):
    """
    Procura uma base de alunos dentro da pasta base.
    Espera colunas como:
    ID, ALUNO, RA, TURMA, UNIDADE...
    """

    pasta_base = os.path.join(pasta_projeto, "base")

    if not os.path.exists(pasta_base):
        return {}

    arquivos = []
    arquivos.extend(glob.glob(os.path.join(pasta_base, "*.csv")))
    arquivos.extend(glob.glob(os.path.join(pasta_base, "*.xlsx")))

    if not arquivos:
        return {}

    caminho_base = arquivos[0]

    if caminho_base.lower().endswith(".csv"):
        try:
            df = pd.read_csv(caminho_base, sep=";", dtype=str, encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(caminho_base, sep=",", dtype=str, encoding="utf-8-sig")
    else:
        df = pd.read_excel(caminho_base, dtype=str)

    df.columns = df.columns.str.strip().str.upper()

    if "RA" not in df.columns or "ID" not in df.columns:
        raise ValueError("A base precisa ter as colunas ID e RA.")

    mapa_ra_para_id = {}

    for _, linha in df.iterrows():
        ra = normalizar_numero(linha.get("RA", ""))
        id_aluno = normalizar_numero(linha.get("ID", ""))

        if ra and id_aluno:
            mapa_ra_para_id[ra] = id_aluno

    return mapa_ra_para_id


def extrair_codigo_prova_do_nome_ou_modelo(nome_arquivo, codigo_padrao="12479"):
    """
    Define o código da prova que fica antes do A.
    Por enquanto usa 12479 como padrão.
    Depois podemos melhorar para ler isso automaticamente do cartão.
    """
    return codigo_padrao


def montar_codigo_barras_por_ra(registro_academico, mapa_ra_para_id, codigo_prova):
    """
    Monta Código de Barras/QRCode001 usando:
    código da prova + A + ID do aluno encontrado pela base.
    """

    ra = normalizar_numero(registro_academico)

    if not ra:
        return ""

    id_aluno = mapa_ra_para_id.get(ra, "")

    if not id_aluno:
        return ""

    return f"{codigo_prova}A{id_aluno}"
       
def processar_imagens_omr(
    pasta_imagens,
    pasta_saida="saida",
    progresso_callback=None,
    evento_callback=None
):
    """
    Processa todas as imagens de uma pasta usando o modelo .xtmpl.

    A cada execução, cria uma nova pasta dentro de 'saida',
    mantendo logs, imagens de debug, pendências e leituras OMR organizados por processo.

    IMPORTANTE:
    O CSV final respostas_omr.csv não é gerado aqui.
    Ele será gerado somente depois das correções manuais no painel.
    """

    os.makedirs(pasta_saida, exist_ok=True)

    # Cria uma pasta exclusiva para esta execução
    data_execucao = agora_local().strftime("%Y%m%d_%H%M%S")
    pasta_execucao = os.path.join(
        pasta_saida,
        f"processamento_{data_execucao}"
    )

    os.makedirs(pasta_execucao, exist_ok=True)

    # Pastas internas do processamento
    pasta_debug = os.path.join(pasta_execucao, "debug_omr")
    os.makedirs(pasta_debug, exist_ok=True)

    pasta_manual = os.path.join(pasta_execucao, "manual_omr")
    os.makedirs(pasta_manual, exist_ok=True)

    pasta_originais = os.path.join(pasta_execucao, "originais")
    os.makedirs(pasta_originais, exist_ok=True)

    pasta_pendencias = os.path.join(pasta_execucao, "pendencias")
    os.makedirs(pasta_pendencias, exist_ok=True)

    # Este dicionário será usado pelo painel de correção manual
    leituras_omr = {}

    imagens = listar_imagens(pasta_imagens)
    
    total_imagens_callback = len(imagens)

    if progresso_callback:
        progresso_callback(
            0,
            total_imagens_callback,
            "Iniciando leitura OMR..."
        )

    caminho_modelo = caminho_modelo_omr_padrao()

    if not os.path.exists(caminho_modelo):
        raise FileNotFoundError(
            f"Modelo .xtmpl nao encontrado. Caminho testado: {caminho_modelo}"
        )

    log = []
    linhas_respostas = []
    resultados_formscanner = []

    for indice, imagem in enumerate(imagens, start=1):
        if progresso_callback:
            progresso_callback(
                indice - 1,
                total_imagens_callback,
                f"Processando imagem {indice} de {total_imagens_callback}: {imagem}"
            )
        caminho_imagem = os.path.join(pasta_imagens, imagem)

        caminho_original_processamento = os.path.join(pasta_originais, imagem)

        if not os.path.exists(caminho_original_processamento):
            try:
                shutil.copy2(caminho_imagem, caminho_original_processamento)
            except Exception:
                caminho_original_processamento = caminho_imagem

        try:
            resultado, detalhe = detectar_respostas_por_template(
                caminho_imagem,
                caminho_modelo,
                pasta_debug
            )

            status = "OK" if resultado else "ERRO"
            respostas = resultado.get("respostas", {}) if resultado else {}
            erros = (
                resultado.get("erros", [])
                if resultado
                else [str(detalhe or "Falha desconhecida durante a leitura.")]
            )

            codigo_prova = extrair_codigo_prova_do_nome_ou_modelo(
                imagem,
                codigo_padrao="12479"
            )
            debug_bolhas_log = ""
            debug_cantos_log = ""

            if resultado:
                codigo_barras_atual = str(
                    resultado.get("codigo_barras", "")
                ).strip().upper()

                registro_academico_lido = resultado.get(
                    "registro_academico",
                    ""
                )

                codigo_prova = extrair_codigo_prova_do_codigo_ou_padrao(
                    codigo_barras_atual,
                    codigo_padrao="12479"
                )

                # Se o código já veio completo, mantém.
                if codigo_barras_completo(codigo_barras_atual):
                    respostas["Codigo de Barras/QRCode001"] = codigo_barras_atual

                # Se veio só o código da prova, mantém parcial e deixa a identificação
                # do aluno para a etapa de validação pela API usando o RA.
                else:
                    resultado["codigo_barras"] = codigo_barras_atual
                    respostas["Codigo de Barras/QRCode001"] = codigo_barras_atual

                    if registro_academico_lido:
                        erros.append(
                            "Código de Barras/QRCode001: cartão sem ID final; "
                            "a identificação será concluída na validação pela API via RA."
                        )
                    else:
                        erros.append(
                            "Código de Barras/QRCode001: cartão sem ID final e sem RA suficiente "
                            "para identificação automática."
                        )

                if erros and evento_callback:
                    evento_callback(
                        tipo="warning",
                        titulo="Leitura com pendência",
                        descricao=" | ".join(erros[:2]),
                        arquivo=imagem
                    )

                # Salva a leitura completa para o painel de correção manual
                nome_debug = "template_" + os.path.basename(caminho_imagem)

                leituras_omr[nome_debug] = {
                    "arquivo_original": os.path.basename(caminho_imagem),
                    "caminho_original_processamento": caminho_original_processamento,
                    "respostas": respostas,
                    "pontos_mapeados": resultado.get("pontos_mapeados", {}),
                    "pontos_cantos": resultado.get("pontos_cantos", []),
                    "origem_cantos": resultado.get("origem_cantos", "AUTO"),
                    "registro_academico": resultado.get("registro_academico", ""),
                    "codigo_barras": resultado.get("codigo_barras", ""),
                    "debug_bolhas": resultado.get("debug_bolhas", ""),
                    "erros": erros,
                    "confianca_questoes": resultado.get("confianca_questoes", {}),
                    "pendencias_confianca": resultado.get("pendencias_confianca", []),
                    "total_pendencias_confianca": resultado.get("total_pendencias_confianca", 0)
                }
                debug_bolhas_log = resultado.get("debug_bolhas", "")
                debug_cantos_log = resultado.get("debug_cantos", "")
            else:
                dados_correcao_manual = registrar_imagem_para_correcao_manual(
                    leituras_omr=leituras_omr,
                    pasta_debug=pasta_debug,
                    pasta_manual=pasta_manual,
                    pasta_pendencias=pasta_pendencias,
                    caminho_imagem=caminho_imagem,
                    caminho_original_processamento=caminho_original_processamento,
                    imagem=imagem,
                    respostas={},
                    erros=erros,
                    pontos_mapeados={},
                    pontos_cantos=[],
                    origem_cantos="AUTO"
                )
                debug_bolhas_log = dados_correcao_manual["debug_bolhas"]
                debug_cantos_log = dados_correcao_manual["debug_cantos"]

                if evento_callback:
                    evento_callback(
                        tipo="error",
                        titulo="Imagem não lida",
                        descricao=str(detalhe or "Falha desconhecida durante a leitura."),
                        arquivo=imagem
                    )

            precisa_correcao_manual = status == "ERRO" or len(erros) > 0

            resultados_formscanner.append({
                "arquivo": imagem,
                "registro_academico": resultado.get("registro_academico", "") if resultado else "",
                "codigo_barras": resultado.get("codigo_barras", "") if resultado else "",
                "respostas": respostas
            })

            linha_respostas = {
                "arquivo": imagem
            }

            if precisa_correcao_manual:
                dados_correcao_manual = registrar_imagem_para_correcao_manual(
                    leituras_omr=leituras_omr,
                    pasta_debug=pasta_debug,
                    pasta_manual=pasta_manual,
                    pasta_pendencias=pasta_pendencias,
                    caminho_imagem=caminho_imagem,
                    caminho_original_processamento=caminho_original_processamento,
                    imagem=imagem,
                    respostas=respostas,
                    erros=erros,
                    pontos_mapeados=resultado.get("pontos_mapeados", {}) if resultado else {},
                    pontos_cantos=resultado.get("pontos_cantos", []) if resultado else [],
                    origem_cantos=resultado.get("origem_cantos", "AUTO") if resultado else "AUTO",
                    registro_academico=resultado.get("registro_academico", "") if resultado else "",
                    codigo_barras=resultado.get("codigo_barras", "") if resultado else "",
                    debug_bolhas=debug_bolhas_log,
                    debug_cantos=debug_cantos_log,
                    confianca_questoes=resultado.get("confianca_questoes", {}) if resultado else {},
                    pendencias_confianca=resultado.get("pendencias_confianca", []) if resultado else [],
                    total_pendencias_confianca=resultado.get("total_pendencias_confianca", 0) if resultado else 0
                )
                caminho_json_manual = dados_correcao_manual["caminho_json_manual"]
            else:
                caminho_json_manual = ""

            linha_respostas.update(respostas)
            linhas_respostas.append(linha_respostas)

            log.append({
                "arquivo": imagem,
                "status": status,
                "registro_academico": resultado.get("registro_academico", "") if resultado else "",
                "codigo_barras": resultado.get("codigo_barras", "") if resultado else "",
                "total_perguntas_modelo": resultado.get("total_perguntas_modelo", 0) if resultado else 0,
                "total_respostas_lidas": resultado.get("total_respostas_lidas", 0) if resultado else 0,
                "total_erros": len(erros),
                "correcao_manual": "SIM" if precisa_correcao_manual else "NÃO",
                "arquivo_manual": caminho_json_manual,
                "erros": " | ".join(erros),
                "debug_bolhas": debug_bolhas_log,
                "debug_cantos": debug_cantos_log,
                "detalhe": detalhe
            })
            
            if progresso_callback:
                progresso_callback(
                    indice,
                    total_imagens_callback,
                    f"Imagem {indice} de {total_imagens_callback} concluída."
                )

        except Exception as e:
            dados_correcao_manual = registrar_imagem_para_correcao_manual(
                leituras_omr=leituras_omr,
                pasta_debug=pasta_debug,
                pasta_manual=pasta_manual,
                pasta_pendencias=pasta_pendencias,
                caminho_imagem=caminho_imagem,
                caminho_original_processamento=caminho_original_processamento,
                imagem=imagem,
                respostas={},
                erros=[str(e)],
                pontos_mapeados={},
                pontos_cantos=[],
                origem_cantos="AUTO"
            )
            if evento_callback:
                evento_callback(
                    tipo="error",
                    titulo="Falha na leitura da imagem",
                    descricao=str(e),
                    arquivo=imagem
                )
            log.append({
                "arquivo": imagem,
                "status": "ERRO",
                "registro_academico": "",
                "codigo_barras": "",
                "total_perguntas_modelo": 0,
                "total_respostas_lidas": 0,
                "total_erros": 1,
                "correcao_manual": "SIM",
                "arquivo_manual": dados_correcao_manual["caminho_json_manual"],
                "erros": str(e),
                "debug_bolhas": dados_correcao_manual["debug_bolhas"],
                "debug_cantos": dados_correcao_manual["debug_cantos"],
                "detalhe": "Erro ao processar imagem"
            })
            
            if progresso_callback:
                progresso_callback(
                    indice,
                    total_imagens_callback,
                    f"Imagem {indice} de {total_imagens_callback} finalizada com erro."
                )

    caminho_log = os.path.join(pasta_execucao, "log_leitura_omr.csv")
    caminho_respostas = os.path.join(pasta_execucao, "respostas_omr.csv")
    caminho_resumo = os.path.join(pasta_execucao, "resumo_processamento.txt")
    caminho_leituras_omr = os.path.join(pasta_execucao, "leituras_omr.json")

    # Salva o JSON usado pelo painel de correção manual
    with open(caminho_leituras_omr, "w", encoding="utf-8") as f:
        json.dump(leituras_omr, f, ensure_ascii=False, indent=4)

    df_log = pd.DataFrame(log)

    df_log.to_csv(
        caminho_log,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    # IMPORTANTE:
    # O CSV final será gerado somente após a correção manual no painel.
    # Por isso, esta função permanece comentada.
    #
    # salvar_csv_padrao_formscanner(
    #     resultados_formscanner,
    #     caminho_respostas
    # )

    total_imagens = len(imagens)
    total_ok = sum(1 for item in log if item["status"] == "OK")
    total_erro = sum(1 for item in log if item["status"] == "ERRO")
    total_manual = sum(1 for item in log if item["correcao_manual"] == "SIM")

    with open(caminho_resumo, "w", encoding="utf-8") as f:
        f.write("RESUMO DO PROCESSAMENTO OMR\n")
        f.write("==========================\n\n")
        f.write(f"Data da execução: {agora_local().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"Pasta de imagens: {pasta_imagens}\n")
        f.write(f"Pasta de saída: {pasta_execucao}\n")
        f.write(f"Modelo usado: {caminho_modelo}\n\n")
        f.write(f"Total de imagens encontradas: {total_imagens}\n")
        f.write(f"Total processado com status OK: {total_ok}\n")
        f.write(f"Total com erro: {total_erro}\n")
        f.write(f"Total enviado para correção manual: {total_manual}\n\n")
        f.write("Arquivos gerados:\n")
        f.write("- CSV de respostas: será gerado após a correção manual\n")
        f.write(f"- Log de leitura: {caminho_log}\n")
        f.write(f"- Leituras OMR: {caminho_leituras_omr}\n")
        f.write(f"- Debug das imagens: {pasta_debug}\n")
        f.write(f"- Pendências manuais: {pasta_manual}\n")
        f.write(f"- Imagens pendentes: {pasta_pendencias}\n")

    if progresso_callback:
        progresso_callback(
            total_imagens,
            total_imagens,
            "Processamento OMR concluído."
        )
        
    return {
        "total_imagens": total_imagens,
        "total_ok": total_ok,
        "total_erro": total_erro,
        "total_manual": total_manual,
        "pasta_execucao": pasta_execucao,
        "log": caminho_log,
        "respostas": caminho_respostas,
        "debug": pasta_debug,
        "manual": pasta_manual,
        "resumo": caminho_resumo,
        "pasta_processamento": pasta_execucao,
        "leituras_omr": caminho_leituras_omr
    }
