"""
Dias+ | Central de Indicadores — Pendências Operacionais
Dashboard Streamlit com leitura robusta do relatório de Notas Pendentes.
"""

import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Central de Indicadores | Dias+",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta Dias+ ──────────────────────────────────────────────────────────────
TEAL   = "#2DC5B4"
DEEP   = "#0E7A8C"
SALMON = "#C47A77"
AMBER  = "#E8C77A"
GREEN  = "#5BC48A"
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68",
          "#7FBFCC", SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]
FONT   = "Barlow Condensed, Arial Narrow, sans-serif"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp, p, div, label, span:not([data-testid]) {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
}

/* Conteúdo principal SEM max-width fixo (deixa o Streamlit controlar) */
.block-container { padding: 1.2rem 2rem 2rem !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #09293A !important;
    border-right: 1px solid rgba(45,197,180,.25) !important;
}
[data-testid="stSidebar"] label {
    font-size: 14px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .05em;
    color: rgba(255,255,255,.8) !important;
}

/* Botão colapso sidebar — ícones ASCII (não depende de Material Icons) */
button[data-testid="stSidebarCollapseButton"] span,
button[data-testid="stBaseButton-headerNoPadding"] span {
    visibility: hidden !important; width: 0 !important;
}
button[data-testid="stSidebarCollapseButton"]::before,
button[data-testid="stBaseButton-headerNoPadding"]::before {
    content: "◀"; visibility: visible; font-size: 14px; color: #2DC5B4;
}
[data-testid="stSidebarCollapsedControl"] button::before {
    content: "▶"; visibility: visible; font-size: 14px; color: #2DC5B4;
}
[data-testid="stSidebarCollapsedControl"] button span {
    visibility: hidden !important; width: 0 !important;
}

/* KPI cards */
[data-testid="metric-container"] {
    background: rgba(45,197,180,.09) !important;
    border: 1px solid rgba(45,197,180,.32) !important;
    border-radius: 14px !important; padding: 16px 18px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 13px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .06em;
    color: rgba(255,255,255,.65) !important;
}
[data-testid="stMetricValue"] {
    font-size: 38px !important; font-weight: 900 !important;
    color: #2DC5B4 !important; font-variant-numeric: tabular-nums;
    line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 14px !important; }

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 15px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .03em; padding: 9px 16px !important;
}
[data-testid="stTabs"] [aria-selected="true"] { color: #2DC5B4 !important; }

/* Títulos de seção */
.sec {
    font-size: 20px !important; font-weight: 900; color: #fff;
    text-transform: uppercase; letter-spacing: .06em;
    border-left: 5px solid #2DC5B4; padding-left: 12px; margin: 24px 0 14px;
}
.fbadge {
    background: rgba(45,197,180,.12); border: 1px solid rgba(45,197,180,.35);
    border-radius: 8px; padding: 8px 14px; font-size: 14px;
    color: rgba(255,255,255,.75); margin-bottom: 8px;
}
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ────────────────────────────────────────────────────────────────
# LGPD: remove dados pessoais do destinatário antes de qualquer exibição/export
LGPD_REMOVE = ["Destinatário", "Endereço", "Bairro", "Telefone",
               "CEP Destinatário", "Obs Entrega", "Cód Destinatário"]
DATE_COLS   = ["Data Pedido", "Data Emissão NF", "Embarque", "Data Prazo",
               "Data Prazo cliente", "Data última viagem", "Data ocorrência",
               "Data Registro Ocorrencia", "Data Primeira Bipagem",
               "Data Bipagem Filial", "Prazo Efetividade"]
NUM_COLS    = ["Peso", "Valor NF", "Volumes"]
MAPA_RISCO  = {0: "Sem risco GR", 1: "Risco baixo", 2: "Risco médio", 3: "Risco alto"}

# Filiais reais seguem o padrão "UF + cidade" (ex: "SP CAMPINAS", "RJ DUQUE").
# A coluna Filial vem contaminada com clientes (FISIA, CENTAURO...) e parceiros
# (PARCEIRO PATINI, R2 EXPRESS) — esses NÃO têm prefixo de UF e são descartados.
UF_BR = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
         "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
         "SP", "SE", "TO"}


def _eh_filial(nome) -> bool:
    """True se o valor parece uma filial real (começa com sigla de UF + espaço)."""
    if not isinstance(nome, str):
        return False
    partes = nome.strip().split()
    return len(partes) >= 2 and partes[0].upper() in UF_BR

