"""
Dias+ | Dashboard de Pendências Operacionais
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── Configuração ──────────────────────────────────────────────────────────────
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
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68", "#7FBFCC",
          SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&display=swap');
html, body, [class*="css"], .stApp {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
}
.block-container { padding-top: 1rem !important; }
[data-testid="metric-container"] {
    background: rgba(45,197,180,.08) !important;
    border: 1px solid rgba(45,197,180,.3) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
}
[data-testid="stMetricLabel"]  { font-size:13px !important; text-transform:uppercase; letter-spacing:.05em; color:rgba(255,255,255,.6) !important; }
[data-testid="stMetricValue"]  { font-size:36px !important; font-weight:900 !important; color:#2DC5B4 !important; font-variant-numeric:tabular-nums; }
[data-testid="stSidebar"]      { background:rgba(11,48,64,.95) !important; border-right:1px solid rgba(45,197,180,.2) !important; }
.sec { font-size:19px; font-weight:800; color:#fff; text-transform:uppercase; letter-spacing:.05em;
       border-left:4px solid #2DC5B4; padding-left:10px; margin:22px 0 12px; }
footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ── Constantes LGPD / datas ───────────────────────────────────────────────────
LGPD_REMOVE = ["Telefone", "Endereço", "Bairro", "CEP Destinatário", "Destinatário"]
DATE_COLS   = ["Data Pedido", "Data Emissão NF", "Embarque", "Data Prazo",
               "Data Prazo cliente", "Data última viagem", "Data ocorrência",
               "Data Registro Ocorrencia", "Data Primeira Bipagem", "Data Bipagem Filial"]
NUM_COLS    = ["Peso", "Valor NF", "Volumes"]


# ── Carregamento e tratamento ─────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dados...")
def carregar(key: str, data: bytes) -> pd.DataFrame:
    import io
    df = pd.read_excel(io.BytesIO(data), engine="openpyxl")

    # Se colunas estão como Unnamed (arquivo sem header=3 na exportação), corrige
    if df.shape[1] > 3 and all(str(c).startswith("Unnamed") for c in df.columns[:4]):
        df = pd.read_excel(io.BytesIO(data), engine="openpyxl", header=3)
        df = df.dropna(how="all")

    # LGPD
    df = df.drop(columns=[c for c in LGPD_REMOVE if c in df.columns])

    # Datas
    for col in DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    # Numéricos
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Remove linhas de cabeçalho repetidas (NF não numérico)
    if "NF" in df.columns:
        df = df[pd.to_numeric(df["NF"], errors="coerce").notna()].copy()

    # SLA
    hoje = pd.Timestamp.today().normalize()
    if "Data Prazo" in df.columns:
        df["Em Atraso"]  = df["Data Prazo"].notna() & (df["Data Prazo"] < hoje)
        df["Dias Atraso"] = (hoje - df["Data Prazo"]).dt.days.clip(lower=0)
        df.loc[~df["Em Atraso"], "Dias Atraso"] = 0

    return df


def encontrar_local() -> Path | None:
    for padrao in ["outputs/pendencias/**/*consolidado*.xlsx", "data/*.xlsx"]:
        hits = sorted(Path(".").glob(padrao), reverse=True)
        if hits:
            return hits[0]
    return None


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
            border-radius:16px;padding:26px 38px;margin-bottom:18px;
            border:1px solid rgba(45,197,180,.35)">
  <div style="font-size:clamp(26px,3.5vw,50px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05">
    PENDÊNCIAS <span style="color:{TEAL}">OPERACIONAIS</span>
  </div>
  <div style="font-size:15px;color:rgba(255,255,255,.6);margin-top:5px">
    Dias+ &nbsp;·&nbsp; Notas Fiscais em Aberto &nbsp;·&nbsp;
    {datetime.now():%d/%m/%Y %H:%M}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: fonte de dados ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<div style='font-family:Barlow Condensed,sans-serif;font-size:22px;"
                f"font-weight:900;color:{TEAL};text-transform:uppercase;"
                f"letter-spacing:.05em;margin-bottom:4px'>FILTROS</div>",
                unsafe_allow_html=True)
    st.divider()

    arquivo_local = encontrar_local()
    arquivo_bytes = None
    arquivo_key   = None

    if arquivo_local:
        st.success(f"📂 {arquivo_local.name}")
        arquivo_bytes = arquivo_local.read_bytes()
        arquivo_key   = arquivo_local.name

    upload = st.file_uploader("Carregar consolidado (.xlsx)", type=["xlsx"],
                               help="Gerado por baixar_pendencias.py")
    if upload:
        arquivo_bytes = upload.read()
        arquivo_key   = upload.name

if arquivo_bytes is None:
    st.info("👈 Carregue o arquivo consolidado na barra lateral para iniciar.")
    st.stop()

df_raw = carregar(arquivo_key, arquivo_bytes)

# ── Sidebar: filtros ──────────────────────────────────────────────────────────
with st.sidebar:

    if "Embarque" in df_raw.columns:
        datas = df_raw["Embarque"].dropna()
        if not datas.empty:
            d_min, d_max = datas.min().date(), datas.max().date()
            data_range = st.date_input("Período (Embarque)", value=(d_min, d_max),
                                        min_value=d_min, max_value=d_max)
        else:
            data_range = None
    else:
        data_range = None

    def ms(label, col):
        opts = sorted(df_raw[col].dropna().unique()) if col in df_raw.columns else []
        return st.multiselect(label, opts, placeholder="Todos")

    sel_filiais  = ms("Filial", "Filial")
    sel_status   = ms("Status de Entrega", "Status de Entrega")
    sel_clientes = ms("Cliente", "Cliente")
    sel_tipos    = ms("Tipo de Entrega", "Tipo Entrega")
    sel_regioes  = ms("Região", "Região")

    st.divider()
    so_atraso = st.toggle("Somente em atraso", value=False)
    st.divider()
    st.caption("diaslog.com.br")

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()

if data_range and len(data_range) == 2 and "Embarque" in df.columns:
    d0, d1 = pd.Timestamp(data_range[0]), pd.Timestamp(data_range[1])
    df = df[df["Embarque"].isna() | ((df["Embarque"] >= d0) & (df["Embarque"] <= d1))]

def filtrar(df, col, sel):
    return df[df[col].isin(sel)] if sel and col in df.columns else df

df = filtrar(df, "Filial",           sel_filiais)
df = filtrar(df, "Status de Entrega", sel_status)
df = filtrar(df, "Cliente",          sel_clientes)
df = filtrar(df, "Tipo Entrega",     sel_tipos)
df = filtrar(df, "Região",           sel_regioes)

if so_atraso and "Em Atraso" in df.columns:
    df = df[df["Em Atraso"]]

# ── KPIs ──────────────────────────────────────────────────────────────────────
total      = len(df)
valor      = df["Valor NF"].sum()     if "Valor NF"  in df.columns else 0
peso       = df["Peso"].sum()         if "Peso"      in df.columns else 0
atraso     = int(df["Em Atraso"].sum()) if "Em Atraso" in df.columns else 0
pct_atraso = atraso / total * 100 if total > 0 else 0
media_dias = df.loc[df["Em Atraso"], "Dias Atraso"].mean() \
             if "Em Atraso" in df.columns and atraso > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes",     f"{total:,.0f}")
k2.metric("Valor Total",       f"R$ {valor/1e6:.2f}M" if valor >= 1e6 else f"R$ {valor:,.0f}")
k3.metric("Peso Total",        f"{peso/1000:.1f} t"  if peso  >= 1000 else f"{peso:,.0f} kg")
k4.metric("Em Atraso",         f"{atraso:,.0f}", delta=f"{pct_atraso:.1f}%", delta_color="inverse")
k5.metric("Média Dias Atraso", f"{media_dias:.0f} dias")


def fmt(fig, h=340, legend_h=False):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FFFFFF", family="Barlow Condensed", size=13),
        margin=dict(l=8, r=8, t=36, b=8), height=h,
        legend=dict(bgcolor="rgba(0,0,0,0)",
                    orientation="h" if legend_h else "v",
                    y=1.1 if legend_h else 1),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.1)", zerolinecolor="rgba(255,255,255,.15)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,.1)", zerolinecolor="rgba(255,255,255,.15)")
    return fig


# ── Status + Filial ───────────────────────────────────────────────────────────
st.markdown('<div class="sec">Status de Entrega</div>', unsafe_allow_html=True)
c1, c2 = st.columns([3, 2])

with c1:
    if "Status de Entrega" in df.columns:
        d = df["Status de Entrega"].value_counts().reset_index()
        d.columns = ["Status", "Qtd"]
        fig = px.bar(d, x="Qtd", y="Status", orientation="h",
                     color="Qtd", color_continuous_scale=[[0, DEEP], [1, TEAL]],
                     title="Por Status de Entrega")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(coloraxis_showscale=False, yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

with c2:
    if "Filial" in df.columns:
        d = df.groupby("Filial").agg(Total=("NF","count"), Atraso=("Em Atraso","sum")).reset_index()
        d = d.sort_values("Total", ascending=False).head(15)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Total"],  orientation="h", name="Total",
                             marker_color=TEAL,   marker_line_width=0))
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Atraso"], orientation="h", name="Em Atraso",
                             marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title="Por Filial",
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400, legend_h=True), use_container_width=True)

# ── Tendência semanal ─────────────────────────────────────────────────────────
st.markdown('<div class="sec">Tendência por Embarque</div>', unsafe_allow_html=True)
if "Embarque" in df.columns:
    tmp = df.dropna(subset=["Embarque"]).copy()
    tmp["Semana"] = tmp["Embarque"].dt.to_period("W").dt.start_time
    trend = tmp.groupby("Semana").agg(
        NFs=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
    ).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=trend["Semana"], y=trend["Atraso"],
                         name="Em Atraso", marker_color=SALMON, marker_line_width=0,
                         opacity=0.7, yaxis="y2"))
    fig.add_trace(go.Scatter(x=trend["Semana"], y=trend["NFs"],
                             mode="lines+markers", name="NFs",
                             line=dict(color=TEAL, width=2.5), marker=dict(size=6)))
    fig.update_layout(
        title="NFs por Semana de Embarque",
        yaxis=dict(title="NFs"),
        yaxis2=dict(title="Em Atraso", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", color=SALMON),
        legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fmt(fig, 300), use_container_width=True)

# ── Clientes + Tipo Entrega ───────────────────────────────────────────────────
st.markdown('<div class="sec">Clientes e Tipo de Entrega</div>', unsafe_allow_html=True)
c3, c4 = st.columns([3, 2])

with c3:
    if "Cliente" in df.columns:
        d = df.groupby("Cliente").agg(
            Qtd=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
        ).reset_index().sort_values("Qtd", ascending=False).head(15)
        fig = px.bar(d, x="Qtd", y="Cliente", orientation="h",
                     color="Atraso",
                     color_continuous_scale=[[0, DEEP],[.5, TEAL],[1, SALMON]],
                     title="Top 15 Clientes (cor = NFs em atraso)")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

with c4:
    if "Tipo Entrega" in df.columns:
        d = df["Tipo Entrega"].value_counts().reset_index()
        d.columns = ["Tipo", "Qtd"]
        fig = px.pie(d, values="Qtd", names="Tipo",
                     color_discrete_sequence=CORES,
                     title="Por Tipo de Entrega", hole=0.45)
        fig.update_traces(textinfo="percent+label",
                          textfont=dict(family="Barlow Condensed", size=12))
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

# ── SLA por Filial ────────────────────────────────────────────────────────────
if "Em Atraso" in df.columns and "Filial" in df.columns:
    st.markdown('<div class="sec">SLA por Filial</div>', unsafe_allow_html=True)
    sla = df.groupby("Filial").agg(
        Total=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum")
    ).reset_index()
    sla["% Atraso"] = (sla["Atraso"] / sla["Total"] * 100).round(1)
    sla = sla.sort_values("% Atraso", ascending=False)
    fig = px.bar(sla, x="Filial", y="% Atraso",
                 color="% Atraso",
                 color_continuous_scale=[[0, TEAL],[.4,"#E8C77A"],[1, SALMON]],
                 title="% de NFs em Atraso por Filial", text="% Atraso",
                 hover_data={"Total":True,"Atraso":True})
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fmt(fig, 300), use_container_width=True)

# ── Região + Ocorrências ──────────────────────────────────────────────────────
st.markdown('<div class="sec">Região e Ocorrências</div>', unsafe_allow_html=True)
c5, c6 = st.columns(2)

with c5:
    if "Região" in df.columns:
        d = df.groupby("Região").agg(
            Total=("NF","count"), Atraso=("Em Atraso","sum")
        ).reset_index().sort_values("Total", ascending=False)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=d["Região"], y=d["Total"],  name="Total",
                             marker_color=TEAL,   marker_line_width=0))
        fig.add_trace(go.Bar(x=d["Região"], y=d["Atraso"], name="Em Atraso",
                             marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title="Por Região")
        st.plotly_chart(fmt(fig, 320, legend_h=True), use_container_width=True)

with c6:
    if "Ocorrência" in df.columns:
        d = df["Ocorrência"].dropna().value_counts().head(12).reset_index()
        d.columns = ["Ocorrência", "Qtd"]
        fig = px.bar(d, x="Qtd", y="Ocorrência", orientation="h",
                     color_discrete_sequence=[SALMON], title="Top 12 Ocorrências")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 320), use_container_width=True)

# ── Faixas de atraso ──────────────────────────────────────────────────────────
if "Dias Atraso" in df.columns and "Em Atraso" in df.columns and df["Em Atraso"].any():
    st.markdown('<div class="sec">Faixas de Atraso</div>', unsafe_allow_html=True)
    df_at = df[df["Em Atraso"]].copy()
    bins   = [0, 5, 15, 30, 60, 90, float("inf")]
    labels = ["1-5 d", "6-15 d", "16-30 d", "31-60 d", "61-90 d", "+90 d"]
    df_at["Faixa"] = pd.cut(df_at["Dias Atraso"], bins=bins, labels=labels, right=True)

    c7, c8 = st.columns(2)
    with c7:
        d = df_at["Faixa"].value_counts().reindex(labels).reset_index()
        d.columns = ["Faixa", "Qtd"]
        fig = px.bar(d, x="Faixa", y="Qtd", color_discrete_sequence=[SALMON],
                     title="NFs em Atraso por Faixa", text="Qtd")
        fig.update_traces(marker_line_width=0, textposition="outside")
        st.plotly_chart(fmt(fig, 280), use_container_width=True)

    with c8:
        d = (df_at.groupby("Faixa", observed=True)
                  .agg(Valor=("Valor NF","sum"))
                  .reindex(labels).reset_index())
        d.columns = ["Faixa", "Valor"]
        fig = px.bar(d, x="Faixa", y="Valor", color_discrete_sequence=["#C47A77"],
                     title="Valor em Risco por Faixa (R$)", text="Valor")
        fig.update_traces(marker_line_width=0,
                          texttemplate="R$ %{text:,.0f}", textposition="outside")
        st.plotly_chart(fmt(fig, 280), use_container_width=True)

# ── Tabela ────────────────────────────────────────────────────────────────────
st.markdown('<div class="sec">Dados Filtrados</div>', unsafe_allow_html=True)

cols_show = [c for c in [
    "NF", "Status de Entrega", "Filial", "Filial de Entrega", "Cliente",
    "Tipo Entrega", "Região", "Cidade", "Embarque", "Data Prazo",
    "Em Atraso", "Dias Atraso", "Peso", "Valor NF",
    "Ocorrência", "Subocorrencia", "Obs Ocorrência", "GV", "Subrota",
] if c in df.columns]

st.dataframe(
    df[cols_show],
    use_container_width=True,
    height=460,
    column_config={
        "Em Atraso":   st.column_config.CheckboxColumn("Em Atraso"),
        "Dias Atraso": st.column_config.NumberColumn("Dias Atraso", format="%d d"),
        "Embarque":    st.column_config.DateColumn("Embarque",   format="DD/MM/YYYY"),
        "Data Prazo":  st.column_config.DateColumn("Data Prazo", format="DD/MM/YYYY"),
        "Valor NF":    st.column_config.NumberColumn("Valor NF",  format="R$ %.2f"),
        "Peso":        st.column_config.NumberColumn("Peso",      format="%.2f kg"),
    },
)

dl1, dl2, _ = st.columns([1, 1, 4])
with dl1:
    csv = df[cols_show].to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Exportar CSV", data=csv,
                       file_name=f"pendencias_{datetime.now():%Y%m%d}.csv",
                       mime="text/csv", use_container_width=True)
with dl2:
    st.caption(f"{total:,.0f} linhas · {len(cols_show)} colunas")
