import json
from pathlib import Path
import unicodedata

import requests

from app.gerador_csv import TOTAL_PERGUNTAS, carregar_leituras, nome_arquivo_keepedu, resposta
from app.services import caminho_leituras
from app.settings import (
    ID_PROVA_KEEPEDU,
    KEEPEDU_API_KEY,
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


def _payload_base(id_aval: str) -> dict:
    id_aval_payload = int(id_aval) if id_aval.isdigit() else id_aval

    return {
        "idAval": id_aval_payload,
    }


def _montar_aluno_payload(
    nome_imagem: str,
    dados_cartao: dict,
    validacao: dict,
    id_aval: str,
    nome_arquivo: str,
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

    respostas = dados_cartao.get("respostas", {})
    aluno = {
        "nomeArquivo": nome_arquivo,
        "lingua": resposta(respostas, 7),
        "respostas": _montar_respostas_objetivas(dados_cartao),
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
            "mensagem": [resposta_api.text.strip() or "A API não retornou um JSON válido."],
        }

    return status_code, corpo_resposta


def _motivo_pendencia_avaliacao(corpo_resposta: dict, nome_arquivo: str) -> str:
    mensagens = _mensagens_resposta(corpo_resposta)

    if mensagens:
        return " | ".join(mensagens[:3])

    return (
        f"O aluno do cartão {nome_arquivo} não pertence à avaliação informada "
        "ou ainda não foi incluído nela."
    )


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
        return 400, {
            "success": False,
            "mensagem": ["Corpo da requisição deve ser um objeto JSON."],
            "arquivoErros": []
        }

    alunos = dados.get("alunos", [])

    if not isinstance(alunos, list):
        return 400, {
            "success": False,
            "mensagem": ["A propriedade 'alunos' deve ser uma lista."],
            "arquivoErros": []
        }

    for aluno in alunos:
        if not isinstance(aluno, dict):
            return 400, {
                "success": False,
                "mensagem": ["Cada aluno na lista deve ser um objeto JSON."],
                "arquivoErros": []
            }

        if not aluno.get("barcode") and not aluno.get("idAluno"):
            return 400, {
                "success": False,
                "mensagem": [
                    f"Aluno {aluno.get('nomeArquivo', 'desconhecido')} não possui barcode nem idAluno."
                ],
                "arquivoErros": []
            }

    return 200, {
        "success": True,
        "idAval": dados.get("idAval"),
        "total": len(alunos),
        "importadas": len(alunos),
        "erros": 0,
        "mensagem": ["Simulação: Importação realizada com sucesso."],
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
):
    if not url_destino:
        return {
            "status": "erro",
            "mensagem": (
                "A URL de simulação não está configurada no arquivo .env."
                if modo == "simulacao" else
                "A URL de importação direta não está configurada no arquivo .env."
            ),
        }

    if not KEEPEDU_API_KEY:
        return {
            "status": "erro",
            "mensagem": "A ApiKey da KeepEdu não está configurada no arquivo .env.",
        }

    if not KEEPEDU_INSTITUTE:
        return {
            "status": "erro",
            "mensagem": "O Institute da KeepEdu não está configurado no arquivo .env.",
        }

    leituras = carregar_leituras(nome_processamento)
    dados_validacao = carregar_validacao_cadastral_salva(nome_processamento)

    if not dados_validacao:
        dados_validacao = gerar_validacao_cadastral(nome_processamento)

    validacoes = dados_validacao.get("validacoes", {})
    itens_envio, id_aluno_filtrado = _selecionar_itens_importacao(leituras, validacoes, id_aluno=id_aluno)
    total_itens = len(itens_envio)

    id_aval_final = _detectar_id_aval(dados_validacao, id_aval)
    if not id_aval_final:
        return {
            "status": "erro",
            "mensagem": "Informe o ID da avaliação antes de enviar as respostas.",
        }

    cabecalhos = _cabecalhos_keepedu()
    payload_base = _payload_base(id_aval_final)
    detalhes = []
    total = 0
    importadas = 0
    mensagens = []
    arquivos_erros = []
    pendencias_avaliacao = []
    validacao_atualizada = False

    _emitir_progresso_importacao(
        progresso_callback,
        percentual=5,
        mensagem="Preparando envio dos cartões para a plataforma...",
        resultado={"modo": modo, "id_aluno": id_aluno_filtrado},
        tipo="info",
        titulo="Envio iniciado",
        descricao=f"Preparando lote {nome_processamento} para envio em modo {modo}.",
    )

    for indice, (nome_imagem, dados_cartao, validacao) in enumerate(itens_envio, start=1):
        total += 1

        try:
            nome_arquivo = nome_arquivo_keepedu(dados_cartao.get("arquivo_original", nome_imagem))
            aluno = _montar_aluno_payload(
                nome_imagem,
                dados_cartao,
                validacao,
                id_aval_final,
                nome_arquivo,
            )
            percentual_inicio = 5 + int(((indice - 1) / max(total_itens, 1)) * 90)
            _emitir_progresso_importacao(
                progresso_callback,
                percentual=percentual_inicio,
                mensagem=f"Processando aluno {indice}/{max(total_itens, 1)} para envio...",
                arquivo_atual=nome_arquivo,
                resultado={
                    "total": total_itens,
                    "processadas": indice - 1,
                    "importadas": importadas,
                    "erros": max((indice - 1) - importadas, 0),
                    "modo": modo,
                    "id_aluno": id_aluno_filtrado,
                },
            )
            payload_envio = {
                **payload_base,
                "alunos": [aluno],
            }

            if modo == "simulacao":
                status_code, corpo_resposta = processar_mock_importacao_keepedu(payload_envio)
            else:
                if KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL:
                    (
                        status_pre_validacao,
                        corpo_pre_validacao,
                    ) = _post_keepedu(KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL, payload_envio, cabecalhos)

                    if _resposta_indica_aluno_fora_avaliacao(corpo_pre_validacao):
                        motivo_pendencia = _motivo_pendencia_avaliacao(
                            corpo_pre_validacao,
                            aluno.get("nomeArquivo") or nome_imagem,
                        )
                        registrar_pendencia_importacao(
                            nome_processamento=nome_processamento,
                            nome_imagem=nome_imagem,
                            status_validacao="PENDENTE_ALUNO_FORA_AVALIACAO",
                            motivo=motivo_pendencia,
                            detalhes={
                                "idAval": payload_base["idAval"],
                                "status_code": status_pre_validacao,
                                "resposta": corpo_pre_validacao,
                            },
                        )
                        validacao_atualizada = True
                        pendencias_avaliacao.append({
                            "imagem": nome_imagem,
                            "nomeArquivo": nome_arquivo,
                            "motivo": motivo_pendencia,
                        })
                        detalhes.append({
                            "imagem": nome_imagem,
                            "nomeArquivo": nome_arquivo,
                            "barcode": aluno.get("barcode", ""),
                            "idAluno": aluno.get("idAluno", ""),
                            "payload": payload_envio,
                            "status_code": status_pre_validacao,
                            "resposta": corpo_pre_validacao,
                            "sucesso": False,
                            "pendencia_avaliacao": True,
                            "etapa": "pre_validacao_avaliacao",
                        })
                        mensagens.append(motivo_pendencia)
                        percentual_pendencia = 5 + int((indice / max(total_itens, 1)) * 90)
                        _emitir_progresso_importacao(
                            progresso_callback,
                            percentual=percentual_pendencia,
                            mensagem=f"Pendência detectada para {nome_arquivo}.",
                            arquivo_atual=nome_arquivo,
                            resultado={
                                "total": total_itens,
                                "processadas": indice,
                                "importadas": importadas,
                                "erros": total - importadas,
                                "modo": modo,
                                "id_aluno": id_aluno_filtrado,
                            },
                            tipo="warning",
                            titulo="Aluno fora da avaliação",
                            descricao=motivo_pendencia,
                        )

                        arquivos_erros_api = corpo_pre_validacao.get("arquivoErros") or []
                        if isinstance(arquivos_erros_api, list):
                            arquivos_erros.extend(arquivos_erros_api)
                        continue

                status_code, corpo_resposta = _post_keepedu(url_destino, payload_envio, cabecalhos)

            sucesso = (200 <= status_code < 300) and bool(corpo_resposta.get("success"))
            fora_avaliacao = _resposta_indica_aluno_fora_avaliacao(corpo_resposta)

            if fora_avaliacao:
                motivo_pendencia = _motivo_pendencia_avaliacao(
                    corpo_resposta,
                    nome_arquivo,
                )
                registrar_pendencia_importacao(
                    nome_processamento=nome_processamento,
                    nome_imagem=nome_imagem,
                    status_validacao="PENDENTE_ALUNO_FORA_AVALIACAO",
                    motivo=motivo_pendencia,
                    detalhes={
                        "idAval": payload_base["idAval"],
                        "status_code": status_code,
                        "resposta": corpo_resposta,
                    },
                )
                validacao_atualizada = True
                pendencias_avaliacao.append({
                    "imagem": nome_imagem,
                    "nomeArquivo": nome_arquivo,
                    "motivo": motivo_pendencia,
                })
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
            }
            detalhes.append(detalhe)

            mensagens_api = corpo_resposta.get("mensagem") or []
            if isinstance(mensagens_api, list):
                mensagens.extend(str(item).strip() for item in mensagens_api if str(item).strip())

            arquivos_erros_api = corpo_resposta.get("arquivoErros") or []
            if isinstance(arquivos_erros_api, list):
                arquivos_erros.extend(arquivos_erros_api)

            if sucesso:
                importadas += 1
                percentual_sucesso = 5 + int((indice / max(total_itens, 1)) * 90)
                _emitir_progresso_importacao(
                    progresso_callback,
                    percentual=percentual_sucesso,
                    mensagem=f"Aluno {indice}/{max(total_itens, 1)} enviado com sucesso.",
                    arquivo_atual=nome_arquivo,
                    resultado={
                        "total": total_itens,
                        "processadas": indice,
                        "importadas": importadas,
                        "erros": total - importadas,
                        "modo": modo,
                        "id_aluno": id_aluno_filtrado,
                    },
                    tipo="success",
                    titulo="Aluno enviado",
                    descricao=nome_arquivo,
                )
            else:
                if not mensagens_api:
                    mensagens.append(
                        f"Falha ao importar {nome_arquivo}: "
                        f"HTTP {status_code}."
                    )
                percentual_erro = 5 + int((indice / max(total_itens, 1)) * 90)
                _emitir_progresso_importacao(
                    progresso_callback,
                    percentual=percentual_erro,
                    mensagem=f"Falha ao processar aluno {indice}/{max(total_itens, 1)}.",
                    arquivo_atual=nome_arquivo,
                    resultado={
                        "total": total_itens,
                        "processadas": indice,
                        "importadas": importadas,
                        "erros": total - importadas,
                        "modo": modo,
                        "id_aluno": id_aluno_filtrado,
                    },
                    tipo="error",
                    titulo="Falha no envio",
                    descricao=" | ".join(_mensagens_resposta(corpo_resposta)[:3]) or f"HTTP {status_code}",
                )

        except requests.RequestException as exc:
            detalhes.append({
                "imagem": nome_imagem,
                "status_code": None,
                "sucesso": False,
                "erro": f"Erro de comunicação com a API: {exc}",
            })
            mensagens.append(f"Erro de comunicação ao importar {nome_imagem}: {exc}")
            percentual_comunicacao = 5 + int((indice / max(total_itens, 1)) * 90)
            _emitir_progresso_importacao(
                progresso_callback,
                percentual=percentual_comunicacao,
                mensagem=f"Erro de comunicação ao enviar {nome_imagem}.",
                arquivo_atual=nome_imagem,
                resultado={
                    "total": total_itens,
                    "processadas": indice,
                    "importadas": importadas,
                    "erros": total - importadas,
                    "modo": modo,
                    "id_aluno": id_aluno_filtrado,
                },
                tipo="error",
                titulo="Erro de comunicação",
                descricao=str(exc),
            )
        except ValueError as exc:
            detalhes.append({
                "imagem": nome_imagem,
                "status_code": None,
                "sucesso": False,
                "erro": str(exc),
            })
            mensagens.append(str(exc))
            percentual_validacao = 5 + int((indice / max(total_itens, 1)) * 90)
            _emitir_progresso_importacao(
                progresso_callback,
                percentual=percentual_validacao,
                mensagem=f"Cartão {nome_imagem} exige ajuste antes do envio.",
                arquivo_atual=nome_imagem,
                resultado={
                    "total": total_itens,
                    "processadas": indice,
                    "importadas": importadas,
                    "erros": total - importadas,
                    "modo": modo,
                    "id_aluno": id_aluno_filtrado,
                },
                tipo="warning",
                titulo="Pendência de identificação",
                descricao=str(exc),
            )

    erros = total - importadas
    status = "ok" if erros == 0 else "parcial"

    if total == 0:
        status = "erro"
        if id_aluno_filtrado:
            mensagens.append(
                f"Nenhum cartão validado com ID final {id_aluno_filtrado} foi encontrado neste processamento."
            )
        else:
            mensagens.append("Nenhum cartão foi encontrado neste processamento.")

    relatorio = {
        "status": status,
        "success": status == "ok",
        "modo": modo,
        "url_destino": url_destino,
        "idAval": payload_base["idAval"],
        "id_aluno": id_aluno_filtrado,
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
        mensagem=(
            "Envio concluído com sucesso."
            if status == "ok" else
            "Envio concluído com pendências."
        ),
        resultado=relatorio,
        tipo="success" if status == "ok" else "warning",
        titulo="Envio finalizado",
        descricao=f"{importadas}/{total} importada(s), {erros} erro(s).",
    )
    relatorio["arquivo_relatorio"] = _salvar_relatorio(nome_processamento, relatorio, modo=modo)
    return relatorio


def importar_respostas_presenciais(
    nome_processamento: str,
    id_aval=None,
    dia_aval=None,
    usuario_id=None,
    id_aluno=None,
    progresso_callback=None,
):
    return _executar_importacao_respostas_presenciais(
        nome_processamento=nome_processamento,
        url_destino=KEEPEDU_IMPORTAR_RESPOSTAS_URL,
        modo="importacao",
        id_aval=id_aval,
        dia_aval=dia_aval,
        usuario_id=usuario_id,
        id_aluno=id_aluno,
        progresso_callback=progresso_callback,
    )


def simular_importacao_respostas_presenciais(
    nome_processamento: str,
    id_aval=None,
    dia_aval=None,
    usuario_id=None,
    id_aluno=None,
    progresso_callback=None,
):
    return _executar_importacao_respostas_presenciais(
        nome_processamento=nome_processamento,
        url_destino=KEEPEDU_SIMULAR_IMPORTAR_RESPOSTAS_URL,
        modo="simulacao",
        id_aval=id_aval,
        dia_aval=dia_aval,
        usuario_id=usuario_id,
        id_aluno=id_aluno,
        progresso_callback=progresso_callback,
    )
