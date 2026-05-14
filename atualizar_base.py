import os
import pandas as pd
from config import URL_BASE_ALUNOS_CSV

print("RODANDO ATUALIZAR BASE")

PASTA_BASE = "base"
ARQUIVO_BASE = "alunos.csv"

os.makedirs(PASTA_BASE, exist_ok=True)

caminho_base = os.path.join(PASTA_BASE, ARQUIVO_BASE)

print("Atualizando base local a partir do Google Sheets...")

try:
    df = pd.read_csv(
        URL_BASE_ALUNOS_CSV,
        dtype=str,
        sep=",",
        engine="python",
        on_bad_lines="skip"
    )

    df.columns = df.columns.str.strip()

    df.to_csv(
        caminho_base,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    print("Base atualizada com sucesso!")
    print("Arquivo salvo em:", caminho_base)
    print("Total de alunos importados:", len(df))

except Exception as erro:
    print("Erro ao atualizar a base:")
    print(erro)