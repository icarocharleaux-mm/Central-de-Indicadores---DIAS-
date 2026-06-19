"""
Dias+ | Dashboard de Pendências Operacionais
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Pendências | Dias+",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta Dias+ ──────────────────────────────────────────────────────────────
TEAL   = "#2DC5B4"
DEEP   = "#0E7A8C"
SALMON = "#C47A77"
AMBER  = "#E8C77A"
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68",
          "#7FBFCC", SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]

# ── CSS — sidebar responsivo, fontes grandes ──────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&display=swap');

/* ─── Base ─────────────────────────────────────────── */
html, body, [class*="css"], .stApp, p, div, label, span:not([data-testid]) {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
}

/* ─── Conteúdo principal — SEM max-width fixo ────── */
/* Deixa o Streamlit controlar a largura dinamicamente */
.block-container {
    padding: 1.2rem 2rem 2rem !important;
}

/* ─── Sidebar ────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #09293A !important;
    border-right: 1px solid rgba(45,197,180,.25) !important;
}
[data-testid="stSidebar"] label {
    font-size: 14px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: rgba(255,255,255,.8) !important;
}

/* ─── Botão colapso sidebar ──────────────────────── */
/* Esconde apenas o texto do ícone Material, mantém o botão clicável */
button[data-testid="stSidebarCollapseButton"] span,
button[data-testid="stBaseButton-headerNoPadding"] span {
    visibility: hidden !important;
    width: 0 !important;
}
button[data-testid="stSidebarCollapseButton"]::before,
button[data-testid="stBaseButton-headerNoPadding"]::before {
    content: "◀";
    visibility: visible;
    font-size: 14px;
    color: #2DC5B4;
}
[data-testid="stSidebarCollapsedControl"] button::before {
    content: "▶";
    visibility: visible;
    font-size: 14px;
    color: #2DC5B4;
}
[data-testid="stSidebarCollapsedControl"] button span {
    visibility: hidden !important;
    width: 0 !important;
}

/* ─── KPI cards ──────────────────────────────────── */
[data-testid="metric-container"] {
    background: rgba(45,197,180,.09) !important;
    border: 1px solid rgba(45,197,180,.32) !important;
    border-radius: 14px !important;
    padding: 18px 20px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 13px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: rgba(255,255,255,.65) !important;
}
[data-testid="stMetricValue"] {
    font-size: 42px !important;
    font-weight: 900 !important;
    color: #2DC5B4 !important;
    font-variant-numeric: tabular-nums;
    line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 14px !important; }

/* ─── Tabs ────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 16px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .04em;
    padding: 10px 20px !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #2DC5B4 !important;
}

/* ─── Títulos de seção ─────────────────────────────── */
.sec {
    font-size: 20px !important;
    font-weight: 900;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: .06em;
    border-left: 5px solid #2DC5B4;
    padding-left: 12px;
    margin: 24px 0 14px;
}

/* ─── Info badge de filtros ───────────────────────── */
.fbadge {
    background: rgba(45,197,180,.12);
    border: 1px solid rgba(45,197,180,.35);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 14px;
    color: rgba(255,255,255,.75);
    margin-bottom: 8px;
}

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ────────────────────────────────────────────────────────────────
LGPD_REMOVE = ["Telefone", "Endereço", "Bairro", "CEP Destinatário", "Destinatário"]
DATE_COLS   = ["Data Pedido","Data Emissão NF","Embarque","Data Prazo",
               "Data Prazo cliente","Data última viagem","Data ocorrência",
               "Data Registro Ocorrencia","Data Primeira Bipagem","Data Bipagem Filial"]
NUM_COLS    = ["Peso","Valor NF","Volumes"]
FONT        = "Barlow Condensed, Arial Narrow, sans-serif"


# ── Carregamento ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dados...")
def carregar(key: str, data: bytes) -> pd.DataFrame:
    import io
    raw = io.BytesIO(data)

    df = pd.read_excel(raw, engine="openpyxl")
    if df.shape[1] > 3 and all(str(c).startswith("Unnamed") for c in df.columns[:4]):
        raw.seek(0)
        df = pd.read_excel(raw, engine="openpyxl", header=3)
        df = df.dropna(how="all")

    df = df.drop(columns=[c for c in LGPD_REMOVE if c in df.columns])

    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "NF" in df.columns:
        df = df[pd.to_numeric(df["NF"], errors="coerce").notna()].copy()

    hoje = pd.Timestamp.today().normalize()
    if "Data Prazo" in df.columns:
        df["Em Atraso"]   = df["Data Prazo"].notna() & (df["Data Prazo"] < hoje)
        df["Dias Atraso"] = (hoje - df["Data Prazo"]).dt.days.clip(lower=0)
        df.loc[~df["Em Atraso"], "Dias Atraso"] = 0

    # Dias desde embarque
    if "Embarque" in df.columns:
        df["Dias Embarque"] = (hoje - df["Embarque"]).dt.days.clip(lower=0)

    return df


def encontrar_local() -> Path | None:
    for p in ["outputs/pendencias/**/*consolidado*.xlsx", "data/*.xlsx"]:
        hits = sorted(Path(".").glob(p), reverse=True)
        if hits:
            return hits[0]
    return None


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
            border-radius:16px;padding:26px 38px;margin-bottom:20px;
            border:1px solid rgba(45,197,180,.4)">
  <div style="font-size:clamp(28px,3.5vw,52px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05;
              font-family:'Barlow Condensed',sans-serif">
    PENDÊNCIAS <span style="color:{TEAL}">OPERACIONAIS</span>
  </div>
  <div style="font-size:15px;color:rgba(255,255,255,.55);margin-top:6px;
              font-family:'Barlow Condensed',sans-serif">
    Dias+ &nbsp;·&nbsp; Notas Fiscais em Aberto &nbsp;·&nbsp;
    {datetime.now():%d/%m/%Y %H:%M}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar — dados ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""<div style="font-family:'Barlow Condensed',sans-serif;
        font-size:24px;font-weight:900;color:{TEAL};text-transform:uppercase;
        letter-spacing:.06em;padding:4px 0 2px">🔍 FILTROS</div>""",
        unsafe_allow_html=True)
    st.divider()

    arquivo_local = encontrar_local()
    arquivo_bytes, arquivo_key = None, None

    if arquivo_local:
        st.success(f"📂 {arquivo_local.name}")
        arquivo_bytes = arquivo_local.read_bytes()
        arquivo_key   = arquivo_local.name

    upload = st.file_uploader("Carregar arquivo (.xlsx)", type=["xlsx"])
    if upload:
        arquivo_bytes = upload.read()
        arquivo_key   = upload.name

