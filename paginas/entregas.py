"""Página: Entregas / Produtividade de Viagens."""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from comum import (TEAL, DEEP, SALMON, AMBER, GREEN, FONT, fmt, barh,
                   lbl_int, lbl_pct, VIAGENS_CSV, cols_ocorrencia,
                   carregar_viagens_sheets, carregar_viagens_excel, header_html)

cabecalho = st.empty()

# ── Sidebar: fonte de dados ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**FONTE DE DADOS**")
    fonte = st.radio("Fonte dos dados",
                     ["☁️ Google Sheets (automático)", "📤 Enviar arquivo"],
                     label_visibility="collapsed", key="fonte_viagens")
    upload = None
    if fonte == "📤 Enviar arquivo":
        upload = st.file_uploader("Relatório de Viagens (.xlsx)", type=["xlsx"],
                                  key="up_viagens")

dfv = None
if fonte == "☁️ Google Sheets (automático)":
    try:
        dfv = carregar_viagens_sheets(VIAGENS_CSV)
        with st.sidebar:
            st.success(f"☁️ {len(dfv):,} linhas")
    except Exception as e:
        with st.sidebar:
            st.warning("Aba 'Viagens' ainda não disponível no Google Sheets. "
                       "Envie o arquivo manualmente ao lado.")
            st.caption(f"Detalhe: {e}")
        st.stop()
else:
    if upload is None:
        st.info("👈 Envie o Relatório de Viagens (.xlsx) na barra lateral.")
        st.stop()
    dfv = carregar_viagens_excel(upload.name, upload.read())
    with st.sidebar:
        st.success(f"📂 {upload.name} · {len(dfv):,} linhas")

with st.sidebar:
    if st.button("🔄 Atualizar dados", use_container_width=True, key="ref_viagens"):
        st.cache_data.clear()
        st.rerun()
    st.caption("diaslog.com.br")

# Selo de alerta: taxa de sucesso geral (dados sem filtro)
_suc = pd.to_numeric(dfv.get("Sucessos"), errors="coerce").sum() if "Sucessos" in dfv.columns else 0
_ins = pd.to_numeric(dfv.get("Insucessos"), errors="coerce").sum() if "Insucessos" in dfv.columns else 0
_taxa = _suc / (_suc + _ins) * 100 if (_suc + _ins) else 0
cabecalho.markdown(header_html("ENTREGAS",
    "Dias+ · Produtividade & Sucesso de Entregas",
    badge=f"✅ {_taxa:.1f}% DE SUCESSO", badge_cor=GREEN),
    unsafe_allow_html=True)

# ── Barra de filtros no topo ──────────────────────────────────────────────────
def ms(label, col):
    if col not in dfv.columns:
        return []
    opts = sorted(dfv[col].dropna().unique())
    return st.multiselect(label, opts, placeholder="Todos") if opts else []

with st.container(border=True):
    st.markdown("**🔍 FILTROS**")
    fc = st.columns(3)
    with fc[0]:
        sel_data = None
        if "Data Entrega" in dfv.columns and dfv["Data Entrega"].notna().any():
            dts = sorted(dfv["Data Entrega"].dropna().dt.date.unique())
            opc = ["Todas"] + [d.strftime("%d/%m/%Y") for d in dts]
            esc = st.selectbox("📅 Data de Entrega", opc, index=0)
            if esc != "Todas":
                sel_data = datetime.strptime(esc, "%d/%m/%Y").date()
    with fc[1]: sel_fil = ms("🏢 Filial", "Filial")
    with fc[2]: sel_mot = ms("🚛 Motorista", "Motorista")

# ── Aplicar filtros ───────────────────────────────────────────────────────────
d = dfv.copy()
if sel_data is not None:
    d = d[d["Data Entrega"].dt.date == sel_data]
if sel_fil:
    d = d[d["Filial"].isin(sel_fil)]
if sel_mot:
    d = d[d["Motorista"].isin(sel_mot)]

