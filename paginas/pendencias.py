"""Página: Pendências Operacionais."""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from comum import (TEAL, DEEP, SALMON, AMBER, GREEN, FONT, fmt, barh,
                   lbl_int, lbl_pct, lbl_rs, eh_filial, SHEET_CSV,
                   carregar_sheets, carregar, header_html)

cabecalho = st.empty()

# ── Sidebar: fonte de dados + configuração ────────────────────────────────────
with st.sidebar:
    st.markdown("**FONTE DE DADOS**")
    fonte = st.radio("Fonte dos dados",
                     ["☁️ Google Sheets (automático)", "📤 Enviar arquivo"],
                     label_visibility="collapsed")
    upload = None
    if fonte == "📤 Enviar arquivo":
        upload = st.file_uploader("Carregar arquivo (.xlsx)", type=["xlsx"])

df_raw = None
if fonte == "☁️ Google Sheets (automático)":
    try:
        df_raw = carregar_sheets(SHEET_CSV)
        with st.sidebar:
            st.success(f"☁️ {len(df_raw):,} NFs")
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

with st.sidebar:
    meta_sla = st.number_input("🎯 Meta de SLA (%)", min_value=50, max_value=100,
                               value=95, step=1)
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("diaslog.com.br")

# Data/hora do consolidado + selo de alerta no header
_atualizado = "não informado"
if "Atualizado em" in df_raw.columns and df_raw["Atualizado em"].notna().any():
    _ts = pd.to_datetime(df_raw["Atualizado em"].dropna().iloc[0],
                         errors="coerce", dayfirst=True)
    _atualizado = _ts.strftime("%d/%m/%Y %H:%M") if pd.notna(_ts) \
                  else str(df_raw["Atualizado em"].dropna().iloc[0])
_n_atraso = int(df_raw["Atrasado"].sum()) if "Atrasado" in df_raw.columns else 0
cabecalho.markdown(header_html("INDICADORES",
    f"Dias+ · Pendências Operacionais · 🔄 Atualizado em "
    f"<b style='color:{TEAL}'>{_atualizado}</b>",
    badge=f"🔴 {_n_atraso:,} NFs EM ATRASO".replace(",", ".")),
    unsafe_allow_html=True)

# ── Barra de filtros no topo ──────────────────────────────────────────────────
def ms(label, col, only=None):
    if col not in df_raw.columns:
        return []
    vals = df_raw[col].dropna().unique()
    if only is not None:
        vals = [v for v in vals if only(v)]
    opts = sorted(vals)
    return st.multiselect(label, opts, placeholder="Todos") if opts else []

with st.container(border=True):
    st.markdown("**🔍 FILTROS**")
    r1 = st.columns(4)
    with r1[0]:
        if "Embarque" in df_raw.columns and df_raw["Embarque"].notna().any():
            datas = df_raw["Embarque"].dropna()
            d_min, d_max = datas.min().date(), datas.max().date()
            intervalo = st.date_input("📅 Período de Embarque", value=(d_min, d_max),
                                      min_value=d_min, max_value=d_max)
            data_ini = intervalo[0] if len(intervalo) > 0 else d_min
            data_fim = intervalo[1] if len(intervalo) > 1 else d_max
        else:
            data_ini = data_fim = None
    with r1[1]: sel_regional = ms("🗺️ Regional", "Regional", only=lambda r: r != "Outros")
    with r1[2]: sel_filiais = ms("🏢 Filial", "Filial", only=eh_filial)
    with r1[3]: sel_cli     = ms("👤 Cliente", "Cliente")
    r2 = st.columns(4)
    with r2[0]: sel_status  = ms("📦 Status de Entrega", "Status de Entrega")
    with r2[1]: sel_fe      = ms("🚚 Filial de Entrega", "Filial de Entrega", only=eh_filial)
    with r2[2]: sel_transp  = ms("🚛 Motorista", "Motorista")
    with r2[3]: sel_tipo    = ms("🔖 Tipo de Entrega", "Tipo Entrega")
    r3 = st.columns(4)
    with r3[0]: sel_risco   = ms("🛡️ Risco GR", "Risco GR")
    with r3[1]: so_atraso   = st.toggle("⚠️ Somente em atraso", value=False)