if arquivo_bytes is None:
    st.info("👈 Carregue o arquivo consolidado na barra lateral.")
    st.stop()

df_raw = carregar(arquivo_key, arquivo_bytes)

# ── Sidebar — filtros ─────────────────────────────────────────────────────────
with st.sidebar:

    # Período embarque
    st.markdown("**📅 Período de Embarque**")
    if "Embarque" in df_raw.columns:
        datas = df_raw["Embarque"].dropna()
        if not datas.empty:
            d_min, d_max = datas.min().date(), datas.max().date()
            intervalo = st.date_input("", value=(d_min, d_max),
                                      min_value=d_min, max_value=d_max,
                                      label_visibility="collapsed")
            data_ini = intervalo[0] if len(intervalo) > 0 else d_min
            data_fim = intervalo[1] if len(intervalo) > 1 else d_max
        else:
            data_ini = data_fim = None
    else:
        data_ini = data_fim = None

    # Filial
    st.markdown("**🏢 Filial**")
    opts_filial = sorted(df_raw["Filial"].dropna().unique()) if "Filial" in df_raw.columns else []
    sel_filiais = st.multiselect("", opts_filial, placeholder="Todas as filiais",
                                  label_visibility="collapsed")

    # Filial de Entrega
    st.markdown("**🚚 Filial de Entrega**")
    opts_fe = sorted(df_raw["Filial de Entrega"].dropna().unique()) if "Filial de Entrega" in df_raw.columns else []
    sel_fe = st.multiselect("", opts_fe, placeholder="Todas",
                              label_visibility="collapsed")

    # Cliente
    st.markdown("**👤 Cliente**")
    opts_cli = sorted(df_raw["Cliente"].dropna().unique()) if "Cliente" in df_raw.columns else []
    sel_cli = st.multiselect("", opts_cli, placeholder="Todos os clientes",
                              label_visibility="collapsed")

    # Status
    st.markdown("**📦 Status de Entrega**")
    opts_status = sorted(df_raw["Status de Entrega"].dropna().unique()) if "Status de Entrega" in df_raw.columns else []
    sel_status = st.multiselect("", opts_status, placeholder="Todos os status",
                                 label_visibility="collapsed")

    # Tipo Entrega
    st.markdown("**🔖 Tipo de Entrega**")
    opts_tipo = sorted(df_raw["Tipo Entrega"].dropna().unique()) if "Tipo Entrega" in df_raw.columns else []
    sel_tipo = st.multiselect("", opts_tipo, placeholder="Todos os tipos",
                               label_visibility="collapsed")

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