# ── Fonte de dados padrão: Google Sheet público (alimentado pelo download) ────
SHEET_ID  = "12_DwR-eL1fM-Aj77ZSFFxtTpLAC9PeN6FE2EoHTn-RA"
SHEET_ABA = "Pendencias"
SHEET_CSV = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
             f"/gviz/tq?tqx=out:csv&sheet={SHEET_ABA}")


def _processar(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica limpeza, tipagem e métricas (SLA, aging, risco) sobre o DataFrame bruto."""
    # Mantém só linhas com NF numérica
    if "NF" in df.columns:
        df = df[pd.to_numeric(df["NF"], errors="coerce").notna()].copy()

    # LGPD — remove dados pessoais (redundante se a fonte já vem limpa)
    df = df.drop(columns=[c for c in LGPD_REMOVE if c in df.columns])

    # Limpa strings com padding e tipa colunas
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": None, "": None})
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    hoje = pd.Timestamp.today().normalize()

    # 5) SLA — usa a verdade do sistema (Efetividade); senão calcula por prazo
    if "Efetividade" in df.columns:
        df["Atrasado"] = df["Efetividade"].str.lower().eq("atrasado")
    elif "Data Prazo" in df.columns:
        df["Atrasado"] = df["Data Prazo"].notna() & (df["Data Prazo"] < hoje)
    else:
        df["Atrasado"] = False

    if "Data Prazo" in df.columns:
        df["Dias Atraso"] = (hoje - df["Data Prazo"]).dt.days.clip(lower=0)
        df.loc[~df["Atrasado"], "Dias Atraso"] = 0
    else:
        df["Dias Atraso"] = 0

    # 6) Aging — tempo parado na filial desde a bipagem
    if "Data Bipagem Filial" in df.columns:
        df["Dias Parado"] = (hoje - df["Data Bipagem Filial"]).dt.days.clip(lower=0)
    elif "Embarque" in df.columns:
        df["Dias Parado"] = (hoje - df["Embarque"]).dt.days.clip(lower=0)
    else:
        df["Dias Parado"] = 0

    # 7) Nível de risco legível
    if "Nivel de Risco" in df.columns:
        df["Risco GR"] = (pd.to_numeric(df["Nivel de Risco"], errors="coerce")
                          .map(MAPA_RISCO).fillna("Não classificado"))

    # 8) Transportadora (motorista da última viagem)
    if "Motorista última viagem" in df.columns:
        df["Transportadora"] = df["Motorista última viagem"].fillna("Sem transportadora")

    # 9) Separa filial real (UF + cidade) de clientes/parceiros contaminando a coluna
    if "Filial" in df.columns:
        df["É Filial"] = df["Filial"].map(_eh_filial)
    if "Filial de Entrega" in df.columns:
        df["É FilialEnt"] = df["Filial de Entrega"].map(_eh_filial)

    return df


@st.cache_data(show_spinner="Carregando do Google Sheets...", ttl=600)
def carregar_sheets(url: str) -> pd.DataFrame:
    """Lê a planilha pública (CSV) e processa. Cache de 10 min."""
    df = pd.read_csv(url)
    return _processar(df)


@st.cache_data(show_spinner="Carregando arquivo...")
def carregar(key: str, data: bytes) -> pd.DataFrame:
    """Lê um Excel enviado manualmente (detecta a linha do cabeçalho)."""
    raw = io.BytesIO(data)
    probe = pd.read_excel(raw, header=None, nrows=15, engine="openpyxl")
    hdr = 0
    for i in range(len(probe)):
        if "NF" in [str(x).strip() for x in probe.iloc[i].tolist()]:
            hdr = i
            break
    raw.seek(0)
    df = pd.read_excel(raw, header=hdr, engine="openpyxl").dropna(how="all")
    return _processar(df)


def encontrar_local() -> Path | None:
    for p in ["outputs/pendencias/**/*consolidado*.xlsx", "data/*.xlsx",
              "RelatorioNotasPendentes*.xlsx"]:
        hits = sorted(Path(".").glob(p), reverse=True)
        if hits:
            return hits[0]
    return None


# ── Helpers de gráfico ────────────────────────────────────────────────────────
def fmt(fig: go.Figure, h: int = 420, legend_h: bool = False) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color="#FFFFFF", size=15),
        title_font=dict(family=FONT, color="#FFFFFF", size=18),
        margin=dict(l=12, r=160, t=50, b=12), height=h,
        uniformtext_minsize=12, uniformtext_mode="hide",
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=14),
                    orientation="h" if legend_h else "v",
                    y=1.12 if legend_h else 1),
        coloraxis_colorbar=dict(thickness=16, len=0.7,
            tickfont=dict(size=13, color="#FFFFFF"),
            title=dict(font=dict(size=13, color="#FFFFFF")),
            bgcolor="rgba(0,0,0,0)", outlinewidth=0),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.1)",
        zerolinecolor="rgba(255,255,255,.18)",
        tickfont=dict(size=14), title_font=dict(size=15))
    fig.update_yaxes(gridcolor="rgba(255,255,255,.1)",
        zerolinecolor="rgba(255,255,255,.18)",
        tickfont=dict(size=15), title_font=dict(size=15), automargin=True)
    return fig


def barh(df_plot, x, y, title, h=None, text_col=None, color_col=None,
         scale=None, color_fixed=None, cbar_title=""):
    if scale is None:
        scale = [[0, DEEP], [1, TEAL]]
    if color_fixed is None:
        kw = dict(color=color_col or x, color_continuous_scale=scale)
    else:
        kw = dict(color_discrete_sequence=[color_fixed])
    fig = px.bar(df_plot, x=x, y=y, orientation="h", title=title,
                 text=text_col, **kw)
    fig.update_traces(marker_line_width=0, textposition="outside",
                      textfont=dict(size=15, family=FONT))
    fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                      xaxis_title="", yaxis_title="")
    f = fmt(fig, h or max(380, len(df_plot) * 34))
    f.update_layout(coloraxis_showscale=color_fixed is None,
                    coloraxis_colorbar_title=cbar_title)
    return f


def lbl_int(s):  return s.apply(lambda x: f"{x:,.0f}")
def lbl_pct(s):  return s.apply(lambda x: f"{x:.1f}%")
def lbl_rs(s):
    return s.apply(lambda x: f"R$ {x/1e6:.2f}M" if x >= 1e6
                   else (f"R$ {x/1e3:.0f}k" if x >= 1000 else f"R$ {x:,.0f}"))


# ── Header (preenchido após carregar os dados, com a data do consolidado) ─────
def _header_html(atualizado: str) -> str:
    return f"""
<div style="background:linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
            border-radius:16px;padding:24px 38px;margin-bottom:18px;
            border:1px solid rgba(45,197,180,.4)">
  <div style="font-size:clamp(26px,3.4vw,48px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05;
              font-family:'Barlow Condensed',sans-serif">
    CENTRAL DE <span style="color:{TEAL}">INDICADORES</span>
  </div>
  <div style="font-size:15px;color:rgba(255,255,255,.55);margin-top:4px;
              font-family:'Barlow Condensed',sans-serif">
    Dias+ &nbsp;·&nbsp; Pendências Operacionais &nbsp;·&nbsp;
    🔄 Dados atualizados em <b style="color:{TEAL}">{atualizado}</b>
  </div>
</div>"""

cabecalho = st.empty()

# ── Sidebar: dados ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""<div style="font-family:'Barlow Condensed',sans-serif;
        font-size:24px;font-weight:900;color:{TEAL};text-transform:uppercase;
        letter-spacing:.06em;padding:4px 0 2px">🔍 FILTROS</div>""",
        unsafe_allow_html=True)
    st.divider()

    fonte = st.radio("Fonte dos dados",
                     ["☁️ Google Sheets (automático)", "📤 Enviar arquivo"],
                     label_visibility="collapsed")
    upload = None
    if fonte == "📤 Enviar arquivo":
        upload = st.file_uploader("Carregar arquivo (.xlsx)", type=["xlsx"])

