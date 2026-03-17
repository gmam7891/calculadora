import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re
import statistics
from typing import Dict, Any, List, Optional
import streamlit as st
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
from twitch_client import TwitchClient
from storage import connect, init_db, get_stream_stats_30d, upsert_vod_summary, get_cached_vod_summary
from influencer_metrics import influencer_calcs, fee_max_by_roi, fee_max_by_cpa
from projections import project_twitch
load_dotenv()

# ==================== FUNÇÕES DE FORMATAÇÃO ====================
def fmt_money(v, prefix="R$ "):
    if v is None:
        return "-"
    return f"{prefix}{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_int(v):
    if v is None:
        return "-"
    try:
        return f"{int(round(v)):,}".replace(",", ".")
    except Exception:
        return "-"

def fmt_float(v, nd=2):
    if v is None:
        return "-"
    return f"{v:.{nd}f}".replace(".", ",")

def parse_twitch_duration_to_hours(s: str) -> float:
    if not s:
        return 0.0
    h = m = sec = 0
    mh = re.search(r"(\d+)h", s)
    mm = re.search(r"(\d+)m", s)
    ms = re.search(r"(\d+)s", s)
    if mh:
        h = int(mh.group(1))
    if mm:
        m = int(mm.group(1))
    if ms:
        sec = int(ms.group(1))
    return h + (m / 60) + (sec / 3600)