# ── Aplicar filtros ───────────────────────────────────────────────────────────
df = df_raw.copy()
if data_ini and data_fim and "Embarque" in df.columns:
    d0, d1 = pd.Timestamp(data_ini), pd.Timestamp(data_fim)
    df = df[df["Embarque"].isna() | ((df["Embarque"] >= d0) & (df["Embarque"] <= d1))]

def f(df, col, sel):
    return df[df[col].isin(sel)] if sel and col in df.columns else df

df = f(df, "Regional", sel_regional)
df = f(df, "Filial", sel_filiais)
df = f(df, "Filial de Entrega", sel_fe)
df = f(df, "Motorista", sel_transp)
df = f(df, "Cliente", sel_cli)
df = f(df, "Status de Entrega", sel_status)
df = f(df, "Tipo Entrega", sel_tipo)
df = f(df, "Risco GR", sel_risco)
if so_atraso:
    df = df[df["Atrasado"]]

ativos = []
if sel_regional: ativos.append(f"Regional: {', '.join(sel_regional)}")
if sel_filiais: ativos.append(f"Filial: {len(sel_filiais)}")
if sel_fe:      ativos.append(f"Fil.Entrega: {len(sel_fe)}")
if sel_transp:  ativos.append(f"Motorista: {len(sel_transp)}")
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
n_transp = df.loc[df["Motorista"] != "Sem motorista", "Motorista"].nunique() \
           if "Motorista" in df.columns else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("NFs Pendentes", f"{total:,.0f}")
k2.metric("Em Atraso", f"{atraso:,.0f}", delta=f"{pct_at:.1f}% do total",
          delta_color="inverse")
k3.metric("Valor em Risco", f"R$ {valor_risco/1e6:.2f}M" if valor_risco >= 1e6
          else f"R$ {valor_risco:,.0f}")
k4.metric("Parado +7 dias", f"{parado7:,.0f}", delta="na filial", delta_color="off")
k5.metric("Motoristas", f"{n_transp:,.0f}")
st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚦  Resumo Executivo",
    "🏢  Filiais",
    "🚚  Motoristas",
    "🔎  Causa-Raiz",
    "⏱️  Aging & Risco",
    "👤  Clientes",
    "📋  Dados",
])

