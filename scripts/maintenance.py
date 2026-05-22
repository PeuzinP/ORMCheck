import argparse
import shutil
import sys
import zipfile
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.settings import (
    APP_BACKUP_ENABLED,
    APP_ENV,
    APP_RETENTION_DAYS,
    APP_UPLOAD_TEMP_RETENTION_HOURS,
    PASTA_BACKUPS,
    PASTA_LOGS,
    PASTA_PROCESSAMENTOS,
    PASTA_RUNTIME,
    PASTA_UPLOADS_TEMP
)
from app.time_utils import agora_local, fromtimestamp_local


def gerar_backup():
    if not APP_BACKUP_ENABLED:
        print("Backup desabilitado por APP_BACKUP_ENABLED=false.")
        return None

    PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = agora_local().strftime("%Y%m%d_%H%M%S")
    caminho_zip = PASTA_BACKUPS / f"backup_{APP_ENV}_{timestamp}.zip"
    pastas_backup = [
        PASTA_PROCESSAMENTOS,
        PASTA_RUNTIME,
        PASTA_LOGS
    ]

    with zipfile.ZipFile(caminho_zip, "w", compression=zipfile.ZIP_DEFLATED) as arquivo_zip:
        for pasta in pastas_backup:
            if not pasta.exists():
                continue

            for item in pasta.rglob("*"):
                if item.is_file():
                    arquivo_zip.write(item, item.relative_to(PASTA_PROCESSAMENTOS.parent))

    print(f"Backup criado em: {caminho_zip}")
    return caminho_zip


def _itens_antigos(pasta: Path, cutoff: datetime):
    itens = []
    if not pasta.exists():
        return itens

    for item in pasta.iterdir():
        atualizado_em = fromtimestamp_local(item.stat().st_mtime)
        if atualizado_em < cutoff:
            itens.append(item)

    return itens


def limpar_processamentos_antigos(dry_run=False):
    cutoff = agora_local() - timedelta(days=APP_RETENTION_DAYS)
    removidos = []

    for item in _itens_antigos(PASTA_PROCESSAMENTOS, cutoff):
        removidos.append(item)
        if not dry_run:
            shutil.rmtree(item, ignore_errors=True)

    return removidos


def limpar_uploads_temporarios(dry_run=False):
    cutoff = agora_local() - timedelta(hours=APP_UPLOAD_TEMP_RETENTION_HOURS)
    removidos = []

    for item in _itens_antigos(PASTA_UPLOADS_TEMP, cutoff):
        removidos.append(item)
        if not dry_run:
            shutil.rmtree(item, ignore_errors=True)

    return removidos


def limpar_logs_antigos(dry_run=False):
    cutoff = agora_local() - timedelta(days=APP_RETENTION_DAYS)
    removidos = []

    for item in _itens_antigos(PASTA_LOGS, cutoff):
        removidos.append(item)
        if not dry_run and item.is_file():
            item.unlink(missing_ok=True)

    return removidos


def executar_rotina(dry_run=False):
    backup = None if dry_run else gerar_backup()
    processamentos = limpar_processamentos_antigos(dry_run=dry_run)
    uploads = limpar_uploads_temporarios(dry_run=dry_run)
    logs = limpar_logs_antigos(dry_run=dry_run)

    print(f"Processamentos antigos: {len(processamentos)}")
    print(f"Uploads temporarios antigos: {len(uploads)}")
    print(f"Logs antigos: {len(logs)}")
    print(f"Runtime mantido em: {PASTA_RUNTIME}")

    return {
        "backup": str(backup) if backup else "",
        "processamentos": [str(item) for item in processamentos],
        "uploads": [str(item) for item in uploads],
        "logs": [str(item) for item in logs]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Rotinas operacionais de backup e retencao do OMRCheck Web."
    )
    parser.add_argument(
        "acao",
        choices=["backup", "cleanup", "all"],
        help="Rotina a executar."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria limpo sem remover arquivos."
    )
    args = parser.parse_args()

    if args.acao == "backup":
        gerar_backup()
        return

    if args.acao == "cleanup":
        processamentos = limpar_processamentos_antigos(dry_run=args.dry_run)
        uploads = limpar_uploads_temporarios(dry_run=args.dry_run)
        logs = limpar_logs_antigos(dry_run=args.dry_run)
        print(f"Processamentos antigos: {len(processamentos)}")
        print(f"Uploads temporarios antigos: {len(uploads)}")
        print(f"Logs antigos: {len(logs)}")
        return

    executar_rotina(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
