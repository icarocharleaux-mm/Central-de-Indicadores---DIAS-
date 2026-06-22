"""
Baixa o relatório de Pendências do sistema Diaslog automaticamente.

Cobertura : 90 dias (limite do sistema = 60 dias por consulta)
  Periodo 1: hoje - 90 dias  ate  hoje - 45 dias
  Periodo 2: hoje - 44 dias  ate  hoje

Status   : conforme selecao padrao
Tipo     : todos marcados, exceto DEVOLUCAO/REVERSA e SNAC DEVOLUCAO
Viagem   : Todas
Saida    : outputs/pendencias/AAAA-MM-DD/
  - pendencias_p1_AAAAMMDD.xlsx  (periodo 1)
  - pendencias_p2_AAAAMMDD.xlsx  (periodo 2)
  - pendencias_consolidado_AAAAMMDD.xlsx

Uso:
    py baixar_pendencias.py
"""

import asyncio
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Garante saida UTF-8 no terminal Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# ── Credenciais ───────────────────────────────────────────────────────────────
# Lidas automaticamente de um arquivo .env ao lado deste script (NUNCA no codigo,
# NUNCA no Git — o .env esta no .gitignore). Tambem aceita variaveis de ambiente.
#
# Crie um arquivo .env com:
#   DIASLOG_USUARIO=seu_usuario
#   DIASLOG_SENHA=sua_senha
def _carregar_env():
    """Le o arquivo .env (KEY=VALUE por linha) para os.environ, sem dependencias."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for linha in env_path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave, valor = chave.strip(), valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)  # env do sistema tem prioridade


_carregar_env()

USUARIO = os.environ.get("DIASLOG_USUARIO", "")
SENHA   = os.environ.get("DIASLOG_SENHA",   "")

if not USUARIO or not SENHA:
    raise SystemExit(
        "Credenciais nao encontradas. Crie um arquivo .env ao lado do script com:\n"
        "  DIASLOG_USUARIO=seu_usuario\n"
        "  DIASLOG_SENHA=sua_senha"
    )

# ── URLs ──────────────────────────────────────────────────────────────────────
URL_LOGIN     = "https://sistema.diaslog.com.br/Login"
URL_RELATORIO = "https://sistema.diaslog.com.br/restrito/Consulta_NotasPendentes.aspx"
URL_VIAGENS   = "https://sistema.diaslog.com.br/restrito/Relatorio_ResumoViagens.aspx"

# Resumo de Viagens: aba do Sheet e colunas que NAO sobem (ajudante=PF; setores=baguncado)
VIAGENS_ABA       = "Viagens"
VIAGENS_DESCARTAR = ["Ajudante", "Setores"]

# ── Google Sheets (upload automatico do consolidado) ──────────────────────────
# ID extraido do link compartilhado da planilha.
SHEET_ID        = "12_DwR-eL1fM-Aj77ZSFFxtTpLAC9PeN6FE2EoHTn-RA"
SHEET_ABA       = "Pendencias"  # nome da aba que recebe os dados

_AQUI = Path(__file__).resolve().parent
# Upload via Apps Script Web App (sem Google Cloud / sem service account).
# URL e token ficam no .env (fora do Git):
#   SHEETS_WEBAPP_URL=https://script.google.com/macros/s/.../exec
#   SHEETS_WEBAPP_TOKEN=<segredo>
WEBAPP_URL   = os.environ.get("SHEETS_WEBAPP_URL", "")
WEBAPP_TOKEN = os.environ.get("SHEETS_WEBAPP_TOKEN", "")

# Colunas operacionais enviadas ao Sheet (sem dados pessoais LGPD).
# Tudo que NAO estiver aqui nao sobe — minimiza exposicao de dados.
COLUNAS_UPLOAD = [
    "NF", "Status de Entrega", "Efetividade", "Peso", "Valor NF", "Volumes",
    "Cliente", "Tipo Entrega", "Região", "Cidade", "Filial", "Filial de Entrega",
    "Embarque", "Data Prazo", "Data Bipagem Filial", "Motorista última viagem",
    "Ocorrência", "Subocorrencia", "Nivel de Risco",
]

# ── Periodos (90 dias divididos em dois blocos de ~45 dias) ───────────────────
HOJE = datetime.today()

PERIODOS = [
    {
        "label": "P1",
        "ini": HOJE - timedelta(days=90),
        "fim": HOJE - timedelta(days=45),
    },
    {
        "label": "P2",
        "ini": HOJE - timedelta(days=44),
        "fim": HOJE,
    },
]

# ── Pasta de saida ────────────────────────────────────────────────────────────
PASTA_SAIDA = Path("outputs") / "pendencias" / HOJE.strftime("%Y-%m-%d")

# ── True = sem janela (usar apos estavel); False = browser visivel (debug) ────
HEADLESS = False

# ── Status da Entrega: apenas estes ficam MARCADOS ───────────────────────────
STATUS_MARCAR = {
    "Nao Viajou", "Não Viajou",
    "Em Separacao", "Em Separação",
    "Na Rua",
    "Solicitacao de Destroca", "Solicitação de Destroca",
    "Solicitacao de Reconhecimento", "Solicitação de Reconhecimento",
    "Tentativa de Entrega",
    "Solicitacao de Reentrega", "Solicitação de Reentrega",
    "Aguardando Volumes",
    "Volumes em transferencia", "Volumes em transferência",
    "Solicitacao de Coleta", "Solicitação de Coleta",
    "Atraso na Viagem",
}

# Checkboxes que ficam DESMARCADOS
STATUS_DESMARCAR = {
    # Status da Entrega
    "aguardando retorno do cliente",
    "Concluido", "Concluído",
    "Pre-devolucao", "Pré-devolução",
    "Aguardando retirada do cliente",
    "Ocorrencia de Mercadoria", "Ocorrência de Mercadoria",
    "Nao Embarcado", "Não Embarcado",
    "Devolucao", "Devolução",
    "Falha de arquivo EDI",
    "Coleta Efetuada",
    "Volumes em transferencia para devolucao", "Volumes em transferência para devolução",
    "Parado no Retido",
    # Filtros extras
    "Somente entregas rapidas", "Somente entregas rápidas",
    "Somente cidades calendarizadas",
    "Somente notas sem setor",
    "Somente TopSellers",
    "Somente primeiro pedido",
    "Somente CNs destaque",
}

# Tipo de Entrega: apenas estes ficam DESMARCADOS
TIPOS_DESMARCAR = {
    "DEVOLUCAO/REVERSA",
    "SNAC DEVOLUCAO",
}


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def texto_normalizado(t: str) -> str:
    return " ".join(t.lower().split())


def corresponde(texto: str, conjunto: set) -> bool:
    t = texto_normalizado(texto)
    return any(texto_normalizado(s) in t or t in texto_normalizado(s) for s in conjunto)


async def fazer_login(page):
    log("Acessando pagina de login...")
    await page.goto(URL_LOGIN, wait_until="networkidle", timeout=30_000)
    await page.locator(
        "input[type='text'], input[name*='user' i], input[id*='user' i], input[id*='login' i]"
    ).first.fill(USUARIO)
    await page.locator("input[type='password']").first.fill(SENHA)
    await page.locator("a:has-text('Entrar'), input[type='submit'], button[type='submit']").first.click()
    await page.wait_for_load_state("networkidle", timeout=30_000)
    log("Login realizado.")


async def preencher_datas(page, data_ini: str, data_fim: str):
    """Preenche Data Embarque Inicial/Final. Prazo de Entrega fica vazio."""
    log(f"Preenchendo datas: {data_ini} ate {data_fim}")
    inputs = await page.locator("input[type='text']:visible").all()
    if len(inputs) < 4:
        raise RuntimeError(f"Esperava 4 campos de data, encontrou {len(inputs)}.")
    # DOM: [0,1] = Prazo de Entrega, [2,3] = Data Embarque
    await inputs[0].fill("")
    await inputs[1].fill("")
    await inputs[2].fill(data_ini)
    await inputs[3].fill(data_fim)
    log("Datas preenchidas.")


async def _texto_checkbox(cb) -> str:
    return await cb.evaluate("""el => {
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.innerText.trim();
        }
        if (el.labels && el.labels.length) return el.labels[0].innerText.trim();
        let sib = el.nextSibling;
        while (sib) {
            if (sib.textContent && sib.textContent.trim()) return sib.textContent.trim();
            sib = sib.nextSibling;
        }
        return el.parentElement ? el.parentElement.innerText.trim() : '';
    }""")


async def configurar_checkboxes(page):
    log("Configurando checkboxes...")
    checkboxes = await page.locator("input[type='checkbox']").all()
    marcados = desmarcados = ignorados = 0
    for cb in checkboxes:
        texto = await _texto_checkbox(cb)
        esta_marcado = await cb.is_checked()
        if corresponde(texto, STATUS_MARCAR):
            if not esta_marcado:
                await cb.check()
                marcados += 1
        elif corresponde(texto, STATUS_DESMARCAR):
            if esta_marcado:
                await cb.uncheck()
                desmarcados += 1
        elif corresponde(texto, TIPOS_DESMARCAR):
            if esta_marcado:
                await cb.uncheck()
                desmarcados += 1
        else:
            ignorados += 1
    log(f"Checkboxes: {marcados} marcados, {desmarcados} desmarcados, {ignorados} sem alteracao.")


async def selecionar_todos_listboxes(page):
    total = await page.evaluate("""() => {
        const selects = document.querySelectorAll('select[multiple], select[size]');
        let count = 0;
        selects.forEach(sel => {
            for (const opt of sel.options) opt.selected = true;
            count += sel.options.length;
        });
        return count;
    }""")
    log(f"Listboxes: {total} itens selecionados (clientes + filiais).")


async def configurar_filtros_extras(page):
    log("Configurando filtros extras...")

    # SPP = Todos
    spp = page.locator("select").filter(has_text="Todos")
    if await spp.count() > 0:
        await spp.first.select_option(label="Todos")

    # Dados de Coleta = Minuta / Manifesto
    for sel in await page.locator("select").all():
        opts = await sel.evaluate("el => Array.from(el.options).map(o => o.text.trim())")
        if any("minuta" in o.lower() for o in opts):
            await sel.select_option(label="Minuta / Manifesto")
            break

    # Entregas especiais e GR: "Todas as Entregas"
    for radio in await page.locator("input[type='radio']").all():
        texto = await radio.evaluate("""el => {
            let sib = el.nextSibling;
            while (sib) {
                if (sib.textContent && sib.textContent.trim()) return sib.textContent.trim();
                sib = sib.nextSibling;
            }
            return '';
        }""")
        if texto.strip().lower() == "todas as entregas":
            if not await radio.is_checked():
                await radio.check()

    log("Filtros extras configurados.")


async def selecionar_viagem_todas(page):
    for radio in await page.locator("input[type='radio']").all():
        valor = (await radio.get_attribute("value") or "").lower()
        texto = await radio.evaluate("el => el.nextSibling ? el.nextSibling.textContent.trim() : ''")
        if "todas" in valor or "todas" in texto.lower():
            if not await radio.is_checked():
                await radio.check()
            break


async def selecionar_nota_a_nota_excel(page):
    for radio in await page.locator("input[type='radio']").all():
        texto = await radio.evaluate("""el => {
            let sib = el.nextSibling;
            while (sib) {
                if (sib.textContent && sib.textContent.trim()) return sib.textContent.trim();
                sib = sib.nextSibling;
            }
            return el.parentElement ? el.parentElement.innerText.trim() : '';
        }""")
        if "nota a nota para excel" in texto.lower():
            if not await radio.is_checked():
                await radio.check()
            log("Tipo de emissao: 'Nota a Nota para excel' selecionado.")
            return
    log("AVISO: radio 'Nota a Nota para excel' nao encontrado.")


async def emitir_e_baixar(page, nome_destino: str) -> Path:
    log("Clicando em 'Emitir Relatorio'...")
    seletores = [
        "input[value='Emitir Relatório']:not(.dropdown-item)",
        "input[value='Emitir Relatorio']:not(.dropdown-item)",
        "button:not(.dropdown-item) >> text=Emitir Relatório",
        "button:not(.dropdown-item) >> text=Emitir Relatorio",
        "form input[type='submit']:visible",
        "form input[type='button']:visible",
    ]
    botao = None
    for sel in seletores:
        loc = page.locator(sel)
        if await loc.count() > 0:
            botao = loc.first
            valor = (await botao.get_attribute("value") or await botao.inner_text()).strip()
            log(f"Botao encontrado: '{valor}'")
            break
    if botao is None:
        raise RuntimeError("Botao 'Emitir Relatorio' nao encontrado.")

    async with page.expect_download(timeout=120_000) as dl_info:
        await botao.click()

    download = await dl_info.value
    destino = PASTA_SAIDA / nome_destino
    await download.save_as(destino)
    log(f"Arquivo salvo: {destino.name}")
    return destino


async def baixar_periodo(page, periodo: dict) -> Path:
    """Navega ao formulario, preenche um periodo e baixa o arquivo."""
    label = periodo["label"]
    data_ini = periodo["ini"].strftime("%d/%m/%Y")
    data_fim = periodo["fim"].strftime("%d/%m/%Y")

    log(f"--- {label}: {data_ini} ate {data_fim} ---")
    await page.goto(URL_RELATORIO, wait_until="networkidle", timeout=30_000)

    await preencher_datas(page, data_ini, data_fim)
    await selecionar_todos_listboxes(page)
    await configurar_filtros_extras(page)
    await configurar_checkboxes(page)
    await selecionar_viagem_todas(page)
    await selecionar_nota_a_nota_excel(page)

    nome = f"pendencias_{label.lower()}_{HOJE:%Y%m%d}.xlsx"
    return await emitir_e_baixar(page, nome)


def _detectar_linha_header(arq: Path) -> int:
    """Acha a linha do cabecalho procurando a celula 'NF' (varia entre 3 e 7)."""
    probe = pd.read_excel(arq, engine="openpyxl", header=None, nrows=15)
    for i in range(len(probe)):
        valores = [str(x).strip() for x in probe.iloc[i].tolist()]
        if "NF" in valores:
            return i
    return 3  # fallback


def consolidar(arquivos: list[Path]) -> Path:
    """Concatena os dois Excel e salva o consolidado sem duplicatas."""
    log("Consolidando arquivos...")
    frames = []
    for arq in arquivos:
        hdr = _detectar_linha_header(arq)
        try:
            df = pd.read_excel(arq, engine="openpyxl", header=hdr)
        except Exception:
            df = pd.read_excel(arq, engine="xlrd", header=hdr)
        df = df.dropna(how="all")  # remove linhas totalmente vazias
        log(f"  {arq.name}: {len(df)} linhas (header linha {hdr})")
        frames.append(df)

    consolidado = pd.concat(frames, ignore_index=True)
    antes = len(consolidado)
    consolidado = consolidado.drop_duplicates()
    depois = len(consolidado)
    if antes != depois:
        log(f"  Duplicatas removidas: {antes - depois}")

    destino = PASTA_SAIDA / f"pendencias_consolidado_{HOJE:%Y%m%d}.xlsx"
    consolidado.to_excel(destino, index=False, engine="openpyxl")
    log(f"Consolidado salvo: {destino.name} ({depois} linhas)")
    return destino


def enviar_para_sheets(arquivo_consolidado: Path):
    """Envia o consolidado (so colunas operacionais, sem dados LGPD) ao Google Sheet
    via Apps Script Web App (POST de CSV). Sem Google Cloud / service account."""
    import urllib.request
    import urllib.parse

    if not WEBAPP_URL or not WEBAPP_TOKEN:
        log("AVISO: SHEETS_WEBAPP_URL/TOKEN nao definidos no .env. Upload ignorado.")
        return

    log("Preparando dados para o Google Sheets...")
    df = pd.read_excel(arquivo_consolidado, engine="openpyxl")

    # 1) Mantem apenas colunas operacionais (descarta dados pessoais LGPD)
    cols = [c for c in COLUNAS_UPLOAD if c in df.columns]
    df = df[cols].copy()

    # 2) Datas viram texto ISO; NaN vira vazio
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.where(pd.notna(df), "")

    # 2b) Carimba a data/hora do arquivo consolidado (exibida no dashboard)
    ts = datetime.fromtimestamp(arquivo_consolidado.stat().st_mtime)
    df["Atualizado em"] = ts.strftime("%d/%m/%Y %H:%M")

    # 3) Serializa em CSV e envia via POST (aba alvo + token vao na query string)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    url = WEBAPP_URL + "?" + urllib.parse.urlencode(
        {"token": WEBAPP_TOKEN, "aba": SHEET_ABA})
    req = urllib.request.Request(
        url, data=csv_bytes, method="POST",
        headers={"Content-Type": "text/csv; charset=utf-8"})

    log(f"Enviando {len(df)} linhas x {len(df.columns)} colunas ao Web App...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        retorno = resp.read().decode("utf-8", errors="replace").strip()
    log(f"Resposta do Google Sheets: {retorno}")


async def baixar_resumo_viagens(page, ctx) -> Path | None:
    """Baixa o Relatorio de Resumo de Viagens do dia atual.

    Passos (conforme operacao):
      datas inicial=final=hoje | Tipo de Relatorio=Completo |
      Tipo de Viagem=Normal | Filial=todos | Motorista=todos |
      Cliente=todos | Tipo de Entrega=todos | Gerar Relatorio ->
      abre nova aba -> Exportar para Excel.
    """
    hoje = HOJE.strftime("%d/%m/%Y")
    log(f"--- Resumo de Viagens: {hoje} ---")
    await page.goto(URL_VIAGENS, wait_until="networkidle", timeout=30_000)

    # 1) Datas inicial e final = hoje (primeiros 2 campos de texto visiveis)
    inputs = await page.locator("input[type='text']:visible").all()
    log(f"Campos de texto encontrados: {len(inputs)}")
    if len(inputs) >= 2:
        await inputs[0].fill(hoje)
        await inputs[1].fill(hoje)
    else:
        raise RuntimeError("Nao encontrei os campos de data inicial/final.")

    # 2) Tipo de Relatorio = Completo (radio)
    for radio in await page.locator("input[type='radio']").all():
        txt = await radio.evaluate("""el => {
            if (el.id) { const l=document.querySelector('label[for="'+el.id+'"]');
                         if (l) return l.innerText; }
            return el.parentElement ? el.parentElement.innerText : ''; }""")
        if "completo" in (txt or "").lower():
            if not await radio.is_checked():
                await radio.check()
            log("Tipo de Relatorio: Completo")
            break

    # 3) Tipo de Viagem: Normal marcado, Repasse desmarcado
    for cb in await page.locator("input[type='checkbox']").all():
        txt = (await _texto_checkbox(cb) or "").lower()
        if "normal" in txt and not await cb.is_checked():
            await cb.check()
        elif "repasse" in txt and await cb.is_checked():
            await cb.uncheck()

    # 4) Filial e Motorista ja vem como "todos" por padrao — nao mexe.

    # 5) Cliente + Tipo de Entrega = TODOS (listboxes multi-selecao)
    #    Seleciona todas as opcoes de cada <select multiple>/<select size> e
    #    dispara 'change' (ASP.NET registra a selecao). Retorna contagem por lista.
    counts = await page.evaluate("""() => {
        const sels = document.querySelectorAll('select[multiple], select[size]');
        const r = [];
        sels.forEach(sel => {
            let n = 0;
            for (const opt of sel.options) { opt.selected = true; n++; }
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            r.push(n);
        });
        return r;
    }""")
    log(f"Listas multi-selecao marcadas (itens por lista): {counts}")
    if not counts:
        log("AVISO: nenhuma lista multi-selecao encontrada (Cliente/Tipo Entrega).")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(PASTA_SAIDA / "viagens_form.png"))

    # 6) Gerar Relatorio: o link é o ÍCONE ao lado do texto. Localiza o elemento
    #    clicavel (img/a/input) proximo ao texto "Gerar Relatorio" e marca com id.
    marcado = await page.evaluate("""() => {
        const xp = document.evaluate(
            "//*[contains(normalize-space(.),'Gerar Relat')]",
            document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        if (!xp.snapshotLength) return 'sem-texto';
        const node = xp.snapshotItem(xp.snapshotLength - 1);  // mais especifico
        const cont = node.closest('td, div, span, p, a') || node.parentElement;
        let alvo = cont.querySelector("a, img, input[type='image']")
                 || node.previousElementSibling || node;
        alvo.id = '__gerar_btn';
        return alvo.tagName + (alvo.onclick ? '(onclick)' : '');
    }""")
    log(f"Alvo do 'Gerar Relatorio': {marcado}")
    if marcado == "sem-texto":
        raise RuntimeError("Texto 'Gerar Relatorio' nao encontrado na pagina.")

    log("Aguardando a nova aba do relatorio abrir (pode demorar ate 3 min)...")
    try:
        async with ctx.expect_page(timeout=180_000) as nova_aba_info:
            await page.locator("#__gerar_btn").click()
        aba = await nova_aba_info.value
        log("Relatorio abriu em nova aba.")
    except PWTimeout:
        log("Nova aba nao abriu em 3 min; tentando na propria pagina.")
        aba = page
    try:
        await aba.wait_for_load_state("domcontentloaded", timeout=60_000)
    except PWTimeout:
        pass

    # 7) Exportar para o excel -> download. Espera o botao aparecer (sem networkidle).
    botao = aba.locator(
        "input[value*='Exportar' i], button:has-text('Exportar'), "
        "a:has-text('Exportar'), [id*='export' i], "
        "input[value*='Excel' i], button:has-text('Excel')")
    log("Aguardando o botao 'Exportar para o excel'...")
    await botao.first.wait_for(state="visible", timeout=120_000)
    log("Botao visivel; exportando...")
    async with aba.expect_download(timeout=120_000) as dl_info:
        await botao.first.click()
    download = await dl_info.value
    destino = PASTA_SAIDA / f"resumo_viagens_{HOJE:%Y%m%d}.xlsx"
    await download.save_as(destino)
    log(f"Resumo de Viagens salvo: {destino.name}")
    return destino


def _detectar_header_viagens(arq: Path) -> int:
    probe = pd.read_excel(arq, engine="openpyxl", header=None, nrows=15)
    for i in range(len(probe)):
        if "Motorista" in [str(x).strip() for x in probe.iloc[i].tolist()]:
            return i
    return 7


def enviar_viagens_para_sheets(arquivo: Path):
    """Envia o Resumo de Viagens para a aba 'Viagens' do Sheet (mesmo Web App)."""
    import urllib.request
    import urllib.parse

    if not WEBAPP_URL or not WEBAPP_TOKEN:
        log("AVISO: SHEETS_WEBAPP_URL/TOKEN nao definidos. Upload de viagens ignorado.")
        return

    hdr = _detectar_header_viagens(arquivo)
    df = pd.read_excel(arquivo, engine="openpyxl", header=hdr).dropna(how="all")
    df = df[df["Motorista"].notna()].copy()
    df = df.drop(columns=[c for c in VIAGENS_DESCARTAR if c in df.columns])

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    df = df.where(pd.notna(df), "")
    ts = datetime.fromtimestamp(arquivo.stat().st_mtime)
    df["Atualizado em"] = ts.strftime("%d/%m/%Y %H:%M")

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    url = WEBAPP_URL + "?" + urllib.parse.urlencode(
        {"token": WEBAPP_TOKEN, "aba": VIAGENS_ABA})
    req = urllib.request.Request(url, data=csv_bytes, method="POST",
                                 headers={"Content-Type": "text/csv; charset=utf-8"})
    log(f"Enviando {len(df)} linhas de viagens ao Web App (aba '{VIAGENS_ABA}')...")
    with urllib.request.urlopen(req, timeout=180) as resp:
        log(f"Resposta (viagens): {resp.read().decode('utf-8', errors='replace').strip()}")


async def main():
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    log("=" * 55)
    log("Relatorio de Pendencias - Diaslog (90 dias)")
    for p in PERIODOS:
        log(f"  {p['label']}: {p['ini']:%d/%m/%Y} ate {p['fim']:%d/%m/%Y}")
    log(f"Destino: {PASTA_SAIDA.resolve()}")
    log("=" * 55)

    arquivos_baixados: list[Path] = []
    arquivo_viagens: Path | None = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="msedge", headless=HEADLESS)
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()

        try:
            await fazer_login(page)

            for periodo in PERIODOS:
                arq = await baixar_periodo(page, periodo)
                arquivos_baixados.append(arq)

            # Resumo de Viagens (nao interrompe o fluxo se falhar)
            try:
                arquivo_viagens = await baixar_resumo_viagens(page, ctx)
            except Exception as e:
                log(f"AVISO: falha ao baixar Resumo de Viagens: {e}")
                await page.screenshot(path=str(PASTA_SAIDA / "erro_viagens.png"))

        except PWTimeout as e:
            log(f"TIMEOUT: {e}")
            await page.screenshot(path=str(PASTA_SAIDA / "erro_timeout.png"))
            raise
        except Exception as e:
            log(f"ERRO: {e}")
            await page.screenshot(path=str(PASTA_SAIDA / "erro.png"))
            raise
        finally:
            await browser.close()

    if len(arquivos_baixados) == 2:
        consolidado = consolidar(arquivos_baixados)
        try:
            enviar_para_sheets(consolidado)
        except Exception as e:
            log(f"AVISO: falha ao enviar pendencias para o Google Sheets: {e}")
            log("       O consolidado local foi salvo normalmente.")

    if arquivo_viagens is not None:
        try:
            enviar_viagens_para_sheets(arquivo_viagens)
        except Exception as e:
            log(f"AVISO: falha ao enviar viagens para o Google Sheets: {e}")

    log("Concluido.")


if __name__ == "__main__":
    asyncio.run(main())