# Carrega conforme a fonte escolhida
df_raw = None
if fonte == "☁️ Google Sheets (automático)":
    try:
        df_raw = carregar_sheets(SHEET_CSV)
        with st.sidebar:
            st.success(f"☁️ Google Sheets · {len(df_raw):,} NFs")
    except Exception as e:
        with st.sidebar:
            st.error("Não consegui ler o Google Sheets. Verifique se a planilha "
                     "está compartilhada como 'qualquer um com o link'.")
            st.caption(f"Detalhe: {e}")
        st.stop()
else:
    if upload is None:
        st.info("👈 Envie o relatório de Notas Pendentes (.xlsx) na barra lateral.")
        st.stop()
    df_raw = carregar(upload.name, upload.read())
    with st.sidebar:
        st.success(f"📂 {upload.name} · {len(df_raw):,} NFs")

# Data/hora do consolidado (carimbada no upload). Fallback: não informado.
_atualizado = "não informado"
if "Atualizado em" in df_raw.columns and df_raw["Atualizado em"].notna().any():
    _ts = pd.to_datetime(df_raw["Atualizado em"].dropna().iloc[0],
                         errors="coerce", dayfirst=True)
    _atualizado = _ts.strftime("%d/%m/%Y %H:%M") if pd.notna(_ts) \
                  else str(df_raw["Atualizado em"].dropna().iloc[0])