# ── TAB 0 — Resumo Executivo ──────────────────────────────────────────────────
with tab0:
    sla_atual = round(100 - pct_at, 1)
    st.markdown('<div class="sec">SLA Geral vs Meta</div>', unsafe_allow_html=True)
    gc1, gc2 = st.columns([2, 3])
    with gc1:
        cor_sla = GREEN if sla_atual >= meta_sla else SALMON
        gfig = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=sla_atual,
            number={"suffix": "%", "font": {"size": 46, "color": cor_sla}},
            delta={"reference": meta_sla, "suffix": " p.p.",
                   "increasing": {"color": GREEN}, "decreasing": {"color": SALMON}},
            gauge={"axis": {"range": [0, 100], "tickfont": {"color": "#fff"}},
                   "bar": {"color": cor_sla},
                   "threshold": {"line": {"color": "#fff", "width": 3},
                                 "value": meta_sla},
                   "steps": [{"range": [0, meta_sla], "color": "rgba(196,122,119,.25)"},
                             {"range": [meta_sla, 100], "color": "rgba(91,196,138,.25)"}]},
        ))
        gfig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=240,
                           margin=dict(l=20, r=20, t=10, b=10),
                           font=dict(family=FONT, color="#fff"))
        st.plotly_chart(gfig, use_container_width=True)
    with gc2:
        no_prazo = total - atraso
        st.markdown(
            f"""<div style="padding:14px 4px;font-family:{FONT}">
            <div style="font-size:17px;color:rgba(255,255,255,.8)">
            Das <b>{total:,.0f}</b> NFs pendentes, <b style="color:{GREEN}">{no_prazo:,.0f}</b>
            estão no prazo e <b style="color:{SALMON}">{atraso:,.0f}</b> em atraso.</div>
            <div style="font-size:17px;margin-top:10px;color:rgba(255,255,255,.8)">
            SLA atual: <b style="color:{('#5BC48A' if sla_atual>=meta_sla else '#C47A77')}">
            {sla_atual:.1f}%</b> &nbsp;·&nbsp; Meta: <b>{meta_sla}%</b> &nbsp;·&nbsp;
            Gap: <b>{sla_atual-meta_sla:+.1f} p.p.</b></div>
            <div style="font-size:15px;margin-top:10px;color:rgba(255,255,255,.55)">
            Valor parado em atraso: <b style="color:{SALMON}">R$ {valor_risco/1e6:.2f}M</b></div>
            </div>""".replace(",", "."), unsafe_allow_html=True)

    if "Regional" in df.columns and (df["Regional"] != "Outros").any():
        st.markdown('<div class="sec">Visão por Regional</div>', unsafe_allow_html=True)
        reg = df[df["Regional"] != "Outros"].groupby("Regional").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        reg["% Atraso"] = (reg["Atraso"] / reg["Total"] * 100).round(1)
        rc1, rc2 = st.columns(2)
        with rc1:
            reg1 = reg.sort_values("Total")
            reg1["label"] = lbl_int(reg1["Total"])
            st.plotly_chart(barh(reg1, "Total", "Regional", "NFs Pendentes por Regional",
                                 text_col="label", cbar_title="NFs", h=300),
                            use_container_width=True)
        with rc2:
            reg2 = reg.sort_values("% Atraso")
            reg2["label"] = lbl_pct(reg2["% Atraso"])
            st.plotly_chart(barh(reg2, "% Atraso", "Regional", "% em Atraso por Regional",
                                 text_col="label", color_col="% Atraso",
                                 scale=[[0, GREEN], [.4, AMBER], [1, SALMON]],
                                 cbar_title="%", h=300),
                            use_container_width=True)

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

    st.markdown('<div class="sec">Evolução do SLA (mensal)</div>', unsafe_allow_html=True)
    if "Embarque" in df.columns and df["Embarque"].notna().any():
        tmp = df.dropna(subset=["Embarque"]).copy()
        tmp["Mês"] = tmp["Embarque"].dt.to_period("M").dt.start_time
        ev = tmp.groupby("Mês").agg(Total=("NF", "count"),
                                    Atraso=("Atrasado", "sum")).reset_index()
        ev = ev[ev["Total"] >= 20]
        ev["SLA"] = ((ev["Total"] - ev["Atraso"]) / ev["Total"] * 100).round(1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ev["Mês"], y=ev["SLA"], mode="lines+markers+text",
                                 line=dict(color=TEAL, width=3),
                                 marker=dict(size=8, color=TEAL),
                                 text=[f"{v:.0f}%" for v in ev["SLA"]],
                                 textposition="top center",
                                 textfont=dict(size=13, color="#fff", family=FONT),
                                 name="SLA"))
        fig.add_hline(y=meta_sla, line_dash="dash", line_color=AMBER,
                      annotation_text=f"Meta {meta_sla}%",
                      annotation_font=dict(color=AMBER, size=13))
        fig.update_layout(title="% de NFs no prazo por mês de embarque",
                          yaxis=dict(title="SLA %", range=[0, 105]))
        st.plotly_chart(fmt(fig, 340), use_container_width=True)

    st.markdown('<div class="sec">🔥 Top Ofensores — maior valor parado em atraso</div>',
                unsafe_allow_html=True)
    of = df[df["Atrasado"]].copy()
    if of.empty:
        st.success("Sem NFs em atraso no recorte atual.")
    else:
        cols_of = [c for c in ["NF", "Filial", "Cliente", "Motorista", "Dias Atraso",
                               "Valor NF", "Status de Entrega", "Ocorrência"]
                   if c in of.columns]
        of = of.sort_values("Valor NF", ascending=False).head(20)[cols_of]
        st.caption("As 20 NFs em atraso de maior valor — priorize estas para destravar caixa.")
        st.dataframe(of, use_container_width=True, hide_index=True, height=420,
            column_config={
                "Dias Atraso": st.column_config.NumberColumn("Atraso", format="%d d"),
                "Valor NF": st.column_config.NumberColumn("Valor NF", format="R$ %.2f"),
            })

    st.markdown('<div class="sec">Concentração de Risco</div>', unsafe_allow_html=True)
    dims = [d for d in ["Cliente", "Filial", "Motorista"] if d in df.columns]
    if dims and "Valor NF" in df.columns:
        cd1, cd2 = st.columns([1, 3])
        with cd1:
            dim = st.radio("Concentração por", dims, key="conc_dim")
        dfc = df[df["É Filial"]] if (dim == "Filial" and "É Filial" in df.columns) else df
        g = (dfc.groupby(dim).agg(Valor=("Valor NF", "sum"), NFs=("NF", "count"))
             .reset_index().sort_values("Valor", ascending=False))
        g = g[g["Valor"] > 0]
        if not g.empty:
            tot = g["Valor"].sum()
            g["acum%"] = (g["Valor"].cumsum() / tot * 100)
            def share(n):
                return g.head(n)["Valor"].sum() / tot * 100 if tot else 0
            with cd1:
                st.metric(f"Top 5 {dim.lower()}s", f"{share(5):.0f}%",
                          help="Participação dos 5 maiores no valor total em aberto")
                st.metric(f"Top 10 {dim.lower()}s", f"{share(10):.0f}%")
                st.caption(f"{len(g)} {dim.lower()}s no total")
            with cd2:
                gp = g.head(15)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=gp[dim], y=gp["Valor"], name="Valor",
                                     marker_color=TEAL, marker_line_width=0))
                fig.add_trace(go.Scatter(x=gp[dim], y=gp["acum%"], name="% acumulado",
                                         yaxis="y2", mode="lines+markers",
                                         line=dict(color=SALMON, width=3),
                                         marker=dict(size=6, color=SALMON)))
                fig.add_hline(y=80, line_dash="dash", line_color=AMBER, yref="y2",
                              annotation_text="80%", annotation_font=dict(color=AMBER))
                fig.update_layout(
                    title=f"Curva de Pareto — valor em aberto por {dim.lower()} (top 15)",
                    yaxis=dict(title="Valor (R$)"),
                    yaxis2=dict(title="% acumulado", overlaying="y", side="right",
                                range=[0, 105], color=SALMON,
                                tickfont=dict(color=SALMON, size=13)))
                fig.update_xaxes(tickangle=-40)
                st.plotly_chart(fmt(fig, 380, legend_h=True), use_container_width=True)

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