df = f(df, "Filial",            sel_filiais)
df = f(df, "Filial de Entrega", sel_fe)
df = f(df, "Cliente",           sel_cli)
df = f(df, "Status de Entrega", sel_status)
df = f(df, "Tipo Entrega",      sel_tipo)

if so_atraso and "Em Atraso" in df.columns:
    df = df[df["Em Atraso"]]

# Badge de filtros ativos
ativos = []
if sel_filiais:  ativos.append(f"Filial: {', '.join(sel_filiais[:2])}{'…' if len(sel_filiais)>2 else ''}")
if sel_fe:       ativos.append(f"Fil. Entrega: {len(sel_fe)}")
if sel_cli:      ativos.append(f"Cliente: {', '.join(sel_cli[:2])}{'…' if len(sel_cli)>2 else ''}")
if sel_status:   ativos.append(f"Status: {len(sel_status)}")
if sel_tipo:     ativos.append(f"Tipo: {len(sel_tipo)}")
if so_atraso:    ativos.append("⚠️ só atraso")
if ativos:
    st.markdown(
        "<div class='fbadge'>🔍 " + "  |  ".join(ativos) + "</div>",
        unsafe_allow_html=True,
    )

# ── KPIs ──────────────────────────────────────────────────────────────────────
total  = len(df)
valor  = df["Valor NF"].sum()       if "Valor NF"  in df.columns else 0
peso   = df["Peso"].sum()           if "Peso"      in df.columns else 0
atraso = int(df["Em Atraso"].sum()) if "Em Atraso" in df.columns else 0
pct_at = atraso / total * 100       if total > 0 else 0
med_d  = df.loc[df.get("Em Atraso", pd.Series(dtype=bool)), "Dias Atraso"].mean() \
         if "Em Atraso" in df.columns and atraso > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes",   f"{total:,.0f}")
k2.metric("Valor Total",     f"R$ {valor/1e6:.2f}M" if valor >= 1e6 else f"R$ {valor:,.0f}")
k3.metric("Peso Total",      f"{peso/1000:.1f} t"   if peso  >= 1000 else f"{peso:,.0f} kg")
k4.metric("Em Atraso",       f"{atraso:,.0f}",
          delta=f"{pct_at:.1f}% do total", delta_color="inverse")
k5.metric("Média de Atraso", f"{med_d:.0f} dias")

st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)


# ── Helper gráfico ────────────────────────────────────────────────────────────
def fmt(fig: go.Figure, h: int = 420, legend_h: bool = False) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color="#FFFFFF", size=15),
        title_font=dict(family=FONT, color="#FFFFFF", size=18),
        margin=dict(l=12, r=160, t=50, b=12),
        height=h,
        uniformtext_minsize=12,
        uniformtext_mode="hide",
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=14),
            orientation="h" if legend_h else "v",
            y=1.1 if legend_h else 1,
        ),
        coloraxis_colorbar=dict(
            thickness=16, len=0.7,
            tickfont=dict(size=13, color="#FFFFFF"),
            title=dict(font=dict(size=13, color="#FFFFFF")),
            bgcolor="rgba(0,0,0,0)", outlinewidth=0,
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,.1)",
        zerolinecolor="rgba(255,255,255,.18)",
        tickfont=dict(size=14),
        title_font=dict(size=15),
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,.1)",
        zerolinecolor="rgba(255,255,255,.18)",
        tickfont=dict(size=15),
        title_font=dict(size=15),
        automargin=True,
    )
    return fig


def barh(df_plot, x, y, title, h=None, text_col=None, color_col=None,
          scale=None, color_fixed=None):
    """Barra horizontal padronizada no estilo do dashboard de referência."""
    if scale is None:
        scale = [[0, DEEP], [1, TEAL]]
    color_kw = dict(color=color_col or x,
                    color_continuous_scale=scale) if color_fixed is None \
               else dict(color_discrete_sequence=[color_fixed])
    fig = px.bar(df_plot, x=x, y=y, orientation="h",
                 title=title, text=text_col, **color_kw)
    fig.update_traces(
        marker_line_width=0,
        textposition="outside",
        textfont=dict(size=15, family=FONT),
    )
    fig.update_layout(
        yaxis=dict(categoryorder="total ascending"),
        xaxis_title="",
        yaxis_title="",
    )
    return fmt(fig, h or max(380, len(df_plot) * 34))


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊  Visão Geral",
    "🏢  Filiais",
    "👤  Clientes",
    "⏰  SLA / Atraso",
    "📋  Dados",
])

