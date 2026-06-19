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

# ── Credenciais (defina nas variaveis de ambiente, NUNCA no codigo) ───────────
#   PowerShell:  $env:DIASLOG_USUARIO="seu_usuario"; $env:DIASLOG_SENHA="sua_senha"
USUARIO = os.environ.get("DIASLOG_USUARIO", "")
SENHA   = os.environ.get("DIASLOG_SENHA",   "")

if not USUARIO or not SENHA:
    raise SystemExit(
        "Defina as credenciais nas variaveis de ambiente:\n"
        '  $env:DIASLOG_USUARIO="seu_usuario"\n'
        '  $env:DIASLOG_SENHA="sua_senha"'
    )

# ── URLs ──────────────────────────────────────────────────────────────────────
URL_LOGIN     = "https://sistema.diaslog.com.br/Login"
URL_RELATORIO = "https://sistema.diaslog.com.br/restrito/Consulta_NotasPendentes.aspx"

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


async def main():
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    log("=" * 55)
    log("Relatorio de Pendencias - Diaslog (90 dias)")
    for p in PERIODOS:
        log(f"  {p['label']}: {p['ini']:%d/%m/%Y} ate {p['fim']:%d/%m/%Y}")
    log(f"Destino: {PASTA_SAIDA.resolve()}")
    log("=" * 55)

    arquivos_baixados: list[Path] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="msedge", headless=HEADLESS)
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()

        try:
            await fazer_login(page)

            for periodo in PERIODOS:
                arq = await baixar_periodo(page, periodo)
                arquivos_baixados.append(arq)

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
        consolidar(arquivos_baixados)

    log("Concluido.")


if __name__ == "__main__":
    asyncio.run(main())