# ── TAB 2 — Motoristas ────────────────────────────────────────────────────────
with tab2:
    if "Motorista" not in df.columns:
        st.info("Coluna de motorista não disponível neste arquivo.")
    else:
        dft = df[df["Motorista"] != "Sem motorista"]
        n = st.slider("Motoristas exibidos", 10, 40, 20, 5)

        st.markdown('<div class="sec">Top Motoristas — Volume vs. Atraso</div>',
                    unsafe_allow_html=True)
        t = dft.groupby("Motorista").agg(
            Total=("NF", "count"), Atraso=("Atrasado", "sum"),
            Valor=("Valor NF", "sum")).reset_index()
        t["% Atraso"] = (t["Atraso"] / t["Total"] * 100).round(1)
        top = t.sort_values("Total", ascending=True).tail(n)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=top["Motorista"], x=top["Total"], orientation="h",
                             name="Total", marker_color=TEAL, marker_line_width=0,
                             text=lbl_int(top["Total"]), textposition="outside",
                             textfont=dict(size=13, color="#fff", family=FONT)))
        fig.add_trace(go.Bar(y=top["Motorista"], x=top["Atraso"], orientation="h",
                             name="Em Atraso", marker_color=SALMON, marker_line_width=0))
        fig.update_layout(barmode="overlay",
                          title=f"Top {n} Motoristas — NFs vs. Atraso",
                          yaxis=dict(categoryorder="total ascending", automargin=True))
        st.plotly_chart(fmt(fig, max(460, n * 28), legend_h=True),
                        use_container_width=True)

        st.markdown('<div class="sec">Piores % de Atraso (mín. 50 NFs)</div>',
                    unsafe_allow_html=True)
        rel = t[t["Total"] >= 50].sort_values("% Atraso").tail(n)
        rel["label"] = lbl_pct(rel["% Atraso"])
        st.plotly_chart(barh(rel, "% Atraso", "Motorista",
                             "Motoristas com maior % de atraso (≥50 NFs)",
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
        "Motorista", "Cliente", "Tipo Entrega", "Embarque", "Data Prazo",
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