# ── TAB 1 — Visão Geral ───────────────────────────────────────────────────────
with tab1:
    # Status de Entrega
    st.markdown('<div class="sec">Status de Entrega</div>', unsafe_allow_html=True)
    if "Status de Entrega" in df.columns:
        d = df["Status de Entrega"].value_counts().reset_index()
        d.columns = ["Status", "Qtd"]
        d["label"] = d.apply(lambda r: f"{r['Qtd']:,.0f}", axis=1)
        fig = barh(d, x="Qtd", y="Status", title="Distribuição por Status de Entrega",
                   text_col="label")
        fig.update_layout(coloraxis_showscale=True,
                          coloraxis_colorbar_title="NFs")
        st.plotly_chart(fig, use_container_width=True)

    # Tendência semanal
    st.markdown('<div class="sec">Tendência Semanal</div>', unsafe_allow_html=True)
    if "Embarque" in df.columns:
        tmp = df.dropna(subset=["Embarque"]).copy()
        tmp["Semana"] = tmp["Embarque"].dt.to_period("W").dt.start_time
        tr = tmp.groupby("Semana").agg(
            NFs=("NF","count"), Atraso=("Em Atraso","sum")
        ).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=tr["Semana"], y=tr["Atraso"],
                             name="Em Atraso", marker_color=SALMON,
                             marker_line_width=0, opacity=0.7, yaxis="y2"))
        fig.add_trace(go.Scatter(x=tr["Semana"], y=tr["NFs"],
                                 mode="lines+markers", name="NFs Pendentes",
                                 line=dict(color=TEAL, width=3),
                                 marker=dict(size=7, color=TEAL)))
        fig.update_layout(
            title="NFs por Semana de Embarque vs. Em Atraso",
            yaxis=dict(title="NFs Pendentes"),
            yaxis2=dict(title="Em Atraso", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)", color=SALMON,
                        tickfont=dict(color=SALMON, size=13)),
        )
        st.plotly_chart(fmt(fig, 320, legend_h=True), use_container_width=True)

    # Tipo de Entrega
    st.markdown('<div class="sec">Tipo de Entrega</div>', unsafe_allow_html=True)
    if "Tipo Entrega" in df.columns:
        d = df["Tipo Entrega"].value_counts().reset_index()
        d.columns = ["Tipo", "Qtd"]
        d["label"] = d["Qtd"].apply(lambda x: f"{x:,.0f}")
        fig = barh(d, x="Qtd", y="Tipo", title="Por Tipo de Entrega",
                   text_col="label")
        fig.update_layout(coloraxis_showscale=True)
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 2 — Filiais ───────────────────────────────────────────────────────────
with tab2:
    if "Filial" not in df.columns:
        st.info("Coluna Filial não disponível.")
    else:
        # Total vs Atraso
        st.markdown('<div class="sec">NFs por Filial</div>', unsafe_allow_html=True)
        d = df.groupby("Filial").agg(
            Total=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
        ).reset_index()
        d["% Atraso"] = (d["Atraso"] / d["Total"] * 100).round(1)
        d = d.sort_values("Total", ascending=True)
        d["label"] = d["Total"].apply(lambda x: f"{x:,.0f}")

        fig = go.Figure()
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Total"], orientation="h",
                             name="Total NFs", marker_color=TEAL,
                             marker_line_width=0,
                             text=d["label"], textposition="outside",
                             textfont=dict(size=14, color="#FFFFFF", family=FONT)))
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON,
                             marker_line_width=0))
        fig.update_layout(barmode="overlay",
                          title="Total NFs vs. Em Atraso por Filial",
                          yaxis=dict(categoryorder="total ascending",
                                     automargin=True))
        st.plotly_chart(fmt(fig, max(440, len(d)*30), legend_h=True),
                        use_container_width=True)

        # % Atraso
        st.markdown('<div class="sec">% em Atraso por Filial</div>', unsafe_allow_html=True)
        d2 = d.sort_values("% Atraso", ascending=True)
        d2["label"] = d2["% Atraso"].apply(lambda x: f"{x:.1f}%")
        fig = barh(d2, x="% Atraso", y="Filial",
                   title="% de NFs em Atraso por Filial",
                   text_col="label",
                   scale=[[0, TEAL],[.35, AMBER],[1, SALMON]])
        fig.update_layout(coloraxis_showscale=True,
                          coloraxis_colorbar_title="%")
        st.plotly_chart(fig, use_container_width=True)

        # Valor por filial
        st.markdown('<div class="sec">Valor em Aberto por Filial</div>', unsafe_allow_html=True)
        d3 = d.sort_values("Valor", ascending=True)
        d3["label"] = d3["Valor"].apply(
            lambda x: f"R$ {x/1e6:.2f}M" if x >= 1e6 else f"R$ {x/1e3:.0f}k")
        fig = barh(d3, x="Valor", y="Filial",
                   title="Valor Total em Aberto por Filial",
                   text_col="label",
                   scale=[[0, DEEP],[1, TEAL]])
        fig.update_layout(coloraxis_showscale=True,
                          coloraxis_colorbar_title="R$")
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 3 — Clientes ──────────────────────────────────────────────────────────
with tab3:
    n_cli = st.slider("Clientes exibidos", 10, min(50, len(df_raw["Cliente"].dropna().unique())), 20, 5)

    st.markdown('<div class="sec">Top Clientes por Volume</div>', unsafe_allow_html=True)
    if "Cliente" in df.columns:
        d = df.groupby("Cliente").agg(
            Total=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
        ).reset_index().sort_values("Total", ascending=True).tail(n_cli)
        d["label"] = d["Total"].apply(lambda x: f"{x:,.0f}")

        fig = go.Figure()
        fig.add_trace(go.Bar(y=d["Cliente"], x=d["Total"], orientation="h",
                             name="Total NFs", marker_color=TEAL,
                             marker_line_width=0,
                             text=d["label"], textposition="outside",
                             textfont=dict(size=14, color="#FFFFFF", family=FONT)))
        fig.add_trace(go.Bar(y=d["Cliente"], x=d["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON,
                             marker_line_width=0))
        fig.update_layout(barmode="overlay",
                          title=f"Top {n_cli} Clientes — NFs Pendentes vs. Em Atraso",
                          yaxis=dict(categoryorder="total ascending", automargin=True))
        st.plotly_chart(fmt(fig, max(460, n_cli*30), legend_h=True),
                        use_container_width=True)

    st.markdown('<div class="sec">Valor em Aberto por Cliente</div>', unsafe_allow_html=True)
    if "Cliente" in df.columns:
        d2 = df.groupby("Cliente").agg(Valor=("Valor NF","sum")).reset_index()
        d2 = d2.sort_values("Valor", ascending=True).tail(n_cli)
        d2["label"] = d2["Valor"].apply(
            lambda x: f"R$ {x/1e6:.2f}M" if x >= 1e6 else f"R$ {x/1e3:.0f}k")
        fig = barh(d2, x="Valor", y="Cliente",
                   title=f"Top {n_cli} Clientes — Valor em Aberto",
                   text_col="label",
                   scale=[[0, DEEP],[1, TEAL]])
        fig.update_layout(coloraxis_showscale=True,
                          coloraxis_colorbar_title="R$")
        st.plotly_chart(fig, use_container_width=True)


# ── TAB 4 — SLA / Atraso ─────────────────────────────────────────────────────
with tab4:
    st.info(
        f"ℹ️ **Cobertura:** embarques desde "
        f"{df['Embarque'].dropna().min():%d/%m/%Y if 'Embarque' in df.columns else '—'}"
        f" até {datetime.now():%d/%m/%Y}. "
        "Dias em Atraso = hoje − Data Prazo (independe do embarque).",
        icon=None,
    )

    if "Em Atraso" not in df.columns or not df["Em Atraso"].any():
        st.success("Nenhum registro em atraso com os filtros atuais.")
    else:
        df_at = df[df["Em Atraso"]].copy()
        bins   = [0, 5, 15, 30, 60, 90, float("inf")]
        labels = ["1–5 d","6–15 d","16–30 d","31–60 d","61–90 d","+90 d"]
        df_at["Faixa"] = pd.cut(df_at["Dias Atraso"], bins=bins, labels=labels, right=True)

        st.markdown('<div class="sec">Faixas de Atraso</div>', unsafe_allow_html=True)
        ca, cb = st.columns(2)

        with ca:
            d = df_at["Faixa"].value_counts().reindex(labels).reset_index()
            d.columns = ["Faixa","Qtd"]
            d["label"] = d["Qtd"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "0")
            fig = px.bar(d, x="Faixa", y="Qtd",
                         color="Qtd",
                         color_continuous_scale=[[0, AMBER],[1, SALMON]],
                         title="NFs em Atraso por Faixa de Dias",
                         text="label")
            fig.update_traces(marker_line_width=0, textposition="outside",
                              textfont=dict(size=15, family=FONT))
            fig.update_layout(coloraxis_showscale=True,
                              coloraxis_colorbar_title="NFs",
                              xaxis_title="")
            st.plotly_chart(fmt(fig, 360), use_container_width=True)

        with cb:
            d2 = (df_at.groupby("Faixa", observed=True)
                       .agg(Valor=("Valor NF","sum"))
                       .reindex(labels).reset_index())
            d2.columns = ["Faixa","Valor"]
            d2["label"] = d2["Valor"].apply(
                lambda x: f"R$ {x/1e6:.2f}M" if pd.notna(x) and x >= 1e6
                          else (f"R$ {x/1e3:.0f}k" if pd.notna(x) and x >= 1000 else ""))
            fig = px.bar(d2, x="Faixa", y="Valor",
                         color_discrete_sequence=[SALMON],
                         title="Valor em Risco por Faixa (R$)", text="label")
            fig.update_traces(marker_line_width=0, textposition="outside",
                              textfont=dict(size=15, family=FONT))
            fig.update_layout(xaxis_title="")
            st.plotly_chart(fmt(fig, 360), use_container_width=True)

        st.markdown('<div class="sec">Ocorrências Mais Frequentes</div>', unsafe_allow_html=True)
        if "Ocorrência" in df.columns:
            d3 = df["Ocorrência"].dropna().value_counts().head(15).reset_index()
            d3.columns = ["Ocorrência","Qtd"]
            d3["label"] = d3["Qtd"].apply(lambda x: f"{x:,.0f}")
            fig = barh(d3, x="Qtd", y="Ocorrência",
                       title="Top 15 Ocorrências",
                       text_col="label",
                       color_fixed=SALMON)
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="sec">SLA por Filial de Entrega</div>', unsafe_allow_html=True)
        if "Filial de Entrega" in df.columns:
            sla = df.groupby("Filial de Entrega").agg(
                Total=("NF","count"), Atraso=("Em Atraso","sum")
            ).reset_index()
            sla["% Atraso"] = (sla["Atraso"] / sla["Total"] * 100).round(1)
            sla = sla.sort_values("% Atraso", ascending=True)
            sla["label"] = sla["% Atraso"].apply(lambda x: f"{x:.1f}%")
            fig = barh(sla, x="% Atraso", y="Filial de Entrega",
                       title="% Atraso por Filial de Entrega",
                       text_col="label",
                       scale=[[0, TEAL],[.35, AMBER],[1, SALMON]])
            fig.update_layout(coloraxis_showscale=True,
                              coloraxis_colorbar_title="%")
            st.plotly_chart(fig, use_container_width=True)


# ── TAB 5 — Dados ─────────────────────────────────────────────────────────────
with tab5:
    cols_show = [c for c in [
        "NF","Status de Entrega","Filial","Filial de Entrega","Cliente",
        "Tipo Entrega","Embarque","Data Prazo","Em Atraso","Dias Atraso",
        "Dias Embarque","Peso","Valor NF","Ocorrência","Obs Ocorrência","GV","Subrota",
    ] if c in df.columns]

    ci, cd = st.columns([3,1])
    ci.markdown(f"**{total:,.0f} registros** com filtros atuais")
    with cd:
        csv = df[cols_show].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Exportar CSV", data=csv,
                           file_name=f"pendencias_{datetime.now():%Y%m%d}.csv",
                           mime="text/csv", use_container_width=True)

    st.dataframe(
        df[cols_show],
        use_container_width=True,
        height=580,
        column_config={
            "Em Atraso":    st.column_config.CheckboxColumn("Em Atraso"),
            "Dias Atraso":  st.column_config.NumberColumn("Atraso", format="%d d"),
            "Dias Embarque":st.column_config.NumberColumn("Dias Emb.", format="%d d"),
            "Embarque":     st.column_config.DateColumn("Embarque",   format="DD/MM/YYYY"),
            "Data Prazo":   st.column_config.DateColumn("Data Prazo", format="DD/MM/YYYY"),
            "Valor NF":     st.column_config.NumberColumn("Valor NF",  format="R$ %.2f"),
            "Peso":         st.column_config.NumberColumn("Peso",      format="%.2f kg"),
        },
    )
