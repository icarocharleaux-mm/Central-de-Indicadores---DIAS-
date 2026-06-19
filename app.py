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

# ── Paleta ────────────────────────────────────────────────────────────────────
TEAL   = "#2DC5B4"
DEEP   = "#0E7A8C"
SALMON = "#C47A77"
AMBER  = "#E8C77A"
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68",
          "#7FBFCC", SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&display=swap');

/* Base */
html, body, [class*="css"], .stApp, p, div, label {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
    font-size: 16px !important;
}
.block-container { padding: 1rem 2rem 2rem !important; max-width: 1400px !important; }

/* Oculta botão de colapso da sidebar e ícone que vira texto */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }
/* Previne que ícones Material não carregados apareçam como texto */
.material-symbols-rounded, .material-icons { font-size: 0 !important; }
button[kind="header"] > div > span { display: none !important; }

/* KPI cards */
[data-testid="metric-container"] {
    background: rgba(45,197,180,.1) !important;
    border: 1px solid rgba(45,197,180,.35) !important;
    border-radius: 16px !important;
    padding: 20px 22px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 15px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: rgba(255,255,255,.7) !important;
}
[data-testid="stMetricValue"] {
    font-size: 48px !important;
    font-weight: 900 !important;
    color: #2DC5B4 !important;
    font-variant-numeric: tabular-nums;
    line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] { font-size: 16px !important; }

/* Tabs */
[data-testid="stTabs"] button {
    font-size: 17px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .05em;
    padding: 10px 24px !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #2DC5B4 !important;
    border-bottom: 3px solid #2DC5B4 !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(11,48,64,.97) !important;
    border-right: 1px solid rgba(45,197,180,.25) !important;
    min-width: 280px !important;
}
[data-testid="stSidebar"] label {
    font-size: 15px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: rgba(255,255,255,.85) !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] span {
    font-size: 14px !important;
}

/* Section title */
.sec {
    font-size: 22px !important;
    font-weight: 900;
    color: #fff;
    text-transform: uppercase;
    letter-spacing: .06em;
    border-left: 5px solid #2DC5B4;
    padding-left: 12px;
    margin: 28px 0 16px;
    line-height: 1.2;
}

/* Filter badge */
.filter-badge {
    background: rgba(45,197,180,.15);
    border: 1px solid rgba(45,197,180,.4);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 13px;
    color: rgba(255,255,255,.75);
}

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── LGPD / constantes ─────────────────────────────────────────────────────────
LGPD_REMOVE = ["Telefone", "Endereço", "Bairro", "CEP Destinatário", "Destinatário"]
DATE_COLS   = ["Data Pedido","Data Emissão NF","Embarque","Data Prazo",
               "Data Prazo cliente","Data última viagem","Data ocorrência",
               "Data Registro Ocorrencia","Data Primeira Bipagem","Data Bipagem Filial"]
NUM_COLS    = ["Peso","Valor NF","Volumes"]


