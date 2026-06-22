"""
Dias+ | Central de Indicadores — biblioteca compartilhada entre as páginas.
Contém paleta, CSS, helpers de gráfico e carregamento de dados (Pendências e Viagens).
Sem renderização no nível do módulo (exceto a função inject_css()).
"""

import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── Paleta Dias+ ──────────────────────────────────────────────────────────────
TEAL   = "#2DC5B4"
DEEP   = "#0E7A8C"
SALMON = "#C47A77"
AMBER  = "#E8C77A"
GREEN  = "#5BC48A"
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68",
          "#7FBFCC", SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]
FONT   = "Barlow Condensed, Arial Narrow, sans-serif"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp, p, div, label, span:not([data-testid]) {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
}
.block-container { padding: 1.2rem 2rem 2rem !important; }

[data-testid="stSidebar"] {
    background: #09293A !important;
    border-right: 1px solid rgba(45,197,180,.25) !important;
}
[data-testid="stSidebar"] label {
    font-size: 14px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .05em;
    color: rgba(255,255,255,.8) !important;
}
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
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 15px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .03em; padding: 9px 16px !important;
}
[data-testid="stTabs"] [aria-selected="true"] { color: #2DC5B4 !important; }
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
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header_html(titulo_destaque: str, subtitulo: str) -> str:
    return f"""
<div style="background:linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
            border-radius:16px;padding:24px 38px;margin-bottom:18px;
            border:1px solid rgba(45,197,180,.4)">
  <div style="font-size:clamp(26px,3.4vw,48px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05;
              font-family:'Barlow Condensed',sans-serif">
    CENTRAL DE <span style="color:{TEAL}">{titulo_destaque}</span>
  </div>
  <div style="font-size:15px;color:rgba(255,255,255,.55);margin-top:4px;
              font-family:'Barlow Condensed',sans-serif">{subtitulo}</div>
</div>"""


# ── Google Sheet (mesma planilha, abas distintas) ─────────────────────────────
SHEET_ID = "12_DwR-eL1fM-Aj77ZSFFxtTpLAC9PeN6FE2EoHTn-RA"


def gviz_csv(aba: str) -> str:
    return (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
            f"/gviz/tq?tqx=out:csv&sheet={aba}")


SHEET_CSV     = gviz_csv("Pendencias")
VIAGENS_CSV   = gviz_csv("Viagens")

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


# ══════════════════════════════════════════════════════════════════════════════
# PENDÊNCIAS
# ══════════════════════════════════════════════════════════════════════════════
LGPD_REMOVE = ["Destinatário", "Endereço", "Bairro", "Telefone",
               "CEP Destinatário", "Obs Entrega", "Cód Destinatário", "Ajudante"]
DATE_COLS   = ["Data Pedido", "Data Emissão NF", "Embarque", "Data Prazo",
               "Data Prazo cliente", "Data última viagem", "Data ocorrência",
               "Data Registro Ocorrencia", "Data Primeira Bipagem",
               "Data Bipagem Filial", "Prazo Efetividade"]
NUM_COLS    = ["Peso", "Valor NF", "Volumes"]
MAPA_RISCO  = {0: "Sem risco GR", 1: "Risco baixo", 2: "Risco médio", 3: "Risco alto"}

UF_BR = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
         "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
         "SP", "SE", "TO"}
SP_INTERIOR = {
    "SP CAMPINAS", "SP BAURU", "SP RIBEIRAO PRETO", "SP ARACATUBA",
    "SP ARARAQUARA", "SP ITAPETININGA", "SP PRESIDENTE PRUDENTE",
    "SP SAO JOSE DOS CAMPOS",
}


def eh_filial(nome) -> bool:
    """True se o valor parece uma filial real (UF + cidade)."""
    if not isinstance(nome, str):
        return False
    partes = nome.strip().split()
    return len(partes) >= 2 and partes[0].upper() in UF_BR


def regional(filial) -> str:
    """Classifica a filial em SP, Interior, Sul, RJ (ou Outros)."""
    if not isinstance(filial, str) or not filial.strip():
        return "Outros"
    f = filial.strip().upper()
    uf = f.split()[0]
    if uf == "RJ":
        return "RJ"
    if uf in {"PR", "SC", "RS"}:
        return "Sul"
    if uf == "SP":
        return "Interior" if f in SP_INTERIOR else "SP"
    return "Outros"


