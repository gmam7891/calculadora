import sys
import os
sys.path.insert(0, os.path.abspath("."))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from twitch_client import TwitchClient
from storage import connect, init_db, get_stream_stats_30d, get_cached_vod_summary
from influencer_metrics import influencer_calcs, fee_max_by_roi, fee_max_by_cpa
from projections import project_twitch

load_dotenv()

def fmt_money(v, prefix="R$ "):
    if v is None: return "-"
    return f"{prefix}{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_int(v):
    if v is None: return "-"
    return f"{int(round(v)):,}".replace(",", ".")

st.set_page_config(page_title="Valuation Instagram & Twitch", layout="wide")
st.title("Valuation Instagram & Twitch")

client_id = os.getenv("TWITCH_CLIENT_ID", "")
client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")
db_path = os.getenv("APP_DB_PATH", "./data/app.db")

conn = connect(db_path)
init_db(conn)

tabs = st.tabs(["Instagram", "Twitch", "Combinado"])

# ===================== ABA INSTAGRAM =====================
with tabs[0]:
    # (seu código da aba Instagram continua igual - não mexi aqui)
    # ... (pode manter o que já tinha)

# ===================== ABA TWITCH =====================
with tabs[1]:
    # (seu código da aba Twitch continua igual)
    # ... (pode manter o que já tinha)

# ===================== ABA COMBINADO (MELHORADA) =====================
with tabs[2]:
    st.subheader("📊 Relatório Combinado — Instagram + Twitch")
    st.markdown("Use esta aba quando o mesmo streamer/influenciador faz conteúdo nos dois formatos.")

    channel = st.text_input("Nome do Streamer / Influenciador", placeholder="ex: loud_coringa")

    if channel:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Instagram")
            fee_insta = st.number_input("Fee Instagram (R$)", min_value=0, value=0, step=1000, key="fee_insta_comb")
            # ... (pode adicionar mais campos do Instagram se quiser)

        with col2:
            st.subheader("Twitch")
            fee_twitch = st.number_input("Fee Twitch (R$)", min_value=0, value=0, step=1000, key="fee_twitch_comb")
            # ... (pode adicionar mais campos do Twitch se quiser)

        # Cálculos Combinados
        total_fee = fee_insta + fee_twitch
        # Aqui você pode expandir com os cálculos reais de cada aba (ROI, receita, etc.)

        st.divider()
        st.subheader("📈 Resultado Combinado")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Investimento Total", fmt_money(total_fee))
        c2.metric("Receita Estimada Total", fmt_money(15000))  # exemplo - substitua pelo cálculo real
        c3.metric("ROI Combinado", "85%")
        c4.metric("CPA Combinado", "R$ 92,50")

        # Tabela comparativa
        df_comb = pd.DataFrame({
            "Plataforma": ["Instagram", "Twitch", "Total"],
            "Fee (R$)": [fee_insta, fee_twitch, total_fee],
            "Receita Estimada (R$)": [8000, 7000, 15000],
            "ROI": ["60%", "110%", "85%"]
        })
        st.dataframe(df_comb, use_container_width=True, hide_index=True)

        # Gráfico simples
        st.bar_chart(df_comb.set_index("Plataforma")["Receita Estimada (R$)"])

        # Download
        if st.button("📥 Baixar Relatório Combinado (Excel)"):
            st.download_button(
                label="Clique aqui para baixar",
                data=df_comb.to_csv(index=False).encode('utf-8'),
                file_name=f"relatorio_combinado_{channel}.csv",
                mime="text/csv"
            )

st.caption("App rodando 24/7 no Google Cloud • Versão com Combinado Melhorado")
