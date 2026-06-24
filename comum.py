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
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

:root{
  --bg:#0B2E3A; --panel:#0E3847; --card:#123347; --border:#1C4F62;
  --teal:#2DC5B4; --teal2:#1A8090; --text:#E8F4F3; --muted:#8DB4C0;
  --amber:#F59E0B; --red:#EF4444; --green:#10B981;
}

html, body, [class*="css"], .stApp, p, div, label, span:not([data-testid]),
button, input, select, textarea {
    font-family: 'Montserrat', sans-serif !important;
}
.stApp { background: var(--bg) !important; }
.block-container { padding: 1rem 1.6rem 2rem !important; max-width: 100% !important; }

/* Sidebar (navegação de páginas + fonte de dados) */
[data-testid="stSidebar"] {
    background: #09222E !important;
    border-right: 1px solid var(--border) !important;
}
/* botões nativos de recolher/expandir a sidebar ficam como padrão */

/* Painéis = containers com borda (st.container(border=True)) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--panel); border: 1px solid var(--border) !important;
    border-radius: 10px; padding: 4px 6px;
}

/* Filtros compactos */
[data-testid="stWidgetLabel"] label, label[data-testid="stWidgetLabel"] {
    font-size: 11px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: .6px; color: var(--muted) !important;
}
[data-baseweb="select"] > div {
    background: var(--card) !important; border-color: var(--border) !important;
    font-size: 13px !important; min-height: 36px;
}
[data-baseweb="tag"] { background: var(--teal2) !important; }

/* KPI cards */
[data-testid="stMetric"], [data-testid="metric-container"] {
    background: var(--card) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important; padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: .6px; color: var(--muted) !important;
}
[data-testid="stMetricValue"] {
    font-size: 30px !important; font-weight: 900 !important;
    color: var(--text) !important; font-variant-numeric: tabular-nums; line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* Tabs no topo */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 13px !important; font-weight: 600 !important;
    padding: 9px 18px !important; color: var(--muted) !important;
    border-radius: 8px 8px 0 0;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--teal) !important; background: var(--panel) !important;
    border-bottom: 3px solid var(--teal) !important;
}

/* Título de seção (estilo ptitle do modelo) */
.sec {
    font-size: 13px !important; font-weight: 700; color: var(--muted);
    text-transform: uppercase; letter-spacing: .8px;
    padding: 4px 0 10px 2px; margin: 4px 0 6px;
}

/* Box de insight / badge de filtros */
.insight, .fbadge {
    background: var(--card); border-left: 3px solid var(--teal);
    border-radius: 0 8px 8px 0; padding: 10px 16px; font-size: 13px;
    color: var(--muted); margin: 6px 0;
}
.insight strong { color: var(--text); }

footer { visibility: hidden; }