# ── KPIs ──────────────────────────────────────────────────────────────────────
def col_sum(c):
    return d[c].sum() if c in d.columns else 0

viagens   = int(col_sum("Viagens"))
entregas  = int(col_sum("Entregas"))
volumes   = int(col_sum("Volumes"))
sucessos  = int(col_sum("Sucessos"))
insucessos = int(col_sum("Insucessos"))
resolvidas = sucessos + insucessos
taxa_suc  = sucessos / resolvidas * 100 if resolvidas else 0
em_rota   = max(entregas - resolvidas, 0)
motoristas = d["Motorista"].nunique() if "Motorista" in d.columns else 0
ent_viagem = entregas / viagens if viagens else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Viagens", f"{viagens:,.0f}")
k2.metric("Entregas roteirizadas", f"{entregas:,.0f}")
k3.metric("Taxa de Sucesso", f"{taxa_suc:.1f}%",
          delta=f"{insucessos:,.0f} insucessos", delta_color="inverse")
k4.metric("Em rota", f"{em_rota:,.0f}", delta="ainda não resolvidas",
          delta_color="off")
k5.metric("Entregas/viagem", f"{ent_viagem:.0f}")
k6.metric("Motoristas", f"{motoristas:,.0f}")
st.caption("Taxa de sucesso = entregas realizadas ÷ entregas já resolvidas "
           "(sucessos + insucessos). 'Em rota' são as ainda não finalizadas no momento da extração.")

tab0, tab1, tab2, tab3 = st.tabs([
    "🚦  Visão Geral", "🚛  Motoristas", "🔎  Insucessos", "📋  Dados"])

# ── TAB 0 — Visão Geral ───────────────────────────────────────────────────────
with tab0:
    if "Filial" in d.columns:
        st.markdown('<div class="sec">Desempenho por Filial</div>', unsafe_allow_html=True)
        g = d.groupby("Filial").agg(
            Entregas=("Entregas", "sum"), Sucessos=("Sucessos", "sum"),
            Insucessos=("Insucessos", "sum"), Viagens=("Viagens", "sum")).reset_index()
        g["Resolvidas"] = g["Sucessos"] + g["Insucessos"]
        g["Sucesso%"] = (g["Sucessos"] / g["Resolvidas"].where(g["Resolvidas"] > 0)
                         * 100).round(1)
        c1, c2 = st.columns(2)
        with c1:
            g1 = g.sort_values("Entregas").tail(15)
            g1["label"] = lbl_int(g1["Entregas"])
            st.plotly_chart(barh(g1, "Entregas", "Filial",
                                 "Entregas roteirizadas por Filial (top 15)",
                                 text_col="label", cbar_title="entregas",
                                 h=max(420, len(g1) * 28)),
                            use_container_width=True)
        with c2:
            g2 = g[g["Resolvidas"] >= 20].dropna(subset=["Sucesso%"]).sort_values("Sucesso%").tail(15)
            g2["label"] = lbl_pct(g2["Sucesso%"])
            st.plotly_chart(barh(g2, "Sucesso%", "Filial",
                                 "Taxa de sucesso por Filial (mín. 20 resolvidas)",
                                 text_col="label", color_col="Sucesso%",
                                 scale=[[0, SALMON], [.6, AMBER], [1, GREEN]],
                                 cbar_title="%", h=max(420, len(g2) * 28)),
                            use_container_width=True)

    if "Modelo Veiculo" in d.columns:
        st.markdown('<div class="sec">Frota — Entregas por Modelo de Veículo</div>',
                    unsafe_allow_html=True)
        fr = d.groupby("Modelo Veiculo").agg(Entregas=("Entregas", "sum"),
                                             Viagens=("Viagens", "sum")).reset_index()
        fr = fr.sort_values("Entregas").tail(15)
        fr["label"] = lbl_int(fr["Entregas"])
        st.plotly_chart(barh(fr, "Entregas", "Modelo Veiculo",
                             "Entregas por modelo (top 15)", text_col="label",
                             cbar_title="entregas", h=max(380, len(fr) * 28)),
                        use_container_width=True)