cabecalho.markdown(_header_html(_atualizado), unsafe_allow_html=True)

# ── Sidebar: filtros ──────────────────────────────────────────────────────────
def ms(label, col, only=None):
    if col not in df_raw.columns:
        return []
    vals = df_raw[col].dropna().unique()
    if only is not None:
        vals = [v for v in vals if only(v)]
    opts = sorted(vals)
    return st.multiselect(label, opts, placeholder="Todos",
                          label_visibility="visible") if opts else []

with st.sidebar:
    st.markdown("**📅 Período de Embarque**")
    if "Embarque" in df_raw.columns and df_raw["Embarque"].notna().any():
        datas = df_raw["Embarque"].dropna()
        d_min, d_max = datas.min().date(), datas.max().date()
        intervalo = st.date_input("", value=(d_min, d_max), min_value=d_min,
                                  max_value=d_max, label_visibility="collapsed")
        data_ini = intervalo[0] if len(intervalo) > 0 else d_min
        data_fim = intervalo[1] if len(intervalo) > 1 else d_max
    else:
        data_ini = data_fim = None

    sel_filiais = ms("🏢 Filial", "Filial", only=_eh_filial)
    sel_fe      = ms("🚚 Filial de Entrega", "Filial de Entrega", only=_eh_filial)
    sel_transp  = ms("🚛 Transportadora", "Transportadora")
    sel_cli     = ms("👤 Cliente", "Cliente")
    sel_status  = ms("📦 Status de Entrega", "Status de Entrega")
    sel_tipo    = ms("🔖 Tipo de Entrega", "Tipo Entrega")
    sel_risco   = ms("🛡️ Risco GR", "Risco GR")

    st.divider()
    so_atraso = st.toggle("⚠️ Somente em atraso", value=False)
    st.divider()
    st.caption("diaslog.com.br")

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()
if data_ini and data_fim and "Embarque" in df.columns:
    d0, d1 = pd.Timestamp(data_ini), pd.Timestamp(data_fim)
    df = df[df["Embarque"].isna() | ((df["Embarque"] >= d0) & (df["Embarque"] <= d1))]

def f(df, col, sel):
    return df[df[col].isin(sel)] if sel and col in df.columns else df

df = f(df, "Filial", sel_filiais)
df = f(df, "Filial de Entrega", sel_fe)
df = f(df, "Transportadora", sel_transp)
df = f(df, "Cliente", sel_cli)
df = f(df, "Status de Entrega", sel_status)
df = f(df, "Tipo Entrega", sel_tipo)
df = f(df, "Risco GR", sel_risco)
if so_atraso:
    df = df[df["Atrasado"]]

