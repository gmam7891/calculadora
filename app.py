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

# ===================== FORMATAÇÃO =====================
def fmt_money(v, prefix="R$ "):
    if v is None: return "-"
    return f"{prefix}{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_int(v):
    if v is None: return "-"
    return f"{int(round(v)):,}".replace(",", ".")

# ===================== CONFIG =====================
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
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Instagram + TikTok")
        fee_instagram = st.number_input("Fee / investimento (R$)", min_value=0, value=0, step=1000, key="fee_insta")
        
        st.markdown("### Reels")
        reels_qty = st.number_input("Qtd Reels", min_value=0, value=0, step=1, key="reels_qty")
        reels_avg_views = st.number_input("Views médias por Reel", min_value=0, value=0, step=1000, key="reels_views")
        reels_ctr_percent = st.number_input("CTR Reels (%)", min_value=0, value=0, step=1, key="reels_ctr")
        
        st.markdown("### Stories")
        stories_qty = st.number_input("Qtd Stories", min_value=0, value=0, step=1, key="stories_qty")
        stories_avg_views = st.number_input("Views médias por Story", min_value=0, value=0, step=1000, key="stories_views")
        stories_ctr_percent = st.number_input("CTR Stories (%)", min_value=0, value=0, step=1, key="stories_ctr")
        
        st.markdown("### TikTok")
        tiktok_qty = st.number_input("Qtd TikToks", min_value=0, value=0, step=1, key="tiktok_qty")
        tiktok_avg_views = st.number_input("Views médias por TikTok", min_value=0, value=0, step=1000, key="tiktok_views")
        tiktok_ctr_percent = st.number_input("CTR TikTok (%)", min_value=0, value=0, step=1, key="tiktok_ctr")
        
        st.markdown("### Funil")
        cvr_percent = st.number_input("CVR para FTD (%)", min_value=0, value=0, step=1, key="cvr_insta")
        value_per_ftd = st.number_input("Valor por FTD (R$)", min_value=0, value=0, step=50, key="value_ftd_insta")

    with c2:
        st.subheader("Resultados Instagram")
        res = influencer_calcs(fee=fee_instagram, reels_qty=reels_qty, reels_avg_views=reels_avg_views, 
                               reels_ctr=reels_ctr_percent/100, stories_qty=stories_qty, stories_avg_views=stories_avg_views, 
                               stories_ctr=stories_ctr_percent/100, tiktok_qty=tiktok_qty, tiktok_avg_views=tiktok_avg_views, 
                               tiktok_ctr=tiktok_ctr_percent/100, cvr_ftd=cvr_percent/100, value_per_ftd=value_per_ftd)

        st.metric("ROI", f"{res['roi']*100:.0f}%")
        st.metric("Receita", fmt_money(res["revenue"]))
        
        if st.button("📥 Baixar Relatório Instagram"):
            df = pd.DataFrame({"Métrica": ["Fee", "ROI", "Receita"], "Valor": [fee_instagram, f"{res['roi']*100:.0f}%", res["revenue"]]})
            st.download_button("Baixar CSV", df.to_csv(index=False), "relatorio_instagram.csv")

# ===================== ABA TWITCH =====================
with tabs[1]:
    st.subheader("Twitch — Virtual Casino")
    channel = st.text_input("Canal (login)", placeholder="ex: loud_coringa").lower().strip()
    
    if channel:
        stats = get_stream_stats_30d(conn, channel)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Viewers (30d)", fmt_int(stats["avg_viewers_30d"]))
        c2.metric("Peak (30d)", fmt_int(stats["peak_viewers_30d"]))
        c3.metric("Hours Watched", fmt_int(stats.get("hours_watched", 0)))
        c4.metric("Followers Gained", fmt_int(stats.get("followers_gained", 0)))
        
        st.metric("Hours Streamed", fmt_int(stats.get("hours_streamed", 0)))
        st.metric("Streams (30d)", fmt_int(stats.get("streams", 0)))

        # Valuation Twitch
        fee = st.number_input("Fee / investimento (R$)", min_value=0, value=0, step=1000)
        planned_hours = st.number_input("Horas contratadas (mês)", min_value=0, value=0, step=1)
        churn_factor = st.number_input("Fator de churn", min_value=0, value=2, step=1)
        
        ctr_percent = st.number_input("CTR Twitch (%)", min_value=0, value=0, step=1)
        cvr_percent = st.number_input("CVR para FTD (%)", min_value=0, value=0, step=1)
        value_per_ftd = st.number_input("Valor por FTD (R$)", min_value=0, value=0, step=50)

        # Cálculo simples
        unique_views = stats["avg_viewers_30d"] * planned_hours * churn_factor
        clicks = unique_views * (ctr_percent / 100)
        ftd = clicks * (cvr_percent / 100)
        revenue = ftd * value_per_ftd
        roi = ((revenue - fee) / fee * 100) if fee > 0 else 0

        st.metric("ROI Estimado", f"{roi:.1f}%")
        st.metric("Receita Projetada", fmt_money(revenue))

        if st.button("📥 Baixar Relatório Twitch"):
            df = pd.DataFrame({
                "Métrica": ["Fee", "Hours Watched", "Followers Gained", "ROI", "Receita"],
                "Valor": [fee, stats.get("hours_watched", 0), stats.get("followers_gained", 0), f"{roi:.1f}%", revenue]
            })
            st.download_button("Baixar CSV", df.to_csv(index=False), f"relatorio_twitch_{channel}.csv")

# ===================== ABA COMBINADO =====================
with tabs[2]:
    st.subheader("📊 Relatório Combinado — Instagram + Twitch")
    st.info("Use quando o streamer faz conteúdo nos dois formatos")

    nome = st.text_input("Nome do Streamer / Influenciador", placeholder="ex: loud_coringa")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Instagram")
        fee_insta = st.number_input("Fee Instagram (R$)", min_value=0, value=0, step=1000, key="fee_insta_comb")
        receita_insta = st.number_input("Receita Estimada Instagram (R$)", min_value=0, value=0, step=1000, key="rec_insta")

    with col2:
        st.subheader("Twitch")
        fee_twitch = st.number_input("Fee Twitch (R$)", min_value=0, value=0, step=1000, key="fee_twitch_comb")
        receita_twitch = st.number_input("Receita Estimada Twitch (R$)", min_value=0, value=0, step=1000, key="rec_twitch")

    total_fee = fee_insta + fee_twitch
    total_receita = receita_insta + receita_twitch
    roi_comb = ((total_receita - total_fee) / total_fee * 100) if total_fee > 0 else 0

    st.divider()
    st.subheader("Resultado Final Combinado")
    st.metric("Investimento Total", fmt_money(total_fee))
    st.metric("Receita Total", fmt_money(total_receita))
    st.metric("ROI Combinado", f"{roi_comb:.1f}%")

    if st.button("📥 Baixar Relatório Combinado"):
        df = pd.DataFrame({
            "Plataforma": ["Instagram", "Twitch", "Total"],
            "Fee (R$)": [fee_insta, fee_twitch, total_fee],
            "Receita (R$)": [receita_insta, receita_twitch, total_receita],
            "ROI": [f"{(receita_insta/fee_insta*100 if fee_insta else 0):.1f}%", 
                    f"{(receita_twitch/fee_twitch*100 if fee_twitch else 0):.1f}%", 
                    f"{roi_comb:.1f}%"]
        })
        st.download_button("Baixar CSV", df.to_csv(index=False), f"relatorio_combinado_{nome}.csv")

st.caption("App rodando 24/7 no Google Cloud")
