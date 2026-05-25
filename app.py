import pandas as pd
import streamlit as st

from components import exibir_logo, grafico_barras_h, grafico_linha, grafico_rosca, kpis, tabela
from data import carregar_overview, carregar_utm

st.set_page_config(
    page_title="GA4 Buriti — Analytics",
    page_icon="📊",
    layout="wide",
)

exibir_logo()
st.title("Google Analytics 4 — Buriti")

# ── Carregar dados ────────────────────────────────────────────────────────────

with st.spinner("Carregando dados..."):
    df_ov  = carregar_overview()
    df_utm = carregar_utm()

if df_ov.empty:
    st.warning("Nenhum dado de overview encontrado.")
    st.stop()

# ── Sidebar: filtros ──────────────────────────────────────────────────────────

st.sidebar.header("Filtros")

# Extrai nome curto do empreendimento (parte após "—")
def _nome_curto(full: str) -> str:
    return full.split("—")[-1].strip() if "—" in str(full) else str(full)

nomes = sorted(df_ov["property_name"].dropna().unique())
nomes_curtos = {n: _nome_curto(n) for n in nomes}
opcoes = ["Todos"] + [nomes_curtos[n] for n in nomes]

sel_nome = st.sidebar.selectbox("Empreendimento", opcoes)

min_date = df_ov["date"].min()
max_date = df_ov["date"].max()
date_range = st.sidebar.date_input(
    "Período",
    value=(max_date - pd.Timedelta(days=30), max_date),
    min_value=min_date,
    max_value=max_date,
)

if len(date_range) == 2:
    dt_ini, dt_fim = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    dt_ini = dt_fim = pd.Timestamp(date_range[0])

# ── Aplicar filtros ───────────────────────────────────────────────────────────

ov = df_ov[(df_ov["date"] >= dt_ini) & (df_ov["date"] <= dt_fim)].copy()
if sel_nome != "Todos":
    full_name = next((k for k, v in nomes_curtos.items() if v == sel_nome), None)
    ov = ov[ov["property_name"] == full_name]

utm = df_utm[(df_utm["date"] >= dt_ini) & (df_utm["date"] <= dt_fim)].copy()
if sel_nome != "Todos" and full_name:
    utm = utm[utm["property_name"] == full_name]

# ── Abas ──────────────────────────────────────────────────────────────────────

aba_ov, aba_utm, aba_lp, aba_tabela = st.tabs([
    "📈 Overview",
    "🔗 UTM — Canais",
    "🏠 Landing Pages",
    "📋 Tabela Bruta",
])


# ════════════════════════════════════════════════════════════════════════════
# ABA 1 — Overview
# ════════════════════════════════════════════════════════════════════════════
with aba_ov:
    if ov.empty:
        st.info("Nenhum dado no período selecionado.")
    else:
        total_sessions = int(ov["sessions"].sum())
        total_users    = int(ov["totalUsers"].sum())
        avg_bounce     = ov["bounceRate"].mean()
        avg_engage     = ov["engagementRate"].mean()
        avg_duration   = ov["averageSessionDuration"].mean()

        kpis({
            "Sessões":            f"{total_sessions:,.0f}",
            "Usuários":           f"{total_users:,.0f}",
            "Taxa de Rejeição":   f"{avg_bounce:.1%}",
            "Taxa de Engaj.":     f"{avg_engage:.1%}",
            "Duração Média (s)":  f"{avg_duration:.0f}s",
        })

        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            # Série temporal: sessões diárias
            ts = ov.groupby("date", as_index=False)["sessions"].sum()
            grafico_linha(ts, x="date", y="sessions", color=None, titulo="Sessões por dia")

        with col2:
            # Top properties por sessões
            top = (
                ov.groupby("property_name", as_index=False)["sessions"]
                .sum()
                .assign(nome=lambda d: d["property_name"].map(_nome_curto))
            )
            grafico_barras_h(top, x="sessions", y="nome", titulo="Top Empreendimentos — Sessões", top_n=15)

        st.divider()
        col3, col4 = st.columns(2)

        with col3:
            ts_users = ov.groupby("date", as_index=False)["totalUsers"].sum()
            grafico_linha(ts_users, x="date", y="totalUsers", color=None, titulo="Usuários por dia")

        with col4:
            ts_pages = ov.groupby("date", as_index=False)["screenPageViews"].sum()
            grafico_linha(ts_pages, x="date", y="screenPageViews", color=None, titulo="Pageviews por dia")


