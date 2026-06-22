"""
Dias+ | Central de Indicadores — app multipágina.
Roteador: define o tema e navega entre Pendências e Entregas.
"""
import streamlit as st

st.set_page_config(
    page_title="Central de Indicadores | Dias+",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

from comum import inject_css
inject_css()

pg = st.navigation([
    st.Page("paginas/pendencias.py", title="Pendências", icon="📦", default=True),
    st.Page("paginas/entregas.py", title="Entregas", icon="🚚"),
], position="top")
pg.run()