# ── Carregamento ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dados...")
def carregar(key: str, data: bytes) -> pd.DataFrame:
    import io
    df = pd.read_excel(io.BytesIO(data), engine="openpyxl")
    if df.shape[1] > 3 and all(str(c).startswith("Unnamed") for c in df.columns[:4]):
        df = pd.read_excel(io.BytesIO(data), engine="openpyxl", header=3)
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
            border-radius:16px;padding:28px 40px;margin-bottom:24px;
            border:1px solid rgba(45,197,180,.4)">
  <div style="font-size:clamp(32px,4vw,58px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05">
    PENDÊNCIAS <span style="color:{TEAL}">OPERACIONAIS</span>
  </div>
  <div style="font-size:17px;color:rgba(255,255,255,.6);margin-top:6px;font-weight:400">
    Dias+ &nbsp;·&nbsp; Notas Fiscais em Aberto &nbsp;·&nbsp;
    Atualizado em {datetime.now():%d/%m/%Y %H:%M}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="font-size:26px;font-weight:900;color:{TEAL};
                text-transform:uppercase;letter-spacing:.06em;
                margin-bottom:2px">🔍 FILTROS</div>
    """, unsafe_allow_html=True)
    st.divider()

    # Upload / arquivo local
    arquivo_local = encontrar_local()
    arquivo_bytes = None
    arquivo_key   = None

    if arquivo_local:
        st.success(f"📂 {arquivo_local.name}", icon=None)
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

# ── Filtros ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # Período de Embarque
    st.markdown("**📅 Período de Embarque**")
    if "Embarque" in df_raw.columns:
        datas = df_raw["Embarque"].dropna()
        if not datas.empty:
            d_min, d_max = datas.min().date(), datas.max().date()
            data_ini, data_fim = st.date_input(
                "De / Até",
                value=(d_min, d_max),
                min_value=d_min,
                max_value=d_max,
                label_visibility="collapsed",
            )
        else:
            data_ini = data_fim = None
    else:
        data_ini = data_fim = None

    st.markdown("**🏢 Filial**")
    opts_filial = sorted(df_raw["Filial"].dropna().unique()) if "Filial" in df_raw.columns else []
    sel_filiais = st.multiselect("Filial", opts_filial, placeholder="Todas",
                                  label_visibility="collapsed")

    st.markdown("**🌎 Regional**")
    opts_reg = sorted(df_raw["Região"].dropna().unique()) if "Região" in df_raw.columns else []
    sel_regioes = st.multiselect("Regional", opts_reg, placeholder="Todas",
                                  label_visibility="collapsed")

    st.markdown("**👤 Cliente**")
    opts_cli = sorted(df_raw["Cliente"].dropna().unique()) if "Cliente" in df_raw.columns else []
    sel_clientes = st.multiselect("Cliente", opts_cli, placeholder="Todos",
                                   label_visibility="collapsed")

    st.markdown("**📦 Status de Entrega**")
    opts_status = sorted(df_raw["Status de Entrega"].dropna().unique()) if "Status de Entrega" in df_raw.columns else []
    sel_status = st.multiselect("Status", opts_status, placeholder="Todos",
                                 label_visibility="collapsed")

    st.markdown("**🚚 Tipo de Entrega**")
    opts_tipo = sorted(df_raw["Tipo Entrega"].dropna().unique()) if "Tipo Entrega" in df_raw.columns else []
    sel_tipos = st.multiselect("Tipo", opts_tipo, placeholder="Todos",
                                label_visibility="collapsed")

    st.divider()
    so_atraso = st.toggle("⚠️ Somente em atraso", value=False)

    st.divider()
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.rerun()

    st.caption("diaslog.com.br")

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()

if data_ini and data_fim and "Embarque" in df.columns:
    d0, d1 = pd.Timestamp(data_ini), pd.Timestamp(data_fim)
    df = df[df["Embarque"].isna() | ((df["Embarque"] >= d0) & (df["Embarque"] <= d1))]

def filtrar(df, col, sel):
    return df[df[col].isin(sel)] if sel and col in df.columns else df

df = filtrar(df, "Filial",            sel_filiais)
df = filtrar(df, "Região",            sel_regioes)
df = filtrar(df, "Cliente",           sel_clientes)
df = filtrar(df, "Status de Entrega", sel_status)
df = filtrar(df, "Tipo Entrega",      sel_tipos)

if so_atraso and "Em Atraso" in df.columns:
    df = df[df["Em Atraso"]]

# ── Resumo dos filtros ativos ─────────────────────────────────────────────────
ativos = []
if sel_filiais:  ativos.append(f"Filial: {', '.join(sel_filiais[:2])}{'...' if len(sel_filiais)>2 else ''}")
if sel_regioes:  ativos.append(f"Regional: {', '.join(sel_regioes[:2])}{'...' if len(sel_regioes)>2 else ''}")
if sel_clientes: ativos.append(f"Cliente: {', '.join(sel_clientes[:2])}{'...' if len(sel_clientes)>2 else ''}")
if sel_status:   ativos.append(f"Status: {len(sel_status)} selecionados")
if sel_tipos:    ativos.append(f"Tipo: {len(sel_tipos)} selecionados")
if so_atraso:    ativos.append("⚠️ Só atraso")

if ativos:
    st.markdown(
        "<div class='filter-badge'>🔍 Filtros ativos: &nbsp;" +
        " &nbsp;|&nbsp; ".join(ativos) + "</div>",
        unsafe_allow_html=True
    )

# ── KPIs ──────────────────────────────────────────────────────────────────────
total      = len(df)
valor      = df["Valor NF"].sum()       if "Valor NF"  in df.columns else 0
peso       = df["Peso"].sum()           if "Peso"      in df.columns else 0
atraso     = int(df["Em Atraso"].sum()) if "Em Atraso" in df.columns else 0
pct_atraso = atraso / total * 100       if total > 0 else 0
media_dias = df.loc[df["Em Atraso"], "Dias Atraso"].mean() \
             if "Em Atraso" in df.columns and atraso > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes",     f"{total:,.0f}")
k2.metric("Valor Total",       f"R$ {valor/1e6:.2f}M" if valor >= 1e6 else f"R$ {valor:,.0f}")
k3.metric("Peso Total",        f"{peso/1000:.1f} t"   if peso  >= 1000 else f"{peso:,.0f} kg")
k4.metric("Em Atraso",         f"{atraso:,.0f}",
          delta=f"{pct_atraso:.1f}% do total", delta_color="inverse")
k5.metric("Média de Atraso",   f"{media_dias:.0f} dias")


# ── Helper de gráficos ────────────────────────────────────────────────────────
def fmt(fig, h=420, legend_h=False):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FFFFFF", family="Barlow Condensed", size=15),
        margin=dict(l=10, r=10, t=48, b=10),
        height=h,
        title_font=dict(size=18, color="#FFFFFF", family="Barlow Condensed"),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=14),
            orientation="h" if legend_h else "v",
            y=1.12 if legend_h else 1,
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,.12)",
        zerolinecolor="rgba(255,255,255,.2)",
        tickfont=dict(size=14),
        title_font=dict(size=15),
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,.12)",
        zerolinecolor="rgba(255,255,255,.2)",
        tickfont=dict(size=14),
        title_font=dict(size=15),
    )
    return fig


# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊  Visão Geral",
    "🏢  Filiais",
    "👤  Clientes",
    "⏰  SLA / Atraso",
    "📋  Dados",
])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — VISÃO GERAL
# ════════════════════════════════════════════════════════════════════════════════
with tab1:

    # Status de Entrega
    st.markdown('<div class="sec">Distribuição por Status de Entrega</div>',
                unsafe_allow_html=True)
    if "Status de Entrega" in df.columns:
        d = df["Status de Entrega"].value_counts().reset_index()
        d.columns = ["Status", "Qtd"]
        d["Pct"] = (d["Qtd"] / d["Qtd"].sum() * 100).round(1)
        d["label"] = d.apply(lambda r: f"{r['Qtd']:,.0f}  ({r['Pct']:.1f}%)", axis=1)
        fig = px.bar(d, x="Qtd", y="Status", orientation="h",
                     color="Qtd",
                     color_continuous_scale=[[0, DEEP], [1, TEAL]],
                     text="label")
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=14))
        fig.update_layout(coloraxis_showscale=False,
                          yaxis=dict(categoryorder="total ascending"),
                          xaxis_title="Quantidade de NFs")
        st.plotly_chart(fmt(fig, 480), use_container_width=True)

    # Tendência semanal
    st.markdown('<div class="sec">Tendência Semanal de Embarque</div>',
                unsafe_allow_html=True)
    if "Embarque" in df.columns:
        tmp = df.dropna(subset=["Embarque"]).copy()
        tmp["Semana"] = tmp["Embarque"].dt.to_period("W").dt.start_time
        trend = tmp.groupby("Semana").agg(
            NFs=("NF","count"),
            Atraso=("Em Atraso","sum"),
            Valor=("Valor NF","sum"),
        ).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=trend["Semana"], y=trend["Atraso"],
            name="Em Atraso", marker_color=SALMON,
            marker_line_width=0, opacity=0.75, yaxis="y2",
        ))
        fig.add_trace(go.Scatter(
            x=trend["Semana"], y=trend["NFs"],
            mode="lines+markers+text", name="NFs Pendentes",
            line=dict(color=TEAL, width=3),
            marker=dict(size=8, color=TEAL),
            text=trend["NFs"], textposition="top center",
            textfont=dict(size=13, color=TEAL),
        ))
        fig.update_layout(
            title="NFs por Semana vs. Em Atraso",
            yaxis=dict(title="NFs Pendentes"),
            yaxis2=dict(title="Em Atraso", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)", color=SALMON,
                        tickfont=dict(color=SALMON)),
            legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)", font=dict(size=15)),
        )
        st.plotly_chart(fmt(fig, 380), use_container_width=True)

    # Tipo Entrega
    st.markdown('<div class="sec">Tipo de Entrega</div>', unsafe_allow_html=True)
    if "Tipo Entrega" in df.columns:
        d = df["Tipo Entrega"].value_counts().reset_index()
        d.columns = ["Tipo", "Qtd"]
        d["Pct"] = (d["Qtd"] / d["Qtd"].sum() * 100).round(1)
        d20 = d.head(20).copy()
        d20["label"] = d20["Pct"].apply(lambda x: f"{x:.1f}%")
        fig = px.bar(d20, x="Tipo", y="Qtd",
                     color="Qtd",
                     color_continuous_scale=[[0, DEEP], [1, TEAL]],
                     text="label")
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=13))
        fig.update_layout(coloraxis_showscale=False, xaxis_title="")
        st.plotly_chart(fmt(fig, 360), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — FILIAIS
# ════════════════════════════════════════════════════════════════════════════════
with tab2:

    st.markdown('<div class="sec">Pendências por Filial</div>', unsafe_allow_html=True)
    if "Filial" in df.columns:
        d = df.groupby("Filial").agg(
            Total=("NF","count"),
            Atraso=("Em Atraso","sum"),
            Valor=("Valor NF","sum"),
            Peso=("Peso","sum"),
        ).reset_index()
        d["% Atraso"] = (d["Atraso"] / d["Total"] * 100).round(1)
        d = d.sort_values("Total", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=d["Filial"], x=d["Total"], orientation="h",
            name="Total NFs", marker_color=TEAL, marker_line_width=0,
            text=d["Total"].apply(lambda x: f"{x:,.0f}"),
            textposition="outside", textfont=dict(size=14),
        ))
        fig.add_trace(go.Bar(
            y=d["Filial"], x=d["Atraso"], orientation="h",
            name="Em Atraso", marker_color=SALMON, marker_line_width=0,
        ))
        fig.update_layout(barmode="overlay", title="Total de NFs vs. Em Atraso por Filial",
                          xaxis_title="Quantidade de NFs")
        st.plotly_chart(fmt(fig, max(420, len(d)*32)), use_container_width=True)

    st.markdown('<div class="sec">% de Atraso por Filial</div>', unsafe_allow_html=True)
    if "Filial" in df.columns:
        d2 = d.sort_values("% Atraso", ascending=False)
        fig = px.bar(d2, x="Filial", y="% Atraso",
                     color="% Atraso",
                     color_continuous_scale=[[0, TEAL],[.35, AMBER],[1, SALMON]],
                     text="% Atraso",
                     hover_data={"Total":True,"Atraso":True,"Valor":":.0f"})
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                          marker_line_width=0, textfont=dict(size=14))
        fig.update_layout(coloraxis_showscale=False, xaxis_title="")
        st.plotly_chart(fmt(fig, 380), use_container_width=True)

    st.markdown('<div class="sec">Valor em Aberto por Filial</div>', unsafe_allow_html=True)
    if "Filial" in df.columns:
        d3 = d.sort_values("Valor", ascending=True)
        fig = px.bar(d3, y="Filial", x="Valor", orientation="h",
                     color_discrete_sequence=[DEEP],
                     text=d3["Valor"].apply(lambda x: f"R$ {x/1e3:.0f}k" if x >= 1000 else f"R$ {x:.0f}").tolist())
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=14))
        fig.update_layout(xaxis_title="Valor NF (R$)")
        st.plotly_chart(fmt(fig, max(420, len(d3)*32)), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — CLIENTES
# ════════════════════════════════════════════════════════════════════════════════
with tab3:

    n_cli = st.slider("Quantos clientes exibir", 10, 50, 20, step=5)

    st.markdown('<div class="sec">Top Clientes por Pendências</div>', unsafe_allow_html=True)
    if "Cliente" in df.columns:
        d = df.groupby("Cliente").agg(
            Total=("NF","count"),
            Atraso=("Em Atraso","sum"),
            Valor=("Valor NF","sum"),
        ).reset_index()
        d["% Atraso"] = (d["Atraso"] / d["Total"] * 100).round(1)
        d = d.sort_values("Total", ascending=True).tail(n_cli)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=d["Cliente"], x=d["Total"], orientation="h",
            name="Total NFs", marker_color=TEAL, marker_line_width=0,
            text=d["Total"].apply(lambda x: f"{x:,.0f}"),
            textposition="outside", textfont=dict(size=13),
        ))
        fig.add_trace(go.Bar(
            y=d["Cliente"], x=d["Atraso"], orientation="h",
            name="Em Atraso", marker_color=SALMON, marker_line_width=0,
        ))
        fig.update_layout(barmode="overlay", xaxis_title="Quantidade de NFs")
        st.plotly_chart(fmt(fig, max(480, n_cli * 26)), use_container_width=True)

    st.markdown('<div class="sec">Valor Total em Aberto por Cliente</div>',
                unsafe_allow_html=True)
    if "Cliente" in df.columns:
        d2 = (df.groupby("Cliente")
                .agg(Valor=("Valor NF","sum"), Total=("NF","count"))
                .reset_index()
                .sort_values("Valor", ascending=True)
                .tail(n_cli))
        fig = px.bar(d2, y="Cliente", x="Valor", orientation="h",
                     color="Valor",
                     color_continuous_scale=[[0, DEEP],[1, TEAL]],
                     text=d2["Valor"].apply(lambda x: f"R$ {x/1e3:.0f}k" if x >= 1000 else f"R$ {x:.0f}").tolist())
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=13))
        fig.update_layout(coloraxis_showscale=False, xaxis_title="Valor NF (R$)")
        st.plotly_chart(fmt(fig, max(480, n_cli * 26)), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — SLA / ATRASO
# ════════════════════════════════════════════════════════════════════════════════
with tab4:

    # Nota sobre cobertura dos dados
    max_embarque = df["Embarque"].dropna().min() if "Embarque" in df.columns else None
    st.info(
        f"ℹ️ **Cobertura do relatório:** embarques de "
        f"{max_embarque:%d/%m/%Y} a {datetime.now():%d/%m/%Y} (90 dias). "
        "O **Dias em Atraso** é calculado como `hoje − Data Prazo`, "
        "portanto NFs com prazo curto embarcadas há >30 dias podem acumular atrasos elevados. "
        "NFs com atraso muito superior à janela de embarque merecem investigação individual."
    )

    st.markdown('<div class="sec">Faixas de Atraso</div>', unsafe_allow_html=True)
    if "Em Atraso" in df.columns and df["Em Atraso"].any():
        df_at = df[df["Em Atraso"]].copy()
        bins   = [0, 5, 15, 30, 60, 90, float("inf")]
        labels = ["1–5 dias","6–15 dias","16–30 dias","31–60 dias","61–90 dias","+90 dias"]
        df_at["Faixa"] = pd.cut(df_at["Dias Atraso"], bins=bins, labels=labels, right=True)

        ca, cb = st.columns(2)
        with ca:
            d = df_at["Faixa"].value_counts().reindex(labels).reset_index()
            d.columns = ["Faixa","Qtd"]
            fig = px.bar(d, x="Faixa", y="Qtd",
                         color="Qtd",
                         color_continuous_scale=[[0, AMBER],[1, SALMON]],
                         text="Qtd", title="NFs em Atraso por Faixa de Dias")
            fig.update_traces(marker_line_width=0, textposition="outside",
                              textfont=dict(size=15))
            fig.update_layout(coloraxis_showscale=False, xaxis_title="")
            st.plotly_chart(fmt(fig, 360), use_container_width=True)

        with cb:
            d2 = (df_at.groupby("Faixa", observed=True)
                       .agg(Valor=("Valor NF","sum"))
                       .reindex(labels).reset_index())
            d2.columns = ["Faixa","Valor"]
            fig = px.bar(d2, x="Faixa", y="Valor",
                         color_discrete_sequence=[SALMON],
                         text=d2["Valor"].apply(lambda x: f"R$ {x/1e3:.0f}k" if pd.notna(x) and x >= 1000 else "").tolist(),
                         title="Valor em Risco por Faixa (R$)")
            fig.update_traces(marker_line_width=0, textposition="outside",
                              textfont=dict(size=14))
            fig.update_layout(xaxis_title="")
            st.plotly_chart(fmt(fig, 360), use_container_width=True)

    st.markdown('<div class="sec">Ocorrências Mais Frequentes</div>', unsafe_allow_html=True)
    if "Ocorrência" in df.columns:
        d = df["Ocorrência"].dropna().value_counts().head(15).reset_index()
        d.columns = ["Ocorrência","Qtd"]
        fig = px.bar(d, x="Qtd", y="Ocorrência", orientation="h",
                     color_discrete_sequence=[SALMON],
                     text="Qtd")
        fig.update_traces(marker_line_width=0, textposition="outside",
                          textfont=dict(size=14))
        fig.update_layout(yaxis=dict(categoryorder="total ascending"), xaxis_title="")
        st.plotly_chart(fmt(fig, 480), use_container_width=True)

    st.markdown('<div class="sec">Atraso por Regional</div>', unsafe_allow_html=True)
    if "Região" in df.columns:
        d = df.groupby("Região").agg(
            Total=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
        ).reset_index()
        d["% Atraso"] = (d["Atraso"] / d["Total"] * 100).round(1)
        d = d.sort_values("% Atraso", ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=d["Região"], y=d["Total"],
                             name="Total", marker_color=TEAL, marker_line_width=0))
        fig.add_trace(go.Bar(x=d["Região"], y=d["Atraso"],
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", xaxis_title="")
        st.plotly_chart(fmt(fig, 360, legend_h=True), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — DADOS
# ════════════════════════════════════════════════════════════════════════════════
with tab5:

    cols_show = [c for c in [
        "NF","Status de Entrega","Filial","Filial de Entrega","Cliente",
        "Tipo Entrega","Região","Cidade","Embarque","Data Prazo",
        "Em Atraso","Dias Atraso","Peso","Valor NF",
        "Ocorrência","Subocorrencia","Obs Ocorrência","GV","Subrota",
    ] if c in df.columns]

    col_info, col_dl = st.columns([3, 1])
    with col_info:
        st.markdown(f"**{total:,.0f} registros** com os filtros atuais")
    with col_dl:
        csv = df[cols_show].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Exportar CSV", data=csv,
                           file_name=f"pendencias_{datetime.now():%Y%m%d}.csv",
                           mime="text/csv", use_container_width=True)

    st.dataframe(
        df[cols_show],
        use_container_width=True,
        height=600,
        column_config={
            "Em Atraso":   st.column_config.CheckboxColumn("Em Atraso"),
            "Dias Atraso": st.column_config.NumberColumn("Dias Atraso", format="%d d"),
            "Embarque":    st.column_config.DateColumn("Embarque",   format="DD/MM/YYYY"),
            "Data Prazo":  st.column_config.DateColumn("Data Prazo", format="DD/MM/YYYY"),
            "Valor NF":    st.column_config.NumberColumn("Valor NF",  format="R$ %.2f"),
            "Peso":        st.column_config.NumberColumn("Peso",      format="%.2f kg"),
            "Dias Atraso": st.column_config.NumberColumn("Dias Atraso", format="%d d"),
        },
    )