ativos = []
if sel_filiais: ativos.append(f"Filial: {len(sel_filiais)}")
if sel_fe:      ativos.append(f"Fil.Entrega: {len(sel_fe)}")
if sel_transp:  ativos.append(f"Transp.: {len(sel_transp)}")
if sel_cli:     ativos.append(f"Cliente: {len(sel_cli)}")
if sel_status:  ativos.append(f"Status: {len(sel_status)}")
if sel_tipo:    ativos.append(f"Tipo: {len(sel_tipo)}")
if sel_risco:   ativos.append(f"Risco: {len(sel_risco)}")
if so_atraso:   ativos.append("⚠️ só atraso")
if ativos:
    st.markdown("<div class='fbadge'>🔍 " + "  |  ".join(ativos) + "</div>",
                unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total   = len(df)
atraso  = int(df["Atrasado"].sum())
pct_at  = atraso / total * 100 if total else 0
valor_risco = df.loc[df["Atrasado"], "Valor NF"].sum() if "Valor NF" in df.columns else 0
parado7 = int((df["Dias Parado"] > 7).sum())
n_transp = df.loc[df["Transportadora"] != "Sem transportadora", "Transportadora"].nunique() \
           if "Transportadora" in df.columns else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes", f"{total:,.0f}")
k2.metric("Em Atraso", f"{atraso:,.0f}", delta=f"{pct_at:.1f}% do total",
          delta_color="inverse")
k3.metric("Valor em Risco", f"R$ {valor_risco/1e6:.2f}M" if valor_risco >= 1e6
          else f"R$ {valor_risco:,.0f}")
k4.metric("Parado +7 dias", f"{parado7:,.0f}", delta="na filial", delta_color="off")
k5.metric("Transportadoras", f"{n_transp:,.0f}")
st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚦  Resumo Executivo",
    "🏢  Filiais",
    "🚚  Transportadoras",
    "🔎  Causa-Raiz",
    "⏱️  Aging & Risco",
    "👤  Clientes",
    "📋  Dados",
])

# ── TAB 0 — Resumo Executivo ──────────────────────────────────────────────────
with tab0:
    st.markdown('<div class="sec">Semáforo de Filiais</div>', unsafe_allow_html=True)
    if "É Filial" in df.columns and df["É Filial"].any():
        s = df[df["É Filial"]].groupby("Filial").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        s["% Atraso"] = (s["Atraso"] / s["Total"] * 100).round(1)
        s = s.sort_values("% Atraso", ascending=True)
        s["label"] = lbl_pct(s["% Atraso"])
        fig = barh(s, x="% Atraso", y="Filial",
                   title="% de NFs em Atraso por Filial (verde→vermelho)",
                   text_col="label", color_col="% Atraso",
                   scale=[[0, GREEN], [.4, AMBER], [1, SALMON]],
                   cbar_title="% atraso", h=max(440, len(s) * 28))
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sec">Status de Entrega</div>', unsafe_allow_html=True)
        if "Status de Entrega" in df.columns:
            d = df["Status de Entrega"].value_counts().reset_index()
            d.columns = ["Status", "Qtd"]
            d["label"] = lbl_int(d["Qtd"])
            st.plotly_chart(barh(d, "Qtd", "Status", "NFs por Status",
                                 text_col="label", cbar_title="NFs", h=360),
                            use_container_width=True)
    with c2:
        st.markdown('<div class="sec">SLA Geral (Efetividade)</div>', unsafe_allow_html=True)
        no_prazo = total - atraso
        fig = go.Figure(go.Pie(
            labels=["Dentro do Prazo", "Atrasado"], values=[no_prazo, atraso],
            hole=.62, marker=dict(colors=[TEAL, SALMON]),
            textinfo="label+percent", textfont=dict(size=16, family=FONT)))
        fig.update_layout(
            annotations=[dict(text=f"{pct_at:.0f}%<br>atraso", x=.5, y=.5,
                              font=dict(size=26, color="#fff", family=FONT),
                              showarrow=False)],
            showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#fff", family=FONT), height=360,
            margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="sec">Tendência Semanal de Embarque</div>', unsafe_allow_html=True)
    if "Embarque" in df.columns and df["Embarque"].notna().any():
        tmp = df.dropna(subset=["Embarque"]).copy()
        tmp["Semana"] = tmp["Embarque"].dt.to_period("W").dt.start_time
        tr = tmp.groupby("Semana").agg(NFs=("NF", "count"),
                                       Atraso=("Atrasado", "sum")).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=tr["Semana"], y=tr["Atraso"], name="Em Atraso",
                             marker_color=SALMON, marker_line_width=0,
                             opacity=.7, yaxis="y2"))
        fig.add_trace(go.Scatter(x=tr["Semana"], y=tr["NFs"], mode="lines+markers",
                                 name="NFs Pendentes", line=dict(color=TEAL, width=3),
                                 marker=dict(size=7, color=TEAL)))
        fig.update_layout(title="NFs por Semana vs. Em Atraso",
                          yaxis=dict(title="NFs"),
                          yaxis2=dict(title="Atraso", overlaying="y", side="right",
                                      gridcolor="rgba(0,0,0,0)", color=SALMON,
                                      tickfont=dict(color=SALMON, size=13)))
        st.plotly_chart(fmt(fig, 320, legend_h=True), use_container_width=True)