def vod_summary(vods: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not vods:
        return {"vod_count": 0, "avg_vod_views": None, "median_vod_views": None, "views_per_hour": None}
    views = [int(v.get("view_count", 0)) for v in vods]
    hours = [parse_twitch_duration_to_hours(v.get("duration", "")) for v in vods]
    total_views = sum(views)
    total_hours = sum(hours)
    avg_v = (total_views / len(views)) if views else None
    med_v = float(statistics.median(views)) if views else None
    vph = (total_views / total_hours) if total_hours > 0 else None
    return {"vod_count": len(vods), "avg_vod_views": avg_v, "median_vod_views": med_v, "views_per_hour": vph}

# ==================== FUNÇÃO DEMOGRÁFICA ICP ====================
def calcular_viabilidade_audiencia(dados: Dict[str, Any]) -> Dict[str, Any]:
    total_seguidores = dados.get("totalSeguidores", 0)
    perc_idade = dados.get("percIdade", 0.0)
    perc_pais = dados.get("percPais", 0.0)
    perc_genero = dados.get("percGenero", 0.0)
    taxa_engajamento = dados.get("taxaEngajamento", 0.0)
    fee = dados.get("fee", 0)
    cvr_ftd = dados.get("cvr_ftd", 0.0)
    value_per_ftd = dados.get("value_per_ftd", 0)
    tamanho_base = dados.get("tamanhoBase", 10000)

    seguidores_potenciais = total_seguidores * perc_idade * perc_pais * perc_genero
    leads_estimados = seguidores_potenciais * taxa_engajamento
    ftd_estimado = leads_estimados * cvr_ftd
    receita_estimada = ftd_estimado * value_per_ftd
    roi = ((receita_estimada - fee) / fee * 100) if fee > 0 else 0
    cpa = (fee / ftd_estimado) if ftd_estimado > 0 else None
    crescimento_base = (leads_estimados / tamanho_base) * 100 if tamanho_base > 0 else 0

    return {
        "seguidores_potenciais": round(seguidores_potenciais),
        "leads_estimados": round(leads_estimados),
        "ftd_estimado": round(ftd_estimado),
        "receita_estimada": round(receita_estimada),
        "roi": round(roi, 1),
        "cpa": round(cpa, 2) if cpa is not None else None,
        "crescimento_base": round(crescimento_base, 2),
        "viabilidade": "✅ MUITO VIÁVEL" if roi >= 200 else "⚠️ VIÁVEL" if roi >= 100 else "❌ NÃO VIÁVEL"
    }

# ==================== CONFIGURAÇÃO DO APP ====================
st.set_page_config(page_title="Valuation Instagram & Twitch", layout="wide")
st.markdown("""
    <style>
        .main .block-container { padding-top: 0.5rem !important; }
        .stImage { margin-top: -60px !important; margin-bottom: -20px !important; }
    </style>
""", unsafe_allow_html=True)
st.image("logo_gmcr.png", width=300)
st.title("Valuation Instagram & Twitch")

client_id = os.getenv("TWITCH_CLIENT_ID", "")
client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")
db_path = os.getenv("APP_DB_PATH", "./data/app.db")
conn = connect(db_path)
init_db(conn)

tabs = st.tabs(["Instagram", "Twitch", "Calculadora ICP", "Analisador de VOD"])

# ==================== ABA INSTAGRAM ====================
with tabs[0]:
    st.subheader("Instagram — Valuation com filtro de audiência ICP")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("### Audiência Qualificada (ICP)")
        total_seguidores = st.number_input(
            "Total de seguidores (Instagram)",
            min_value=0, value=0, step=1000, key="seguidores_total_inst"
        )
        
        perc_icp = st.number_input(
            "% de seguidores que são compradores em potencial (ICP)",
            min_value=0.0, max_value=100.0, value=0.0, step=0.1, format="%.1f",
            key="perc_icp_inst"
        ) / 100.0
        
        compradores_potenciais = int(total_seguidores * perc_icp)
        st.metric("**Compradores reais potenciais (ICP)**", fmt_int(compradores_potenciais))
        
        st.markdown("---")
        
        st.markdown("### Reels")
        reels_qty = st.number_input("Qtd Reels", min_value=0, value=0, step=1, key="reels_qty_inst")
        reels_avg_views = st.number_input("Views médias por Reel (bruto)", min_value=0, value=0, step=1000, key="reels_views_inst")
        reels_ctr_percent = st.number_input("CTR Reels (%)", min_value=0.0, value=0.0, step=0.1, key="reels_ctr_inst")
        
        st.markdown("### Stories")
        stories_qty = st.number_input("Qtd Stories", min_value=0, value=0, step=1, key="stories_qty_inst")
        stories_avg_views = st.number_input("Views médias por Story (bruto)", min_value=0, value=0, step=500, key="stories_views_inst")
        stories_ctr_percent = st.number_input("CTR Stories (%)", min_value=0.0, value=0.0, step=0.1, key="stories_ctr_inst")
        
        st.markdown("### Funil (conversão)")
        manual_clicks = st.number_input("Cliques reais (total) — deixe 0 para calcular", min_value=0, value=0, step=50, key="manual_clicks_inst")
        manual_ftd = st.number_input("FTD real (total) — deixe 0 para calcular", min_value=0, value=0, step=1, key="manual_ftd_inst")
        cvr_percent = st.number_input("CVR para FTD (%)", min_value=0.0, value=0.0, step=0.1, key="cvr_percent_inst")
        value_per_ftd = st.number_input("Valor médio por FTD (R$)", min_value=0, value=0, step=50, key="value_per_ftd_inst")
        
        fee_instagram = st.number_input(
            "Fee / investimento (R$)",
            min_value=0, value=0, step=1000, key="fee_instagram"
        )
        
        st.markdown("### Metas desejadas")
        roi_percent_target = st.number_input("ROI alvo (%)", min_value=0, value=0, step=10, key="roi_target_inst")
        target_roi = roi_percent_target / 100.0
        
        target_cpa = st.number_input("CPA alvo (R$)", min_value=0.0, value=0.0, step=10.0, key="cpa_target_inst")

    with c2:
        st.subheader("Resultados")
        
        perc_icp_ajustada = perc_icp if perc_icp > 0 else 1.0
        
        reels_views_brutas   = reels_qty * reels_avg_views
        stories_views_brutas = stories_qty * stories_avg_views
        
        reels_views_efetivas   = reels_views_brutas   * perc_icp_ajustada
        stories_views_efetivas = stories_views_brutas * perc_icp_ajustada
        
        total_views_qualificadas = reels_views_efetivas + stories_views_efetivas
        
        reels_ctr   = reels_ctr_percent   / 100
        stories_ctr = stories_ctr_percent / 100
        cvr_ftd     = cvr_percent         / 100
        
        if manual_clicks > 0:
            clicks = manual_clicks
        else:
            clicks_reels   = reels_views_efetivas   * reels_ctr
            clicks_stories = stories_views_efetivas * stories_ctr
            clicks = clicks_reels + clicks_stories
        
        if manual_ftd > 0:
            ftd = manual_ftd
        else:
            ftd = clicks * cvr_ftd
        
        revenue = ftd * value_per_ftd
        fee = fee_instagram
        
        roi = ((revenue - fee) / fee * 100) if fee > 0 else 0
        cpa = (fee / ftd) if ftd > 0 else None
        
        # Métricas principais
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Views qualificadas (após ICP)", fmt_int(total_views_qualificadas))
        col_b.metric("Cliques estimados", fmt_int(clicks))
        col_c.metric("FTD projetado", fmt_int(ftd))
        
        col_d, col_e, col_f = st.columns(3)
        col_d.metric("Receita projetada", fmt_money(revenue))
        col_e.metric("ROI", f"{roi:.1f}%")
        col_f.metric("CPA", fmt_money(cpa))
        
        # Feedback de lucratividade (exatamente como na aba Twitch)
        st.markdown("### Avaliação em relação às metas")
        if roi >= target_roi and (cpa is None or cpa <= target_cpa):
            st.success("✅ LUCRATIVO")
        elif roi >= 0:
            st.warning("⚠️ Margem positiva")
        else:
            st.error("❌ PREJUÍZO")
        
        st.markdown("---")
        
        # Exportar
        st.subheader("Exportar resultados")
        
        dados = {
            "Total Seguidores": total_seguidores,
            "% ICP": perc_icp * 100,
            "Compradores Potenciais": compradores_potenciais,
            "Qtd Reels": reels_qty,
            "Views Reels Brutas": reels_views_brutas,
            "Views Reels Qualificadas": round(reels_views_efetivas),
            "CTR Reels (%)": reels_ctr_percent,
            "Qtd Stories": stories_qty,
            "Views Stories Brutas": stories_views_brutas,
            "Views Stories Qualificadas": round(stories_views_efetivas),
            "CTR Stories (%)": stories_ctr_percent,
            "Cliques Estimados": clicks,
            "FTD Projetado": ftd,
            "Receita Projetada (R$)": revenue,
            "Fee (R$)": fee,
            "ROI (%)": round(roi, 1) if fee > 0 else None,
            "CPA (R$)": round(cpa, 2) if cpa is not None else None,
            "ROI Alvo (%)": roi_percent_target,
            "CPA Alvo (R$)": target_cpa
        }
        
        df = pd.DataFrame([dados])  # uma linha só
        
        from io import BytesIO
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Valuation Instagram")
        buffer.seek(0)
        
        st.download_button(
            label="Baixar em Excel (.xlsx)",
            data=buffer,
            file_name=f"valuation_instagram_{total_seguidores or 'sem_dados'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_instagram"
        )
        
        # ==================== CÁLCULO OBRIGATÓRIO COM ICP ====================
        perc_icp_ajustada = perc_icp if perc_icp > 0 else 1.0
        
        # Views brutas (digitadas pelo usuário)
        reels_views_brutas = reels_qty * reels_avg_views
        stories_views_brutas = stories_qty * stories_avg_views
        
        # Views qualificadas = bruto × % ICP (exatamente como você pediu)
        reels_views_efetivas   = reels_views_brutas   * perc_icp_ajustada
        stories_views_efetivas = stories_views_brutas * perc_icp_ajustada
        
        total_views_qualificadas = reels_views_efetivas + stories_views_efetivas
        
        reels_ctr   = reels_ctr_percent   / 100
        stories_ctr = stories_ctr_percent / 100
        cvr_ftd     = cvr_percent         / 100
        
        # Cliques e FTD
        if manual_clicks > 0:
            clicks = manual_clicks
        else:
            clicks_reels   = reels_views_efetivas   * reels_ctr
            clicks_stories = stories_views_efetivas * stories_ctr
            clicks = clicks_reels + clicks_stories
        
        if manual_ftd > 0:
            ftd = manual_ftd
        else:
            ftd = clicks * cvr_ftd
        
        revenue = ftd * value_per_ftd
        fee = fee_instagram
        
        roi = ((revenue - fee) / fee * 100) if fee > 0 else 0
        cpa = (fee / ftd) if ftd > 0 else None
        
        # ==================== MÉTRICAS (sem aviso de lucro/prejuízo) ====================
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Views qualificadas (após ICP)", fmt_int(total_views_qualificadas))
        col_b.metric("Cliques estimados", fmt_int(clicks))
        col_c.metric("FTD projetado", fmt_int(ftd))
        
        col_d, col_e, col_f = st.columns(3)
        col_d.metric("Receita projetada", fmt_money(revenue))
        col_e.metric("ROI", f"{roi:.0f}%")
        col_f.metric("CPA", fmt_money(cpa))
        
        st.markdown("---")
        
        # ==================== DOWNLOAD EXCEL ====================
        st.subheader("📥 Baixar relatório completo")
        
        dados_relatorio = {
            "Total de Seguidores": [total_seguidores],
            "% ICP": [perc_icp * 100],
            "Compradores Potenciais (ICP)": [compradores_potenciais],
            "Qtd Reels": [reels_qty],
            "Views Reels Brutas": [reels_views_brutas],
            "Views Reels Qualificadas": [reels_views_efetivas],
            "CTR Reels (%)": [reels_ctr_percent],
            "Qtd Stories": [stories_qty],
            "Views Stories Brutas": [stories_views_brutas],
            "Views Stories Qualificadas": [stories_views_efetivas],
            "CTR Stories (%)": [stories_ctr_percent],
            "Cliques Estimados": [clicks],
            "FTD Projetado": [ftd],
            "Receita Projetada (R$)": [revenue],
            "Fee / Investimento (R$)": [fee],
            "ROI (%)": [round(roi, 1)],
            "CPA (R$)": [round(cpa, 2) if cpa is not None else None]
        }
        
        df = pd.DataFrame(dados_relatorio)
        
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        
        st.download_button(
            label="📥 Baixar tudo em Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"Instagram_ICP_Valuation_{total_seguidores}_seguidores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.caption("O arquivo contém todas as entradas + cálculos com o filtro ICP aplicado nas views.")

# ==================== ABA TWITCH ====================
with tabs[1]:
    st.subheader("Twitch — Virtual Casino")
    tc = None
    if client_id and client_secret:
        try:
            tc = TwitchClient(client_id, client_secret)
        except Exception:
            tc = None
    left, right = st.columns([1, 2])
    with left:
        channel = st.text_input("Canal (login)", value="", placeholder="Digite o login aqui").lower().strip()
        fee = st.number_input("Fee / investimento (R$)", min_value=0, value=0, step=1000)
        planned_hours = st.number_input("Horas contratadas (mês)", min_value=0, value=0, step=1)
        churn_factor = st.number_input("Fator de churn (views únicas)", min_value=0, value=0, step=1)
        vod_n = st.number_input("VODs para média (últimos N)", min_value=0, value=0, step=1)
    with right:
        if not channel:
            st.info("Digite o login do canal acima.")
        else:
            stats = get_stream_stats_30d(conn, channel)
            avg_30d = stats["avg_viewers_30d"]
            peak_30d = stats["peak_viewers_30d"]
            is_live_now = False
            live_viewers_now = None
            is_casino = False
            if tc:
                try:
                    live_map = tc.get_streams_by_logins([channel])
                    s = live_map.get(channel)
                    if s:
                        is_live_now = True
                        live_viewers_now = int(s.get("viewer_count", 0))
                        is_casino = str(s.get("game_id")) == "29452"
                except Exception:
                    pass
            vod_cached = get_cached_vod_summary(conn, channel, max_age_hours=12)
            top = st.columns(6)
            top[0].metric("Status agora", "✅ LIVE" if is_live_now else "⭕ OFF")
            top[1].metric("Viewers agora", fmt_int(live_viewers_now))
            top[2].metric("Avg viewers (30d)", fmt_int(avg_30d))
            top[3].metric("Peak (30d)", fmt_int(peak_30d))
            if not is_casino and is_live_now:
                st.error("❌ Canal não está em Virtual Casino.")
            st.markdown("---")
            st.subheader("💰 Valuation Financeiro (Fee Independente)")
            roi_percent_tw = st.number_input("ROI alvo (%)", min_value=0, value=0, step=5, key="roi_tw")
            target_roi_tw = roi_percent_tw / 100.0
            target_cpa_tw = st.number_input("CPA alvo (R$)", min_value=0, value=0, step=25, key="cpa_tw")
            ctr_percent_tw = st.number_input("CTR Twitch (%)", min_value=0, value=0, step=1, key="ctr_tw")
            cvr_percent_tw = st.number_input("CVR para FTD (%)", min_value=0, value=0, step=1, key="cvr_tw")
            value_per_ftd_tw = st.number_input("Valor por FTD (R$)", min_value=0, value=0, step=50, key="vftd_tw")
            twitch_ctr = ctr_percent_tw / 100.0
            twitch_cvr = cvr_percent_tw / 100.0
            proj = project_twitch(
                planned_hours=planned_hours,
                avg_viewers_30d=avg_30d,
                peak_30d=peak_30d,
                churn_factor=churn_factor,
                vod_views_per_hour=vod_cached["views_per_hour"] if vod_cached else None,
            )
            unique_views = proj.get("projected_unique_views", 0) or 0
            clicks = unique_views * twitch_ctr
            ftd = clicks * twitch_cvr
            revenue = ftd * value_per_ftd_tw
            roi = ((revenue - fee) / fee) if fee > 0 else 0
            cpa = (fee / ftd) if ftd > 0 else None
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Cliques estimados", fmt_int(clicks))
            tc2.metric("FTD projetado", fmt_int(ftd))
            tc3.metric("Receita projetada", fmt_money(revenue))
            tc4.metric("ROAS", fmt_int(revenue / fee if fee > 0 else 0))
            td1, td2, td3, td4 = st.columns(4)
            td1.metric("CPA (FTD)", fmt_money(cpa))
            td2.metric("ROI", f"{roi*100:.0f}%")
            td3.metric("Lucro/Prejuízo", fmt_money(revenue - fee))
            td4.metric("Fee máximo", fmt_money(fee_max_by_roi(revenue, target_roi_tw)))
            if fee > 0:
                if roi >= target_roi_tw and (cpa is None or cpa <= target_cpa_tw):
                    st.success("✅ LUCRATIVO")
                elif roi >= 0:
                    st.warning("⚠️ Margem positiva")
                else:
                    st.error("❌ PREJUÍZO")

# ==================== ABA CALCULADORA DEMOGRÁFICA ICP (AGORA TODOS ZERADOS) ====================
with tabs[2]:
    st.title("🎯 Calculadora Demográfica ICP")
    st.markdown("Descubra qual **% real** da audiência do influenciador é potencial cliente (ICP).")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📊 Dados do Influenciador")
        total_seguidores = st.number_input(
            "Total de Seguidores",
            min_value=0,
            value=0,
            step=1000,
            key="demo_seguidores"
        )

        st.markdown("**Filtros do ICP (perfil ideal do cliente)**")
        perc_idade = st.number_input(
            "% Idade que bate com ICP",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            format="%.1f",
            key="demo_idade"
        ) / 100.0

        perc_pais = st.number_input(
            "% no País-alvo (ex: Brasil)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            format="%.1f",
            key="demo_pais"
        ) / 100.0

        perc_genero = st.number_input(
            "% Gênero que bate com ICP",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            format="%.1f",
            key="demo_genero"
        ) / 100.0

        st.markdown("**Engajamento esperado**")
        taxa_engajamento = st.number_input(
            "Taxa de Engajamento realista (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            format="%.2f",
            key="demo_eng"
        ) / 100.0

        st.markdown("---")
        st.caption("Opcional: comparação com sua base atual")
        tamanho_base = st.number_input(
            "Tamanho da sua base atual de leads/clientes",
            min_value=0,
            value=0,
            step=500,
            key="demo_base"
        )

    with col2:
        st.subheader("📈 Alcance Real do ICP")

        if total_seguidores > 0 and (perc_idade > 0 or perc_pais > 0 or perc_genero > 0):
            # Cálculo em etapas (mais transparente)
            potenciais_brutos = total_seguidores * perc_idade * perc_pais * perc_genero
            perc_icp_final = (potenciais_brutos / total_seguidores) * 100 if total_seguidores > 0 else 0.0

            leads_estimados = potenciais_brutos * taxa_engajamento

            # Métricas principais
            st.metric("**% real de potenciais compradores (ICP)**", f"{perc_icp_final:.2f}%")
            st.metric("Pessoas reais no ICP", fmt_int(potenciais_brutos))

            st.markdown("---")

            st.metric("Leads realistas esperados (com engajamento)", fmt_int(leads_estimados))

            if tamanho_base > 0 and leads_estimados > 0:
                crescimento = (leads_estimados / tamanho_base) * 100
                st.metric("Crescimento potencial da base", f"+{crescimento:.1f}%")

            # Funil visual simples
            st.markdown("**Funil aproximado**")
            dados_funil = pd.DataFrame({
                "Etapa": ["Seguidores totais", "Após filtros ICP", "Leads estimados"],
                "Quantidade": [total_seguidores, round(potenciais_brutos), round(leads_estimados)]
            })
            st.bar_chart(dados_funil.set_index("Etapa"))

            # Interpretação
            if perc_icp_final >= 30:
                st.success(f"Audiência **muito alinhada** ({perc_icp_final:.1f}% dentro do ICP)")
            elif perc_icp_final >= 10:
                st.info(f"Audiência razoavelmente qualificada ({perc_icp_final:.1f}% no ICP)")
            elif perc_icp_final > 0:
                st.warning(f"Apenas {perc_icp_final:.1f}% da base está no ICP — pode ser desafiador")
            else:
                st.info("Ajuste os filtros de ICP para ver o resultado.")

        else:
            st.info("Informe o total de seguidores e pelo menos um filtro de ICP para ver os resultados.")

# ==================== ABA ANALISADOR DE VOD - VERSÃO COM FALA (WHISPER) ====================
with tabs[3]:
    st.title("🎰 Analisador de VOD - Área Link")
    st.write("Cole qualquer URL da Twitch (qualquer streamer):")
    st.caption("⏳ Pode demorar 5–15 minutos na primeira vez (baixa modelo + transcreve áudio)")

    def analisar_vod(vod_input: str):
        vod_str = str(vod_input).strip()
        if vod_str.isdigit():
            vod_id = vod_str
        else:
            match = re.search(r'twitch\.tv/videos/(\d+)', vod_str)
            vod_id = match.group(1) if match else vod_str

        try:
            import yt_dlp
            from faster_whisper import WhisperModel
            import tempfile, os

            url = f"https://www.twitch.tv/videos/{vod_id}"

            # ==================== PASSO 1: Baixa só o áudio ====================
            with st.spinner("📥 Baixando áudio do VOD..."):
                with yt_dlp.YoutubeDL({
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'bestaudio/best',
                    'outtmpl': '/tmp/vod_audio.%(ext)s'
                }) as ydl:
                    info = ydl.extract_info(url, download=True)
                    audio_path = ydl.prepare_filename(info)

            # ==================== PASSO 2: Transcreve com Whisper (fala real) ====================
            with st.spinner("🎤 Transcrevendo fala do streamer (Whisper)..."):
                model = WhisperModel("small", device="cpu", compute_type="int8")  # small = mais rápido
                segments, _ = model.transcribe(audio_path, beam_size=5, language="pt")
                transcricao = " ".join(segment.text for segment in segments).lower()

            # ==================== PASSO 3: Análise com fala + chapters (fallback) ====================
            jogos_config = {
                "Area Link™ Phoenix Firestorm": r"phoenix firestorm|phoenix.*firestorm|area vegas|pear fiction|slingshot|buck stakes",
                "Area Link™ Bank Boss": r"bank boss|bank.*boss|area vegas|pear fiction",
                "Area Link™ Dragon": r"dragon|area link.*dragon|area vegas",
                "VoltedUP WildSurge": r"voltedup|wild surge|wild.*surge|volted.*up",
                "Wacky Panda Power Combo": r"wacky panda|wacky.*panda|power combo",
                "Squealin Riches 2": r"squealin riches|squealin.*riches",
                "Treasures of Mjolnir": r"treasures of mjolnir|mjolnir",
                "FlyX Cash Turbo": r"flyx|cash turbo|flyx.*cash"
            }

            tempos = {}
            total_area_link = 0

            for nome, padrao in jogos_config.items():
                regex = re.compile(padrao, re.IGNORECASE)
                # Procura na transcrição da fala
                matches_fala = len(regex.findall(transcricao))
                minutos_fala = matches_fala * 5  # estimativa conservadora: 5 min por menção

                tempos[nome] = minutos_fala
                if "Area Link" in nome:
                    total_area_link += minutos_fala

            # Limpa arquivo temporário
            if os.path.exists(audio_path):
                os.remove(audio_path)

            return {
                "vod_id": vod_id,
                "tempos_por_jogo": tempos,
                "total_area_link_minutos": total_area_link,
                "transcricao_resumo": transcricao[:500] + "..." if len(transcricao) > 500 else transcricao
            }

        except Exception as e:
            return {"erro": str(e)}

    vod_input = st.text_input("URL ou ID da VOD", placeholder="https://www.twitch.tv/videos/2717322831")
    
    if st.button("🔍 Analisar VOD com Fala (Whisper)", type="primary"):
        if vod_input:
            with st.spinner("🚀 Iniciando análise completa com áudio..."):
                resultado = analisar_vod(vod_input)
            
            if "erro" in resultado:
                st.error(f"Erro: {resultado['erro']}")
            else:
                st.success("✅ VOD analisada com transcrição de fala!")
                st.subheader("⏱ Tempos por jogo (baseado no que o streamer falou)")
                for jogo, minutos in resultado.get("tempos_por_jogo", {}).items():
                    st.write(f"**{jogo}**: {minutos} minutos")
                st.markdown(f"### Total Família Area Link™: **{resultado.get('total_area_link_minutos', 0)} minutos**")
                
                # Mostra um pedacinho da transcrição (opcional)
                with st.expander("Ver transcrição parcial"):
                    st.write(resultado.get("transcricao_resumo", ""))
        else:
            st.warning("Cole uma URL primeiro!")
