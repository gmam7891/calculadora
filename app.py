import os
import re
import statistics
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from src.twitch_client import TwitchClient
from src import storage
from src.influencer_metrics import influencer_calcs, fee_max_by_roi, fee_max_by_cpa
from src.projections import project_twitch


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
    if mh: h = int(mh.group(1))
    if mm: m = int(mm.group(1))
    if ms: sec = int(ms.group(1))
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

def load_streamers_file(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                out.append(s.lower())
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


load_dotenv()

st.set_page_config(page_title="Valuation Influenciadores + Twitch", layout="wide")
st.title("Valuation Influenciadores + Twitch")

client_id = os.getenv("TWITCH_CLIENT_ID", "")
client_secret = os.getenv("TWITCH_CLIENT_SECRET", "")
db_path = os.getenv("APP_DB_PATH", "./data/app.db")

conn = storage.connect(db_path)
storage.init_db(conn)

tabs = st.tabs(["Influenciador", "Twitch (Avg/Peak + Projeções)", "Como rodar"])

# -------------------
# Influenciador
# -------------------
with tabs[0]:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("Inputs (manual)")
        fee = st.number_input("Fee / investimento (R$)", min_value=0.0, value=50000.0, step=1000.0)

        st.markdown("### Instagram Reels")
        reels_qty = st.number_input("Qtd Reels", min_value=0, value=2, step=1)
        reels_avg_views = st.number_input("Views médias por Reel", min_value=0.0, value=150000.0, step=1000.0)
        reels_ctr = st.number_input("CTR Reels (0,003 = 0,3%)", min_value=0.0, value=0.003, step=0.001, format="%.6f")

        st.markdown("### Instagram Stories")
        stories_qty = st.number_input("Qtd Stories (frames/combos)", min_value=0, value=6, step=1)
        stories_avg_views = st.number_input("Views médias por Story", min_value=0.0, value=40000.0, step=1000.0)
        stories_ctr = st.number_input("CTR Stories (0,01 = 1%)", min_value=0.0, value=0.01, step=0.001, format="%.6f")

        st.markdown("### TikTok")
        tiktok_qty = st.number_input("Qtd TikToks", min_value=0, value=1, step=1)
        tiktok_avg_views = st.number_input("Views médias por TikTok", min_value=0.0, value=200000.0, step=1000.0)
        tiktok_ctr = st.number_input("CTR TikTok", min_value=0.0, value=0.002, step=0.001, format="%.6f")

        st.markdown("### Funil (FTD)")
        manual_clicks_toggle = st.checkbox("Tenho cliques reais (sobrescrever CTR)", value=False)
        manual_clicks = None
        if manual_clicks_toggle:
            manual_clicks = st.number_input("Cliques reais (total)", min_value=0.0, value=1200.0, step=50.0)

        manual_ftd_toggle = st.checkbox("Tenho FTD real (sobrescrever projeção)", value=False)
        manual_ftd = None
        if manual_ftd_toggle:
            manual_ftd = st.number_input("FTD real (total)", min_value=0.0, value=0.0, step=1.0)

        cvr_ftd = st.number_input("CVR para FTD (0,02 = 2%)", min_value=0.0, value=0.02, step=0.005, format="%.6f")
        value_per_ftd = st.number_input("Valor por FTD (R$) — LTV/NGR médio", min_value=0.0, value=600.0, step=50.0)

        st.markdown("### Metas")
        target_roi = st.number_input("ROI alvo (0,30 = +30%)", value=0.30, step=0.05, format="%.2f")
        target_cpa = st.number_input("CPA (FTD) alvo (R$)", value=350.0, step=25.0)

    with c2:
        st.subheader("Resultados")
        res = influencer_calcs(
            fee=fee,
            reels_qty=reels_qty, reels_avg_views=reels_avg_views, reels_ctr=reels_ctr,
            stories_qty=stories_qty, stories_avg_views=stories_avg_views, stories_ctr=stories_ctr,
            tiktok_qty=tiktok_qty, tiktok_avg_views=tiktok_avg_views, tiktok_ctr=tiktok_ctr,
            manual_clicks=manual_clicks,
            manual_ftd=manual_ftd,
            cvr_ftd=cvr_ftd,
            value_per_ftd=value_per_ftd,
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Views totais (proxy impressões)", fmt_int(res["total_views"]))
        k2.metric("Cliques (estimado/real)", fmt_int(res["clicks"]))
        k3.metric("FTD (proj./real)", fmt_float(res["ftd"], 1))
        k4.metric("Receita (FTD * valor)", fmt_money(res["revenue"]))

        k5, k6, k7, k8, k9 = st.columns(5)
        k5.metric("CPM", fmt_money(res["cpm"]))
        k6.metric("CPC", fmt_money(res["cpc"]))
        k7.metric("CPA (FTD)", fmt_money(res["cpa_ftd"]))
        k8.metric("ROAS", fmt_float(res["roas"], 2))
        k9.metric("ROI", fmt_float(res["roi"], 2))

        st.markdown("### Fee máximo para bater metas")
        max_fee_roi = fee_max_by_roi(res["revenue"], target_roi) if res["revenue"] is not None else None
        max_fee_cpa = fee_max_by_cpa(target_cpa, res["ftd"]) if res["ftd"] is not None else None

        a, b = st.columns(2)
        a.metric("Fee máx p/ ROI alvo", fmt_money(max_fee_roi))
        b.metric("Fee máx p/ CPA alvo", fmt_money(max_fee_cpa))

        verdicts = []
        if res["roi"] is not None:
            verdicts.append(res["roi"] >= target_roi)
        if res["cpa_ftd"] is not None:
            verdicts.append(res["cpa_ftd"] <= target_cpa)

        if verdicts and all(verdicts):
            st.success("✅ Cenário saudável (bate ROI e CPA).")
        elif verdicts and any(verdicts):
            st.warning("⚠️ Cenário misto (bate uma meta e falha outra).")
        else:
            st.error("❌ Cenário ruim (não bate metas) — renegociar fee/entregas ou revisar premissas.")

# -------------------
# Twitch
# -------------------
with tabs[1]:
    st.subheader("Twitch — Avg Viewers / Peak (30d) + Projeções")
    # ... (todo o código que você já tem até o final das projeções fica igual)

    # ==================== NOVA SEÇÃO: PROJEÇÕES FINANCEIRAS ====================
    st.markdown("---")
    st.subheader("💰 Projeções Financeiras (FTD + Receita + Lucro/Prejuízo)")

    # Inputs específicos pro Twitch (pode deixar fixo ou deixar editável)
    twitch_ctr = st.number_input("CTR Twitch (chat + overlay)", min_value=0.0, value=0.0025, step=0.0005, format="%.6f", help="Valor típico no nicho slots: 0,001 ~ 0,005")
    
    # Reusa os valores que você já tem na aba Influenciador (melhor UX)
    use_same_cvr = st.checkbox("Usar mesmo CVR e Valor por FTD da aba Influenciador", value=True)
    if use_same_cvr:
        twitch_cvr = cvr_ftd
        twitch_value_per_ftd = value_per_ftd
    else:
        twitch_cvr = st.number_input("CVR Twitch para FTD", min_value=0.0, value=0.015, step=0.001, format="%.6f")
        twitch_value_per_ftd = st.number_input("Valor por FTD (R$)", min_value=0.0, value=600.0, step=50.0)

    # Calcula usando as projeções que você já tem
    proj_unique = proj["projected_unique_views"] or 0
    proj_hours = proj["projected_hours_watched"] or 0

    # Funil Twitch
    twitch_clicks = proj_unique * twitch_ctr
    twitch_ftd = twitch_clicks * twitch_cvr
    twitch_revenue = twitch_ftd * twitch_value_per_ftd
    twitch_roi = ((twitch_revenue - fee) / fee) if fee > 0 else 0
    twitch_cpa = (fee / twitch_ftd) if twitch_ftd > 0 else None
    twitch_roas = (twitch_revenue / fee) if fee > 0 else 0

    # Métricas bonitinhas
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Cliques estimados (Twitch)", fmt_int(twitch_clicks))
    f2.metric("FTD projetado", fmt_float(twitch_ftd, 1))
    f3.metric("Receita projetada", fmt_money(twitch_revenue))
    f4.metric("ROAS", fmt_float(twitch_roas, 2))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("CPA (FTD)", fmt_money(twitch_cpa))
    g2.metric("ROI", fmt_float(twitch_roi, 2))
    g3.metric("Lucro/Prejuízo esperado", fmt_money(twitch_revenue - fee))
    g4.metric("Fee máximo (ROI alvo)", fmt_money(fee_max_by_roi(twitch_revenue, target_roi)))

    # Veredito forte
    if twitch_roi >= target_roi and (twitch_cpa is None or twitch_cpa <= target_cpa):
        st.success("✅ **LUCRATIVO** — Fee vale muito a pena!")
    elif twitch_roi >= 0:
        st.warning("⚠️ Margem positiva, mas não bate suas metas. Negociar fee ou horas.")
    else:
        st.error("❌ **PREJUÍZO** — Não compensa pagar esse fee com o volume atual.")

    st.caption("Obs.: CTR Twitch é conservador. Ajuste conforme histórico real do streamer.")
# -------------------
# Como rodar
# -------------------
with tabs[2]:
    st.subheader("Rodar no VS Code (local)")

    st.markdown(
        '''
### 1) Instalar deps
```bash
python -m venv .venv
source .venv/bin/activate   # mac/linux
pip install -r requirements.txt
```

### 2) Configurar .env
Copie `.env.example` -> `.env` e preencha TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET.

### 3) Rodar coletor (Terminal A)
```bash
python src/collector.py --channels-file streamers.txt --interval 120
```

### 4) Rodar app (Terminal B)
```bash
streamlit run app.py
```
        '''
    )