# ── TAB 1 — Filiais ───────────────────────────────────────────────────────────
with tab1:
    if "É Filial" not in df.columns or not df["É Filial"].any():
        st.info("Nenhuma filial (UF + cidade) encontrada no recorte atual.")
    else:
        st.caption("Apenas filiais operacionais da Dias+ (UF + cidade). "
                   "Clientes como FISIA e Centauro ficam na aba 👤 Clientes.")
        d = df[df["É Filial"]].groupby("Filial").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        d["% Atraso"] = (d["Atraso"] / d["Total"] * 100).round(1)

        st.markdown('<div class="sec">NFs por Filial — Total vs. Atraso</div>',
                    unsafe_allow_html=True)
        dd = d.sort_values("Total")
        fig = go.Figure()
        fig.add_trace(go.Bar(y=dd["Filial"], x=dd["Total"], orientation="h",
                             name="Total", marker_color=TEAL, marker_line_width=0,
                             text=lbl_int(dd["Total"]), textposition="outside",
                             textfont=dict(size=14, color="#fff", family=FONT)))
        fig.add_trace(go.Bar(y=dd["Filial"], x=dd["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title="Total NFs vs. Em Atraso",
                          yaxis=dict(categoryorder="total ascending", automargin=True))
        st.plotly_chart(fmt(fig, max(440, len(dd) * 28), legend_h=True),
                        use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="sec">% em Atraso</div>', unsafe_allow_html=True)
            d2 = d.sort_values("% Atraso")
            d2["label"] = lbl_pct(d2["% Atraso"])
            st.plotly_chart(barh(d2, "% Atraso", "Filial", "% de Atraso por Filial",
                                 text_col="label", color_col="% Atraso",
                                 scale=[[0, GREEN], [.4, AMBER], [1, SALMON]],
                                 cbar_title="%", h=max(440, len(d2) * 26)),
                            use_container_width=True)
        with c2:
            st.markdown('<div class="sec">Valor em Aberto</div>', unsafe_allow_html=True)
            d3 = d.sort_values("Valor")
            d3["label"] = lbl_rs(d3["Valor"])
            st.plotly_chart(barh(d3, "Valor", "Filial", "Valor por Filial",
                                 text_col="label", cbar_title="R$",
                                 h=max(440, len(d3) * 26)),
                            use_container_width=True)

# ── TAB 2 — Transportadoras ───────────────────────────────────────────────────
with tab2:
    if "Transportadora" not in df.columns:
        st.info("Coluna de transportadora não disponível neste arquivo.")
    else:
        dft = df[df["Transportadora"] != "Sem transportadora"]
        n = st.slider("Transportadoras exibidas", 10, 40, 20, 5)

        st.markdown('<div class="sec">Top Transportadoras — Volume vs. Atraso</div>',
                    unsafe_allow_html=True)
        t = dft.groupby("Transportadora").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        t["% Atraso"] = (t["Atraso"] / t["Total"] * 100).round(1)
        top = t.sort_values("Total", ascending=True).tail(n)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=top["Transportadora"], x=top["Total"], orientation="h",
                             name="Total", marker_color=TEAL, marker_line_width=0,
                             text=lbl_int(top["Total"]), textposition="outside",
                             textfont=dict(size=13, color="#fff", family=FONT)))
        fig.add_trace(go.Bar(y=top["Transportadora"], x=top["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay",
                          title=f"Top {n} Transportadoras — NFs vs. Atraso",
                          yaxis=dict(categoryorder="total ascending", automargin=True))
        st.plotly_chart(fmt(fig, max(460, n * 28), legend_h=True),
                        use_container_width=True)

        st.markdown('<div class="sec">Piores % de Atraso (mín. 50 NFs)</div>',
                    unsafe_allow_html=True)
        rel = t[t["Total"] >= 50].sort_values("% Atraso").tail(n)
        rel["label"] = lbl_pct(rel["% Atraso"])
        st.plotly_chart(barh(rel, "% Atraso", "Transportadora",
                             f"Transportadoras com maior % de atraso (≥50 NFs)",
                             text_col="label", color_col="% Atraso",
                             scale=[[0, GREEN], [.4, AMBER], [1, SALMON]],
                             cbar_title="%", h=max(440, len(rel) * 28)),
                        use_container_width=True)

# ── TAB 3 — Causa-Raiz ────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="sec">Ocorrências (Pareto)</div>', unsafe_allow_html=True)
    if "Ocorrência" in df.columns and df["Ocorrência"].notna().any():
        o = df["Ocorrência"].dropna().value_counts().head(15).reset_index()
        o.columns = ["Ocorrência", "Qtd"]
        o = o.sort_values("Qtd")
        o["label"] = lbl_int(o["Qtd"])
        st.plotly_chart(barh(o, "Qtd", "Ocorrência", "Top 15 Ocorrências",
                             text_col="label", color_fixed=SALMON,
                             h=max(420, len(o) * 30)),
                        use_container_width=True)
    else:
        st.info("Sem ocorrências registradas no recorte atual.")

    st.markdown('<div class="sec">Subocorrências (motivo detalhado)</div>',
                unsafe_allow_html=True)
    if "Subocorrencia" in df.columns and df["Subocorrencia"].notna().any():
        so = df["Subocorrencia"].dropna().value_counts().head(15).reset_index()
        so.columns = ["Subocorrência", "Qtd"]
        so = so.sort_values("Qtd")
        so["label"] = lbl_int(so["Qtd"])
        st.plotly_chart(barh(so, "Qtd", "Subocorrência", "Top 15 Subocorrências",
                             text_col="label", color_col="Qtd",
                             scale=[[0, AMBER], [1, SALMON]], cbar_title="NFs",
                             h=max(420, len(so) * 30)),
                        use_container_width=True)
    else:
        st.info("Sem subocorrências registradas no recorte atual.")

# ── TAB 4 — Aging & Risco ─────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="sec">Aging — Tempo Parado na Filial</div>',
                unsafe_allow_html=True)
    bins = [-1, 3, 7, 15, 30, float("inf")]
    labels = ["0–3 d", "4–7 d", "8–15 d", "16–30 d", "+30 d"]
    dfa = df.copy()
    dfa["Faixa Aging"] = pd.cut(dfa["Dias Parado"], bins=bins, labels=labels)
    c1, c2 = st.columns(2)
    with c1:
        a = dfa["Faixa Aging"].value_counts().reindex(labels).reset_index()
        a.columns = ["Faixa", "Qtd"]
        a["label"] = a["Qtd"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "0")
        fig = px.bar(a, x="Faixa", y="Qtd", color="Qtd",
                     color_continuous_scale=[[0, TEAL], [.5, AMBER], [1, SALMON]],
                     title="NFs por Faixa de Dias Parado", text="label")
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=15, family=FONT))
        fig.update_layout(xaxis_title="")
        f4 = fmt(fig, 360)
        f4.update_layout(coloraxis_showscale=True, coloraxis_colorbar_title="NFs")
        st.plotly_chart(f4, use_container_width=True)
    with c2:
        av = (dfa.groupby("Faixa Aging", observed=True)
              .agg(Valor=("Valor NF", "sum")).reindex(labels).reset_index())
        av.columns = ["Faixa", "Valor"]
        av["label"] = av["Valor"].apply(
            lambda x: f"R$ {x/1e6:.2f}M" if pd.notna(x) and x >= 1e6
            else (f"R$ {x/1e3:.0f}k" if pd.notna(x) and x >= 1000 else ""))
        fig = px.bar(av, x="Faixa", y="Valor", color_discrete_sequence=[DEEP],
                     title="Valor Parado por Faixa (R$)", text="label")
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=15, family=FONT))
        fig.update_layout(xaxis_title="")
        st.plotly_chart(fmt(fig, 360), use_container_width=True)

    st.markdown('<div class="sec">Exposição por Nível de Risco (GR)</div>',
                unsafe_allow_html=True)
    if "Risco GR" in df.columns:
        r = df.groupby("Risco GR").agg(NFs=("NF", "count"),
                                       Valor=("Valor NF", "sum")).reset_index()
        r = r.sort_values("Valor")
        r["label"] = lbl_rs(r["Valor"])
        st.plotly_chart(barh(r, "Valor", "Risco GR",
                             "Valor em Aberto por Nível de Risco",
                             text_col="label", color_col="Valor",
                             scale=[[0, TEAL], [1, SALMON]], cbar_title="R$", h=320),
                        use_container_width=True)
    else:
        st.info("Coluna de Nível de Risco não disponível.")

