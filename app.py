"""
Dias+ | Dashboard de Pendências Operacionais
Hospedado via Streamlit Cloud + GitHub
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from utils.data_loader import encontrar_arquivo, carregar

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pendências | Dias+",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paleta Dias+ ──────────────────────────────────────────────────────────────
TEAL   = "#2DC5B4"
DEEP   = "#0E7A8C"
DARK   = "#0B3040"
SALMON = "#C47A77"
CORES  = [TEAL, DEEP, "#5BA8B8", "#1A8090", "#1A5A68", "#7FBFCC",
          SALMON, "#E8A5A2", "#4A9BAB", "#0D5F70"]

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif !important;
}
.block-container { padding-top: 1.2rem !important; }

/* KPI cards */
[data-testid="metric-container"] {
    background: rgba(45,197,180,0.08) !important;
    border: 1px solid rgba(45,197,180,0.28) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 13px !important;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: rgba(255,255,255,.6) !important;
}
[data-testid="stMetricValue"] {
    font-size: 36px !important;
    font-weight: 900 !important;
    font-variant-numeric: tabular-nums;
    color: #2DC5B4 !important;
}
[data-testid="stMetricDelta"] { font-size: 14px !important; }

/* Section titles */
.sec {
    font-size: 19px; font-weight: 800; color: #fff;
    text-transform: uppercase; letter-spacing: .05em;
    border-left: 4px solid #2DC5B4; padding-left: 10px;
    margin: 22px 0 12px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(11,48,64,0.95) !important;
    border-right: 1px solid rgba(45,197,180,.2) !important;
}

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Header hero ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0B2E3A 0%,#1D7A8A 100%);
            border-radius:16px;padding:28px 40px;margin-bottom:20px;
            border:1px solid rgba(45,197,180,.35)">
  <div style="font-size:clamp(28px,3.5vw,52px);font-weight:900;color:#fff;
              text-transform:uppercase;letter-spacing:.04em;line-height:1.05">
    PENDÊNCIAS <span style="color:{TEAL}">OPERACIONAIS</span>
  </div>
  <div style="font-size:16px;color:rgba(255,255,255,.6);margin-top:6px">
    Dias+ &nbsp;·&nbsp; Notas Fiscais em Aberto &nbsp;·&nbsp;
    Atualizado em {datetime.now():%d/%m/%Y %H:%M}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Carregamento de dados ─────────────────────────────────────────────────────
arquivo_auto = encontrar_arquivo()
arquivo_path = None

with st.sidebar:
    st.markdown(f"""
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:24px;
                font-weight:900;color:{TEAL};text-transform:uppercase;
                letter-spacing:.05em;margin-bottom:4px">FILTROS</div>
    """, unsafe_allow_html=True)
    st.divider()

    if arquivo_auto:
        st.success(f"📂 {arquivo_auto.name}", icon=None)
        arquivo_path = str(arquivo_auto)
    else:
        st.warning("Arquivo não encontrado automaticamente.")

    upload = st.file_uploader(
        "Carregar consolidado (.xlsx)",
        type=["xlsx"],
        help="Arquivo gerado por baixar_pendencias.py"
    )
    if upload:
        arquivo_path = upload

if arquivo_path is None:
    st.info("👈 Carregue o arquivo consolidado na barra lateral para iniciar.")
    st.stop()

df_raw = carregar(arquivo_path if isinstance(arquivo_path, str) else arquivo_path.name
                  if hasattr(arquivo_path, "name") else str(arquivo_path))

# Quando é um objeto de upload, recarrega sem cache (cache usa string do path)
if hasattr(arquivo_path, "read"):
    df_raw = carregar.__wrapped__(arquivo_path)

# ── Filtros sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    # Período de embarque
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

    def ms(label, col, df=df_raw):
        opts = sorted(df[col].dropna().unique()) if col in df.columns else []
        return st.multiselect(label, opts, placeholder="Todos")

    sel_filiais  = ms("Filial", "Filial")
    sel_status   = ms("Status de Entrega", "Status de Entrega")
    sel_clientes = ms("Cliente", "Cliente")
    sel_tipos    = ms("Tipo de Entrega", "Tipo Entrega")
    sel_regioes  = ms("Região", "Região")

    st.divider()
    so_atraso = st.toggle("Somente em atraso", value=False)
    st.divider()
    st.markdown(f"<div style='text-align:center;color:rgba(255,255,255,.35);font-size:12px'>diaslog.com.br</div>",
                unsafe_allow_html=True)

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()

if data_range and len(data_range) == 2 and "Embarque" in df.columns:
    d0, d1 = pd.Timestamp(data_range[0]), pd.Timestamp(data_range[1])
    df = df[df["Embarque"].isna() | ((df["Embarque"] >= d0) & (df["Embarque"] <= d1))]

def filtrar(df, col, sel):
    return df[df[col].isin(sel)] if sel and col in df.columns else df

df = filtrar(df, "Filial", sel_filiais)
df = filtrar(df, "Status de Entrega", sel_status)
df = filtrar(df, "Cliente", sel_clientes)
df = filtrar(df, "Tipo Entrega", sel_tipos)
df = filtrar(df, "Região", sel_regioes)

if so_atraso and "Em Atraso" in df.columns:
    df = df[df["Em Atraso"]]

# ── KPIs ──────────────────────────────────────────────────────────────────────
total      = len(df)
valor      = df["Valor NF"].sum() if "Valor NF" in df.columns else 0
peso       = df["Peso"].sum() if "Peso" in df.columns else 0
atraso     = int(df["Em Atraso"].sum()) if "Em Atraso" in df.columns else 0
pct_atraso = atraso / total * 100 if total > 0 else 0
media_dias = df.loc[df["Em Atraso"], "Dias Atraso"].mean() if "Em Atraso" in df.columns and atraso > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes",   f"{total:,.0f}")
k2.metric("Valor Total",     f"R$ {valor/1e6:.2f}M" if valor >= 1e6 else f"R$ {valor:,.0f}")
k3.metric("Peso Total",      f"{peso/1000:.1f} t" if peso >= 1000 else f"{peso:,.0f} kg")
k4.metric("Em Atraso",       f"{atraso:,.0f}", delta=f"{pct_atraso:.1f}%", delta_color="inverse")
k5.metric("Média Dias Atraso", f"{media_dias:.0f} dias")

# ── Helper de layout de gráficos ──────────────────────────────────────────────
def fmt(fig, h=340, legend_h=False):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FFFFFF", family="Barlow Condensed", size=13),
        margin=dict(l=8, r=8, t=36, b=8),
        height=h,
        legend=dict(bgcolor="rgba(0,0,0,0)",
                    orientation="h" if legend_h else "v",
                    y=1.08 if legend_h else 1),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.1)", zerolinecolor="rgba(255,255,255,.15)")
    fig.update_yaxes(gridcolor="rgba(255,255,255,.1)", zerolinecolor="rgba(255,255,255,.15)")
    return fig

# ── Seção 1: Status + Filial ──────────────────────────────────────────────────
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
        fig.update_layout(coloraxis_showscale=False,
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

with c2:
    if "Filial" in df.columns:
        d = df.groupby("Filial").agg(
            Total=("NF", "count"),
            Atraso=("Em Atraso", "sum")
        ).reset_index().sort_values("Total", ascending=False).head(15)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Total"], orientation="h",
                             name="Total", marker_color=TEAL, marker_line_width=0))
        fig.add_trace(go.Bar(y=d["Filial"], x=d["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title="Por Filial (total vs. atraso)",
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400, legend_h=True), use_container_width=True)

# ── Seção 2: Tendência semanal ────────────────────────────────────────────────
st.markdown('<div class="sec">Tendência por Embarque</div>', unsafe_allow_html=True)

if "Embarque" in df.columns:
    tmp = df.dropna(subset=["Embarque"]).copy()
    tmp["Semana"] = tmp["Embarque"].dt.to_period("W").dt.start_time
    trend = tmp.groupby("Semana").agg(
        NFs=("NF", "count"),
        Valor=("Valor NF", "sum"),
        Atraso=("Em Atraso", "sum"),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=trend["Semana"], y=trend["Atraso"],
                         name="Em Atraso", marker_color=SALMON,
                         marker_line_width=0, opacity=0.75, yaxis="y2"))
    fig.add_trace(go.Scatter(x=trend["Semana"], y=trend["NFs"],
                             mode="lines+markers", name="NFs Pendentes",
                             line=dict(color=TEAL, width=2.5),
                             marker=dict(size=6, color=TEAL)))
    fig.update_layout(
        title="NFs por Semana de Embarque",
        yaxis=dict(title="NFs"),
        yaxis2=dict(title="Em Atraso", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", color=SALMON),
        legend=dict(orientation="h", y=1.12, bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fmt(fig, 300), use_container_width=True)

# ── Seção 3: Clientes + Tipo de Entrega ──────────────────────────────────────
st.markdown('<div class="sec">Clientes e Tipo de Entrega</div>', unsafe_allow_html=True)
c3, c4 = st.columns([3, 2])

with c3:
    if "Cliente" in df.columns:
        d = df.groupby("Cliente").agg(
            Qtd=("NF", "count"), Valor=("Valor NF", "sum"), Atraso=("Em Atraso", "sum")
        ).reset_index().sort_values("Qtd", ascending=False).head(15)
        fig = px.bar(d, x="Qtd", y="Cliente", orientation="h",
                     color="Atraso",
                     color_continuous_scale=[[0, DEEP], [0.5, TEAL], [1, SALMON]],
                     title="Top 15 Clientes (cor = NFs em atraso)")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(coloraxis_showscale=True,
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

with c4:
    if "Tipo Entrega" in df.columns:
        d = df["Tipo Entrega"].value_counts().reset_index()
        d.columns = ["Tipo", "Qtd"]
        fig = px.pie(d, values="Qtd", names="Tipo",
                     color_discrete_sequence=CORES,
                     title="Por Tipo de Entrega", hole=0.45)
        fig.update_traces(
            textinfo="percent+label",
            textfont=dict(family="Barlow Condensed", size=12),
        )
        st.plotly_chart(fmt(fig, 400), use_container_width=True)

# ── Seção 4: SLA por Filial ───────────────────────────────────────────────────
if "Em Atraso" in df.columns and "Filial" in df.columns:
    st.markdown('<div class="sec">SLA por Filial</div>', unsafe_allow_html=True)
    sla = (df.groupby("Filial")
             .agg(Total=("NF", "count"), Atraso=("Em Atraso", "sum"),
                  Valor=("Valor NF", "sum"))
             .reset_index())
    sla["% Atraso"] = (sla["Atraso"] / sla["Total"] * 100).round(1)
    sla = sla.sort_values("% Atraso", ascending=False)

    fig = px.bar(sla, x="Filial", y="% Atraso",
                 color="% Atraso",
                 color_continuous_scale=[[0, TEAL], [0.4, "#E8C77A"], [1, SALMON]],
                 title="% de NFs em Atraso por Filial",
                 text="% Atraso",
                 hover_data={"Total": True, "Atraso": True, "Valor": ":,.0f"})
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                      marker_line_width=0)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fmt(fig, 300), use_container_width=True)

# ── Seção 5: Região + Ocorrências ─────────────────────────────────────────────
st.markdown('<div class="sec">Região e Ocorrências</div>', unsafe_allow_html=True)
c5, c6 = st.columns(2)

with c5:
    if "Região" in df.columns:
        d = (df.groupby("Região")
               .agg(Total=("NF","count"), Atraso=("Em Atraso","sum"), Valor=("Valor NF","sum"))
               .reset_index().sort_values("Total", ascending=False))
        fig = go.Figure()
        fig.add_trace(go.Bar(x=d["Região"], y=d["Total"],
                             name="Total", marker_color=TEAL, marker_line_width=0))
        fig.add_trace(go.Bar(x=d["Região"], y=d["Atraso"],
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay", title="Por Região")
        st.plotly_chart(fmt(fig, 320, legend_h=True), use_container_width=True)

with c6:
    if "Ocorrência" in df.columns:
        d = df["Ocorrência"].dropna().value_counts().head(12).reset_index()
        d.columns = ["Ocorrência", "Qtd"]
        fig = px.bar(d, x="Qtd", y="Ocorrência", orientation="h",
                     color_discrete_sequence=[SALMON],
                     title="Top 12 Ocorrências")
        fig.update_traces(marker_line_width=0)
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fmt(fig, 320), use_container_width=True)

# ── Seção 6: Atraso por faixa de dias ────────────────────────────────────────
if "Dias Atraso" in df.columns and df["Em Atraso"].any():
    st.markdown('<div class="sec">Faixas de Atraso</div>', unsafe_allow_html=True)
    df_at = df[df["Em Atraso"]].copy()
    bins   = [0, 5, 15, 30, 60, 90, float("inf")]
    labels = ["1-5 dias", "6-15 dias", "16-30 dias", "31-60 dias", "61-90 dias", "+90 dias"]
    df_at["Faixa"] = pd.cut(df_at["Dias Atraso"], bins=bins, labels=labels, right=True)

    c7, c8 = st.columns(2)
    with c7:
        d = df_at["Faixa"].value_counts().reindex(labels).reset_index()
        d.columns = ["Faixa", "Qtd"]
        fig = px.bar(d, x="Faixa", y="Qtd", color_discrete_sequence=[SALMON],
                     title="NFs em Atraso por Faixa de Dias", text="Qtd")
        fig.update_traces(marker_line_width=0, textposition="outside")
        st.plotly_chart(fmt(fig, 280), use_container_width=True)

    with c8:
        d = (df_at.groupby("Faixa", observed=True)
                  .agg(Valor=("Valor NF","sum"), Qtd=("NF","count"))
                  .reindex(labels).reset_index())
        d.columns = ["Faixa", "Valor", "Qtd"]
        fig = px.bar(d, x="Faixa", y="Valor",
                     color_discrete_sequence=["#C47A77"],
                     title="Valor em Risco por Faixa (R$)", text="Valor")
        fig.update_traces(marker_line_width=0,
                          texttemplate="R$ %{text:,.0f}", textposition="outside")
        st.plotly_chart(fmt(fig, 280), use_container_width=True)

# ── Tabela de dados ───────────────────────────────────────────────────────────
st.markdown('<div class="sec">Dados Filtrados</div>', unsafe_allow_html=True)

cols_show = [c for c in [
    "NF", "Status de Entrega", "Filial", "Filial de Entrega", "Cliente",
    "Tipo Entrega", "Região", "Cidade", "Embarque", "Data Prazo",
    "Em Atraso", "Dias Atraso", "Peso", "Valor NF",
    "Ocorrência", "Subocorrencia", "Obs Ocorrência", "GV", "Subrota",
] if c in df.columns]

df_show = df[cols_show].copy()

st.dataframe(
    df_show,
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

col_dl1, col_dl2, _ = st.columns([1, 1, 4])
with col_dl1:
    csv = df[cols_show].to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Exportar CSV", data=csv,
                       file_name=f"pendencias_{datetime.now():%Y%m%d}.csv",
                       mime="text/csv", use_container_width=True)
with col_dl2:
    st.caption(f"{total:,.0f} linhas · {len(cols_show)} colunas")