def _processar(df: pd.DataFrame) -> pd.DataFrame:
    if "NF" in df.columns:
        df = df[pd.to_numeric(df["NF"], errors="coerce").notna()].copy()
    df = df.drop(columns=[c for c in LGPD_REMOVE if c in df.columns])
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": None, "": None})
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    hoje = pd.Timestamp.today().normalize()
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
    if "Data Bipagem Filial" in df.columns:
        df["Dias Parado"] = (hoje - df["Data Bipagem Filial"]).dt.days.clip(lower=0)
    elif "Embarque" in df.columns:
        df["Dias Parado"] = (hoje - df["Embarque"]).dt.days.clip(lower=0)
    else:
        df["Dias Parado"] = 0
    if "Nivel de Risco" in df.columns:
        df["Risco GR"] = (pd.to_numeric(df["Nivel de Risco"], errors="coerce")
                          .map(MAPA_RISCO).fillna("Não classificado"))
    if "Motorista última viagem" in df.columns:
        df["Motorista"] = df["Motorista última viagem"].fillna("Sem motorista")
    if "Filial" in df.columns:
        df["É Filial"] = df["Filial"].map(eh_filial)
        df["Regional"] = df["Filial"].map(regional)
    if "Filial de Entrega" in df.columns:
        df["É FilialEnt"] = df["Filial de Entrega"].map(eh_filial)
    return df


@st.cache_data(show_spinner="Carregando do Google Sheets...", ttl=600)
def carregar_sheets(url: str) -> pd.DataFrame:
    return _processar(pd.read_csv(url))


@st.cache_data(show_spinner="Carregando arquivo...")
def carregar(key: str, data: bytes) -> pd.DataFrame:
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


# ══════════════════════════════════════════════════════════════════════════════
# VIAGENS / ENTREGAS
# ══════════════════════════════════════════════════════════════════════════════
# LGPD: nomes de ajudante saem; motorista permanece (dimensão operacional, igual às pendências).
VIAGENS_LGPD = ["Ajudante"]
VIAGENS_NUM  = ["Viagens", "Entregas", "Volumes", "Sucessos", "Insucessos"]
# Colunas-base; as demais (com hífen e código) são tipos de ocorrência.
VIAGENS_BASE = {"Data Entrega", "Filial", "Motorista", "Veiculo", "Modelo Veiculo",
                "Viagens", "Setores", "Entregas", "Volumes", "Sucessos",
                "Insucessos", "Atualizado em"}


def cols_ocorrencia(df: pd.DataFrame) -> list:
    """Colunas de tipo de ocorrência (ex.: '66-TENTATIVA DE ENTREGA')."""
    return [c for c in df.columns if c not in VIAGENS_BASE and c != "Atualizado em"]


def _processar_viagens(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in VIAGENS_LGPD if c in df.columns], errors="ignore")
    if "Motorista" in df.columns:
        df = df[df["Motorista"].notna()].copy()
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": None, "": None})
    if "Data Entrega" in df.columns:
        df["Data Entrega"] = pd.to_datetime(df["Data Entrega"], errors="coerce",
                                            dayfirst=True)
    for col in VIAGENS_NUM:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in cols_ocorrencia(df):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if {"Sucessos", "Insucessos"}.issubset(df.columns):
        df["Resolvidas"] = df["Sucessos"].fillna(0) + df["Insucessos"].fillna(0)
    return df


@st.cache_data(show_spinner="Carregando viagens do Google Sheets...", ttl=600)
def carregar_viagens_sheets(url: str) -> pd.DataFrame:
    return _processar_viagens(pd.read_csv(url))


@st.cache_data(show_spinner="Carregando arquivo de viagens...")
def carregar_viagens_excel(key: str, data: bytes) -> pd.DataFrame:
    raw = io.BytesIO(data)
    probe = pd.read_excel(raw, header=None, nrows=15, engine="openpyxl")
    hdr = 0
    for i in range(len(probe)):
        if "Motorista" in [str(x).strip() for x in probe.iloc[i].tolist()]:
            hdr = i
            break
    raw.seek(0)
    df = pd.read_excel(raw, header=hdr, engine="openpyxl").dropna(how="all")
    return _processar_viagens(df)