# ── TAB 5 — Clientes ──────────────────────────────────────────────────────────
with tab5:
    if "Cliente" not in df.columns:
        st.info("Coluna Cliente não disponível.")
    else:
        st.caption("Clientes da Dias+ (coluna Cliente) — ex.: FISIA, Centauro, "
                   "Boticário, Natura. Separado das filiais operacionais.")
        nmax = max(10, df["Cliente"].nunique())
        n = st.slider("Clientes exibidos", 10, min(50, nmax), min(20, nmax), 5)
        c = df.groupby("Cliente").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        c["% Atraso"] = (c["Atraso"] / c["Total"] * 100).round(1)

        st.markdown('<div class="sec">Top Clientes — Volume vs. Atraso</div>',
                    unsafe_allow_html=True)
        top = c.sort_values("Total", ascending=True).tail(n)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=top["Cliente"], x=top["Total"], orientation="h",
                             name="Total", marker_color=TEAL, marker_line_width=0,
                             text=lbl_int(top["Total"]), textposition="outside",
                             textfont=dict(size=13, color="#fff", family=FONT)))
        fig.add_trace(go.Bar(y=top["Cliente"], x=top["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title=f"Top {n} Clientes",
                          yaxis=dict(categoryorder="total ascending", automargin=True))
        st.plotly_chart(fmt(fig, max(460, n * 28), legend_h=True),
                        use_container_width=True)

        st.markdown('<div class="sec">Valor em Aberto por Cliente</div>',
                    unsafe_allow_html=True)
        cv = c.sort_values("Valor", ascending=True).tail(n)
        cv["label"] = lbl_rs(cv["Valor"])
        st.plotly_chart(barh(cv, "Valor", "Cliente", f"Top {n} — Valor em Aberto",
                             text_col="label", cbar_title="R$",
                             h=max(460, n * 28)),
                        use_container_width=True)

        st.markdown('<div class="sec">% em Atraso por Cliente (mín. 50 NFs)</div>',
                    unsafe_allow_html=True)
        rel = c[c["Total"] >= 50].sort_values("% Atraso", ascending=True).tail(n)
        rel["label"] = lbl_pct(rel["% Atraso"])
        st.plotly_chart(barh(rel, "% Atraso", "Cliente",
                             "Clientes com maior % de atraso (≥50 NFs)",
                             text_col="label", color_col="% Atraso",
                             scale=[[0, GREEN], [.4, AMBER], [1, SALMON]],
                             cbar_title="%", h=max(440, len(rel) * 28)),
                        use_container_width=True)

# ── TAB 6 — Dados ─────────────────────────────────────────────────────────────
with tab6:
    cols_show = [c for c in [
        "NF", "Status de Entrega", "Efetividade", "Filial", "Filial de Entrega",
        "Transportadora", "Cliente", "Tipo Entrega", "Embarque", "Data Prazo",
        "Atrasado", "Dias Atraso", "Dias Parado", "Risco GR", "Peso", "Valor NF",
        "Ocorrência", "Subocorrencia", "Cidade", "Região",
    ] if c in df.columns]

    ci, cd = st.columns([3, 1])
    ci.markdown(f"**{total:,.0f} registros** com os filtros atuais")
    with cd:
        csv = df[cols_show].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Exportar CSV", data=csv,
                           file_name=f"pendencias_{datetime.now():%Y%m%d}.csv",
                           mime="text/csv", use_container_width=True)

    st.dataframe(df[cols_show], use_container_width=True, height=580,
        column_config={
            "Atrasado":     st.column_config.CheckboxColumn("Atrasado"),
            "Dias Atraso":  st.column_config.NumberColumn("Atraso", format="%d d"),
            "Dias Parado":  st.column_config.NumberColumn("Parado", format="%d d"),
            "Embarque":     st.column_config.DateColumn("Embarque", format="DD/MM/YYYY"),
            "Data Prazo":   st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
            "Valor NF":     st.column_config.NumberColumn("Valor NF", format="R$ %.2f"),
            "Peso":         st.column_config.NumberColumn("Peso", format="%.2f kg"),
        })