# ── TAB 1 — Motoristas ────────────────────────────────────────────────────────
with tab1:
    if "Motorista" not in d.columns:
        st.info("Coluna de motorista não disponível.")
    else:
        n = st.slider("Motoristas exibidos", 10, 40, 20, 5, key="n_mot_viagens")
        m = d.groupby("Motorista").agg(
            Entregas=("Entregas", "sum"), Sucessos=("Sucessos", "sum"),
            Insucessos=("Insucessos", "sum"), Viagens=("Viagens", "sum")).reset_index()
        m["Resolvidas"] = m["Sucessos"] + m["Insucessos"]
        m["Sucesso%"] = (m["Sucessos"] / m["Resolvidas"].where(m["Resolvidas"] > 0)
                         * 100).round(1)

        st.markdown('<div class="sec">Produtividade — Entregas por Motorista</div>',
                    unsafe_allow_html=True)
        mp = m.sort_values("Entregas").tail(n)
        mp["label"] = lbl_int(mp["Entregas"])
        st.plotly_chart(barh(mp, "Entregas", "Motorista",
                             f"Top {n} motoristas por entregas roteirizadas",
                             text_col="label", cbar_title="entregas",
                             h=max(440, n * 26)),
                        use_container_width=True)

        st.markdown('<div class="sec">Maior nº de Insucessos</div>',
                    unsafe_allow_html=True)
        mi = m[m["Insucessos"] > 0].sort_values("Insucessos").tail(n)
        if mi.empty:
            st.success("Nenhum insucesso registrado no recorte atual.")
        else:
            mi["label"] = lbl_int(mi["Insucessos"])
            st.plotly_chart(barh(mi, "Insucessos", "Motorista",
                                 f"Top {n} motoristas por insucessos",
                                 text_col="label", color_fixed=SALMON,
                                 h=max(440, len(mi) * 26)),
                            use_container_width=True)

# ── TAB 2 — Insucessos ────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="sec">Motivos de Insucesso (Pareto)</div>',
                unsafe_allow_html=True)
    ocs = cols_ocorrencia(d)
    # Exclui a coluna de sucesso (entrega realizada) — fica só o que deu errado
    motivos = {c: d[c].sum() for c in ocs
               if "REALIZADA" not in c.upper() and d[c].sum() > 0}
    if not motivos:
        st.info("Sem motivos de insucesso no recorte atual.")
    else:
        mv = (pd.DataFrame({"Motivo": list(motivos), "Qtd": list(motivos.values())})
              .sort_values("Qtd"))
        mv["label"] = lbl_int(mv["Qtd"])
        st.plotly_chart(barh(mv.tail(15), "Qtd", "Motivo",
                             "Ocorrências de insucesso por tipo (top 15)",
                             text_col="label", color_col="Qtd",
                             scale=[[0, AMBER], [1, SALMON]], cbar_title="qtd",
                             h=max(420, min(len(mv), 15) * 32)),
                        use_container_width=True)

# ── TAB 3 — Dados ─────────────────────────────────────────────────────────────
with tab3:
    base_cols = [c for c in ["Data Entrega", "Filial", "Motorista", "Veiculo",
                             "Modelo Veiculo", "Viagens", "Entregas", "Volumes",
                             "Sucessos", "Insucessos", "Resolvidas"]
                 if c in d.columns]
    ci, cd = st.columns([3, 1])
    ci.markdown(f"**{len(d):,} linhas** com os filtros atuais")
    with cd:
        csv = d[base_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ Exportar CSV", data=csv,
                           file_name=f"viagens_{datetime.now():%Y%m%d}.csv",
                           mime="text/csv", use_container_width=True)
    st.dataframe(d[base_cols], use_container_width=True, height=560,
        column_config={
            "Data Entrega": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        })