/* Navegação no topo (st.navigation position=top) bem visível */
[data-testid="stHeader"] { background: #09222E !important; }
[data-testid="stNavSectionHeader"], [data-testid="stSidebarNav"] { display: block; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header_html(titulo_destaque: str, subtitulo: str, badge: str = "",
                badge_cor: str = SALMON) -> str:
    badge_html = (f"""<div style="margin-left:auto;background:{badge_cor};color:#fff;
        font-size:12px;font-weight:700;padding:7px 16px;border-radius:20px;
        white-space:nowrap;align-self:center">{badge}</div>""" if badge else "")
    return f"""
<div style="position:relative;background:
       linear-gradient(90deg, rgba(11,46,58,.97) 40%, rgba(29,122,138,.85) 100%),
       linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
     border-radius:14px;padding:20px 32px;margin-bottom:14px;
     border:1px solid var(--border);display:flex;align-items:center;gap:16px">
  <div>
    <div style="font-size:clamp(22px,3vw,38px);font-weight:900;color:#fff;
                letter-spacing:.5px;line-height:1.05;font-family:'Montserrat',sans-serif">
      CENTRAL DE <span style="color:{TEAL}">{titulo_destaque}</span>
    </div>
    <div style="font-size:13px;color:{ '#8DB4C0' };margin-top:5px;
                font-family:'Montserrat',sans-serif">{subtitulo}</div>
  </div>
  {badge_html}
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
                      cliponaxis=False, textfont=dict(size=15, family=FONT))
    fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                      xaxis_title="", yaxis_title="")
    # Estende o eixo de valor para as etiquetas "para fora" nao serem cortadas
    try:
        xmax = float(pd.to_numeric(df_plot[x], errors="coerce").max())
        if xmax > 0:
            fig.update_xaxes(range=[0, xmax * 1.22])
    except Exception:
        pass
    f = fmt(fig, h or max(380, len(df_plot) * 34))
    f.update_layout(coloraxis_showscale=color_fixed is None,
                    coloraxis_colorbar_title=cbar_title)
    return f


def lbl_int(s):  return s.apply(lambda x: f"{x:,.0f}")
def lbl_pct(s):  return s.apply(lambda x: f"{x:.1f}%")
def lbl_rs(s):
    return s.apply(lambda x: f"R$ {x/1e6:.2f}M" if x >= 1e6
                   else (f"R$ {x/1e3:.0f}k" if x >= 1000 else f"R$ {x:,.0f}"))


def tabela_detalhe(df: pd.DataFrame, chave) -> pd.DataFrame:
    """Agrega por 'chave' (str ou lista) com Total, Na Rua, Atrasadas, Tentativas,
    Não Viajou, Peso e Valor — base das tabelas de detalhamento (estilo do modelo)."""
    base = df.copy()
    s = base["Status de Entrega"].astype(str) if "Status de Entrega" in base.columns \
        else pd.Series("", index=base.index)
    base["_narua"] = s.str.contains("Na Rua", case=False, na=False)
    base["_tent"] = s.str.contains("Tentativa de Entrega", case=False, na=False)
    base["_naoviajou"] = s.str.contains("Viajou", case=False, na=False)
    aggs = {"Total": ("NF", "count"), "Na Rua": ("_narua", "sum"),
            "Atrasadas": ("Atrasado", "sum"), "Tentativas": ("_tent", "sum"),
            "Não Viajou": ("_naoviajou", "sum")}
    if "Peso" in base.columns:
        aggs["Peso (kg)"] = ("Peso", "sum")
    if "Valor NF" in base.columns:
        aggs["Valor"] = ("Valor NF", "sum")
    g = base.groupby(chave).agg(**aggs).reset_index()
    g["% Atraso"] = (g["Atrasadas"] / g["Total"] * 100).round(1)
    return g.sort_values("Total", ascending=False)


def estilo_detalhe(g: pd.DataFrame):
    """Styler com formatação e destaque em vermelho para Atrasadas/% Atraso."""
    fmts = {c: "{:,.0f}" for c in ["Total", "Na Rua", "Atrasadas", "Tentativas",
                                   "Não Viajou", "Peso (kg)"] if c in g.columns}
    if "Valor" in g.columns:
        fmts["Valor"] = "R$ {:,.0f}"
    if "% Atraso" in g.columns:
        fmts["% Atraso"] = "{:.1f}%"
    destaque = [c for c in ["Atrasadas", "% Atraso"] if c in g.columns]
    return (g.style.format(fmts, na_rep="—")
            .set_properties(subset=destaque, color="#F08C8C", **{"font-weight": "700"}))


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

# Mapa regional oficial — replica a aba "apoio" da planilha do gerente (Amauri).
# SPC = SP Capital/Metropolitana, SPI = SP Interior.
REGIONAL_MAP = {
    "SP SAO MATEUS": "SP Capital", "SP SAO MATEUS II": "SP Capital",
    "SP CARAPICUIBA": "SP Capital", "SP GUARULHOS": "SP Capital",
    "SP PRAIA GRANDE": "SP Capital", "SP SAO JOSE DOS CAMPOS": "SP Capital",
    "SP TABOAO DA SERRA": "SP Capital", "SP OSASCO": "SP Capital",
    "SP SAO BERNARDO": "SP Capital", "R2 EXPRESS": "SP Capital",
    "SP ITAPETININGA": "SP Interior", "SP RIBEIRAO PRETO": "SP Interior",
    "SP BAURU": "SP Interior", "SP PRESIDENTE PRUDENTE": "SP Interior",
    "SP ARARAQUARA": "SP Interior", "SP ARACATUBA": "SP Interior",
    "SP CAMPINAS": "SP Interior", "SP SOROCABA": "SP Interior",
    "PARCEIRO PATINI": "SP Interior",
    "RJ DUQUE DE CAXIAS": "RJ", "RJ DUQUE - RIO DE JANEIRO": "RJ",
    "RJ DUQUE - BAIXADA": "RJ", "RJ CAMPO GRANDE": "RJ", "RJ SAO GONCALO": "RJ",
    "RJ BARRA MANSA": "RJ", "RJ CAMPOS GOYTACAZES": "RJ", "RJ TRES RIOS": "RJ",
    "RJ NOVA FRIBURGO": "RJ", "RJ SAO PEDRO DA ALDEIA": "RJ", "RJ CUFA": "RJ",
    "PR PARANAGUA": "PR", "PR CURITIBA": "PR", "PR PONTA GROSSA": "PR",
}


def eh_filial(nome) -> bool:
    """True se o valor parece uma filial real (UF + cidade)."""
    if not isinstance(nome, str):
        return False
    partes = nome.strip().split()
    return len(partes) >= 2 and partes[0].upper() in UF_BR


def regional(filial) -> str:
    """Regional pela tabela 'apoio' do gerente; fallback por UF para filiais novas."""
    if not isinstance(filial, str) or not filial.strip():
        return "Outros"
    f = filial.strip().upper()
    if f in REGIONAL_MAP:
        return REGIONAL_MAP[f]
    uf = f.split()[0]
    if uf == "RJ":
        return "RJ"
    if uf in {"PR", "SC", "RS"}:
        return "PR"
    if uf == "SP":
        return "SP Interior"   # padrão para filiais SP novas não mapeadas
    return "Outros"


def _processar(df: pd.DataFrame) -> pd.DataFrame:
    if "NF" in df.columns:
        df = df[pd.to_numeric(df["NF"], errors="coerce").notna()].copy()
    df = df.drop(columns=[c for c in LGPD_REMOVE if c in df.columns])
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": None, "": None})
    for col in DATE_COLS:
        if col in df.columns:
            # Fonte (Sheet/Excel) usa ISO ano-mês-dia; dayfirst=True invertia dia<=12
            df[col] = pd.to_datetime(df[col], errors="coerce")
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
        df["Data Entrega"] = pd.to_datetime(df["Data Entrega"], errors="coerce")
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