# ════════════════════════════════════════════════════════════════════════════
# ABA 2 — UTM: Canais
# ════════════════════════════════════════════════════════════════════════════
with aba_utm:
    if utm.empty:
        st.info("Nenhum dado de UTM no período selecionado.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            by_source = (
                utm.groupby("sessionSource", as_index=False)["sessions"].sum()
                .rename(columns={"sessionSource": "source"})
            )
            grafico_barras_h(by_source, x="sessions", y="source", titulo="Sessões por Source (utm_source)", top_n=15)

        with col2:
            by_medium = (
                utm.groupby("sessionMedium", as_index=False)["sessions"].sum()
                .rename(columns={"sessionMedium": "medium"})
            )
            grafico_barras_h(by_medium, x="sessions", y="medium", titulo="Sessões por Medium (utm_medium)", top_n=15)

        st.divider()
        col3, col4 = st.columns(2)

        with col3:
            by_campaign = (
                utm.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
                .rename(columns={"sessionCampaignName": "campaign"})
            )
            grafico_barras_h(by_campaign, x="sessions", y="campaign", titulo="Sessões por Campaign (utm_campaign)", top_n=15)

        with col4:
            by_content = (
                utm.groupby("sessionManualAdContent", as_index=False)["sessions"].sum()
                .rename(columns={"sessionManualAdContent": "content"})
            )
            grafico_barras_h(by_content, x="sessions", y="content", titulo="Sessões por Content (utm_content)", top_n=15)

        st.divider()
        st.subheader("Source × Medium (combinado)")
        by_src_med = (
            utm.groupby(["sessionSource", "sessionMedium"], as_index=False)["sessions"]
            .sum()
            .assign(canal=lambda d: d["sessionSource"] + " / " + d["sessionMedium"])
        )
        grafico_barras_h(by_src_med, x="sessions", y="canal", titulo="Top Canais (source / medium)", top_n=20)


# ════════════════════════════════════════════════════════════════════════════
# ABA 3 — Landing Pages
# ════════════════════════════════════════════════════════════════════════════
with aba_lp:
    if utm.empty:
        st.info("Nenhum dado de landing page no período selecionado.")
    else:
        # Top landing pages
        top_lp = (
            utm.groupby("landingPage", as_index=False)["sessions"]
            .sum()
            .sort_values("sessions", ascending=False)
        )

        # Filtro de landing page específica
        lps_disponiveis = ["Todas"] + top_lp["landingPage"].head(50).tolist()
        sel_lp = st.selectbox("Filtrar landing page", lps_disponiveis)

        if sel_lp == "Todas":
            grafico_barras_h(top_lp, x="sessions", y="landingPage", titulo="Sessões por Landing Page", top_n=20)
        else:
            st.subheader(f"UTMs para: `{sel_lp}`")
            utm_lp = utm[utm["landingPage"] == sel_lp]

            col1, col2 = st.columns(2)
            with col1:
                src = utm_lp.groupby("sessionSource", as_index=False)["sessions"].sum()
                grafico_rosca(src, names="sessionSource", values="sessions", titulo="Source")
            with col2:
                med = utm_lp.groupby("sessionMedium", as_index=False)["sessions"].sum()
                grafico_rosca(med, names="sessionMedium", values="sessions", titulo="Medium")

            camp = (
                utm_lp.groupby("sessionCampaignName", as_index=False)["sessions"]
                .sum()
                .assign(
                    totalUsers=utm_lp.groupby("sessionCampaignName")["totalUsers"].sum().values,
                    engagedSessions=utm_lp.groupby("sessionCampaignName")["engagedSessions"].sum().values,
                )
            )
            grafico_barras_h(camp, x="sessions", y="sessionCampaignName", titulo="Sessões por Campaign nesta LP", top_n=15)


# ════════════════════════════════════════════════════════════════════════════
# ABA 4 — Tabela Bruta
# ════════════════════════════════════════════════════════════════════════════
with aba_tabela:
    sub = st.radio("Tabela", ["Overview", "UTM"], horizontal=True)
    if sub == "Overview":
        tabela(ov.sort_values("date", ascending=False))
    else:
        tabela(utm.sort_values("date", ascending=False))
