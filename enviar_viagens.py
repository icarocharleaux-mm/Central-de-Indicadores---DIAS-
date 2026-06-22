"""
Envia o Relatório de Resumo de Viagens para a aba 'Viagens' do Google Sheet,
pelo mesmo Apps Script Web App usado nas pendências.

Uso:
    py enviar_viagens.py [caminho_do_arquivo.xlsx]
Sem argumento, usa o relatorioResumoViagens*.xlsx mais recente na pasta.
"""
import glob
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

ABA = "Viagens"
# Colunas que NAO sobem (ajudante = dado pessoal; setores = campo baguncado)
DESCARTAR = ["Ajudante", "Setores"]

_AQUI = Path(__file__).resolve().parent


def _carregar_env():
    env = _AQUI / ".env"
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _detectar_header(arq: Path) -> int:
    probe = pd.read_excel(arq, header=None, nrows=15, engine="openpyxl")
    for i in range(len(probe)):
        if "Motorista" in [str(x).strip() for x in probe.iloc[i].tolist()]:
            return i
    return 7


def main():
    _carregar_env()
    url = os.environ.get("SHEETS_WEBAPP_URL", "")
    token = os.environ.get("SHEETS_WEBAPP_TOKEN", "")
    if not url or not token:
        raise SystemExit("Defina SHEETS_WEBAPP_URL e SHEETS_WEBAPP_TOKEN no .env")

    if len(sys.argv) > 1:
        arq = Path(sys.argv[1])
    else:
        hits = sorted(glob.glob("relatorioResumoViagens*.xlsx"), reverse=True)
        if not hits:
            raise SystemExit("Nenhum relatorioResumoViagens*.xlsx encontrado.")
        arq = Path(hits[0])

    print(f"Lendo: {arq.name}", flush=True)
    hdr = _detectar_header(arq)
    df = pd.read_excel(arq, header=hdr, engine="openpyxl").dropna(how="all")
    df = df[df["Motorista"].notna()].copy()
    df = df.drop(columns=[c for c in DESCARTAR if c in df.columns])

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    df = df.where(pd.notna(df), "")
    df["Atualizado em"] = datetime.fromtimestamp(arq.stat().st_mtime).strftime("%d/%m/%Y %H:%M")

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    full = url + "?" + urllib.parse.urlencode({"token": token, "aba": ABA})
    req = urllib.request.Request(full, data=csv_bytes, method="POST",
                                 headers={"Content-Type": "text/csv; charset=utf-8"})
    print(f"Enviando {len(df)} linhas x {len(df.columns)} colunas para a aba '{ABA}'...",
          flush=True)
    with urllib.request.urlopen(req, timeout=180) as resp:
        print("Resposta:", resp.read().decode("utf-8", errors="replace").strip())


if __name__ == "__main__":
    main()
