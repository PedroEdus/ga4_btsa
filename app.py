import pandas as pd
import streamlit as st

from components import (
    CANAL_COLORS,
    classificar_canal,
    exibir_logo,
    grafico_barras_h_card,
    grafico_barras_mensais,
    grafico_rosca,
    kpis,
    tabela,
)
from data import carregar_overview, carregar_utm
from style import aplicar_tema

st.set_page_config(
    page_title="GA4 Buriti — Analytics",
    page_icon="📊",
    layout="wide",
)

aplicar_tema()
exibir_logo()
st.title("Google Analytics 4 — Buriti")

# ── Carregar dados ────────────────────────────────────────────────────────────

with st.spinner("Carregando dados..."):
    df_ov  = carregar_overview()
    df_utm = carregar_utm()

if df_ov.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# ── Separar institucionais ────────────────────────────────────────────────────
# Contas do site institucional — não comparar com empreendimentos

_INST_KEYWORDS = ["institucional", "btsa | site"]

def _is_inst(name: str) -> bool:
    n = str(name).lower()
    short = n.split("—")[-1].strip()
    return any(k in n for k in _INST_KEYWORDS) or short == "buriti empreendimentos"

def _nome_curto(full: str) -> str:
    return full.split("—")[-1].strip() if "—" in str(full) else str(full)

mask_ov  = df_ov["property_name"].apply(_is_inst)
mask_utm = df_utm["property_name"].apply(_is_inst) if not df_utm.empty else pd.Series(dtype=bool)

df_ov_inst  = df_ov[mask_ov].copy()
df_ov_emp   = df_ov[~mask_ov].copy()
df_utm_inst = df_utm[mask_utm].copy()  if not df_utm.empty else pd.DataFrame()
df_utm_emp  = df_utm[~mask_utm].copy() if not df_utm.empty else pd.DataFrame()

# ── Classificar canais UTM ────────────────────────────────────────────────────

def _enriquecer_utm(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["canal"] = df.apply(
        lambda r: classificar_canal(
            r.get("sessionMedium", ""), r.get("sessionSource", "")
        ), axis=1
    )
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df

df_utm_emp  = _enriquecer_utm(df_utm_emp)
df_utm_inst = _enriquecer_utm(df_utm_inst)

# ── Sidebar — filtros (apenas empreendimentos) ────────────────────────────────

st.sidebar.header("Filtros")

nomes        = sorted(df_ov_emp["property_name"].dropna().unique())
nomes_curtos = {n: _nome_curto(n) for n in nomes}
opcoes_emp   = [nomes_curtos[n] for n in nomes]
sel_nomes    = st.sidebar.multiselect("Empreendimento", opcoes_emp, placeholder="Todos")

min_date = df_ov_emp["date"].min()
max_date = df_ov_emp["date"].max()
date_range = st.sidebar.date_input(
    "Período",
    value=(max_date - pd.Timedelta(days=90), max_date),
    min_value=min_date,
    max_value=max_date,
)
dt_ini, dt_fim = (
    (pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
    if len(date_range) == 2
    else (pd.Timestamp(date_range[0]), pd.Timestamp(date_range[0]))
)

# ── Aplicar filtros ───────────────────────────────────────────────────────────

ov = df_ov_emp[(df_ov_emp["date"] >= dt_ini) & (df_ov_emp["date"] <= dt_fim)].copy()
if sel_nomes:
    full_names = [k for k, v in nomes_curtos.items() if v in sel_nomes]
    ov = ov[ov["property_name"].isin(full_names)]
else:
    full_names = []

utm = (
    df_utm_emp[(df_utm_emp["date"] >= dt_ini) & (df_utm_emp["date"] <= dt_fim)].copy()
    if not df_utm_emp.empty else pd.DataFrame()
)
if full_names and not utm.empty:
    utm = utm[utm["property_name"].isin(full_names)]

_RUIDO = {"(not set)", "(none)", "(data not available)", "data not available",
          "not set", "", "nan", "(not provided)"}

def _limpo(v: str) -> bool:
    return str(v).strip().lower() not in _RUIDO

def _sr(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Remove linhas com valor de ruído na coluna especificada."""
    return df[df[col].apply(_limpo)]

# ── Abas ──────────────────────────────────────────────────────────────────────

aba_inst, aba_ov, aba_utm, aba_lp, aba_tab = st.tabs([
    "🏛️ Sites Institucionais",
    "🏢 Empreendimentos",
    "🔗 UTM — Canais",
    "🏠 Landing Pages",
    "📋 Tabela",
])


# ════════════════════════════════════════════════════════════════════════════
# ABA 1 — Overview (empreendimentos)
# ════════════════════════════════════════════════════════════════════════════
with aba_ov:
    if ov.empty:
        st.info("Nenhum dado no período selecionado.")
    else:
        kpis({
            "Sessões":           f"{int(ov['sessions'].sum()):,.0f}",
            "Usuários":          f"{int(ov['totalUsers'].sum()):,.0f}",
            "Taxa de Rejeição":  f"{ov['bounceRate'].mean():.1%}",
            "Taxa de Engaj.":    f"{ov['engagementRate'].mean():.1%}",
            "Duração Média":     f"{ov['averageSessionDuration'].mean():.0f}s",
        })
        st.divider()

        ov_m = ov.copy()
        ov_m["month"] = ov_m["date"].dt.to_period("M").dt.to_timestamp()

        col1, col2 = st.columns(2)
        with col1:
            monthly = ov_m.groupby("month", as_index=False)["sessions"].sum()
            grafico_barras_mensais(monthly, "month", "sessions", "Sessões por mês")
        with col2:
            top_emp = (
                ov.groupby("property_name", as_index=False)["sessions"].sum()
                .assign(nome=lambda d: d["property_name"].map(_nome_curto))
            )
            grafico_barras_h_card(top_emp, "sessions", "nome", "Top Empreendimentos — Sessões")

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            monthly_u = ov_m.groupby("month", as_index=False)["totalUsers"].sum()
            grafico_barras_mensais(monthly_u, "month", "totalUsers", "Usuários por mês")
        with col4:
            monthly_pv = ov_m.groupby("month", as_index=False)["screenPageViews"].sum()
            grafico_barras_mensais(monthly_pv, "month", "screenPageViews", "Pageviews por mês")


# ════════════════════════════════════════════════════════════════════════════
# ABA 2 — UTM: Canais
# ════════════════════════════════════════════════════════════════════════════

with aba_utm:
    if utm.empty:
        st.info("Nenhum dado de UTM no período selecionado.")
    else:
        # ── Filtros ──────────────────────────────────────────────────────────
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            canal_opts = sorted(utm["canal"].dropna().unique().tolist())
            sel_canais = st.multiselect("Canal", canal_opts, placeholder="Todos", key="utm_canal")
        with fc2:
            utm_clean    = utm[utm["sessionSource"].apply(_limpo) & utm["sessionMedium"].apply(_limpo)]
            src_med_vals = sorted(
                (utm_clean["sessionSource"] + " / " + utm_clean["sessionMedium"]).unique().tolist()
            )
            sel_src_meds = st.multiselect("Source / Medium", src_med_vals, placeholder="Todos", key="utm_src_med")
        with fc3:
            camp_opts  = sorted(_sr(utm, "sessionCampaignName")["sessionCampaignName"].dropna().unique().tolist())
            sel_camps  = st.multiselect("Campaign (utm_campaign)", camp_opts, placeholder="Todos", key="utm_camp")
        with fc4:
            cont_opts  = sorted(_sr(utm, "sessionManualAdContent")["sessionManualAdContent"].dropna().unique().tolist())
            sel_conts  = st.multiselect("Content (utm_content)", cont_opts, placeholder="Todos", key="utm_cont")

        utm_f = utm.copy()
        if sel_canais:
            utm_f = utm_f[utm_f["canal"].isin(sel_canais)]
        if sel_src_meds:
            pairs = [v.split(" / ", 1) for v in sel_src_meds]
            mask  = pd.Series(False, index=utm_f.index)
            for s, m in pairs:
                mask |= (utm_f["sessionSource"] == s) & (utm_f["sessionMedium"] == m)
            utm_f = utm_f[mask]
        if sel_camps:
            utm_f = utm_f[utm_f["sessionCampaignName"].isin(sel_camps)]
        if sel_conts:
            utm_f = utm_f[utm_f["sessionManualAdContent"].isin(sel_conts)]

        st.divider()
        canal_df = utm_f.groupby("canal", as_index=False)["sessions"].sum()
        grafico_barras_h_card(canal_df, "sessions", "canal", "Distribuição por Canal")

        st.divider()
        col3, col4 = st.columns(2)
        with col3:
            src = _sr(utm_f, "sessionSource").groupby("sessionSource", as_index=False)["sessions"].sum()
            grafico_barras_h_card(src, "sessions", "sessionSource", "Source (utm_source)")
        with col4:
            med = _sr(utm_f, "sessionMedium").groupby("sessionMedium", as_index=False)["sessions"].sum()
            grafico_barras_h_card(med, "sessions", "sessionMedium", "Medium (utm_medium)")

        st.divider()
        col5, col6 = st.columns(2)
        with col5:
            camp = _sr(utm_f, "sessionCampaignName").groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            grafico_barras_h_card(camp, "sessions", "sessionCampaignName", "Campaign (utm_campaign)")
        with col6:
            cont = _sr(utm_f, "sessionManualAdContent").groupby("sessionManualAdContent", as_index=False)["sessions"].sum()
            grafico_barras_h_card(cont, "sessions", "sessionManualAdContent", "Content (utm_content)")

        st.divider()
        st.subheader("Source × Medium")
        src_med_df = (
            _sr(_sr(utm_f, "sessionSource"), "sessionMedium")
            .groupby(["sessionSource", "sessionMedium"], as_index=False)["sessions"].sum()
            .assign(canal_label=lambda d: d["sessionSource"] + " / " + d["sessionMedium"])
        )
        grafico_barras_h_card(src_med_df, "sessions", "canal_label", "Top combinações source / medium", top_n=20)


# ════════════════════════════════════════════════════════════════════════════
# ABA 3 — Landing Pages
# ════════════════════════════════════════════════════════════════════════════
with aba_lp:
    if utm.empty:
        st.info("Nenhum dado de landing page no período selecionado.")
    else:
        top_lp = (
            utm.groupby("landingPage", as_index=False)["sessions"]
            .sum()
            .sort_values("sessions", ascending=False)
        )
        lps       = ["Todas"] + top_lp["landingPage"].head(50).tolist()
        sel_lp    = st.selectbox("Filtrar landing page", lps)

        if sel_lp == "Todas":
            grafico_barras_h_card(top_lp, "sessions", "landingPage", "Sessões por Landing Page")
        else:
            utm_lp = utm[utm["landingPage"] == sel_lp]
            st.subheader(f"`{sel_lp}`")

            col1, col2 = st.columns(2)
            with col1:
                canal_lp = utm_lp.groupby("canal", as_index=False)["sessions"].sum()
                grafico_barras_h_card(canal_lp, "sessions", "canal", "Canal")
            with col2:
                src_lp = utm_lp.groupby("sessionSource", as_index=False)["sessions"].sum()
                grafico_barras_h_card(src_lp, "sessions", "sessionSource", "Source")

            camp_lp = utm_lp.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
            grafico_barras_h_card(camp_lp, "sessions", "sessionCampaignName", "Campaigns nesta Landing Page")


# ════════════════════════════════════════════════════════════════════════════
# ABA 4 — Sites Institucionais
# ════════════════════════════════════════════════════════════════════════════
with aba_inst:
    ov_inst = df_ov_inst[
        (df_ov_inst["date"] >= dt_ini) & (df_ov_inst["date"] <= dt_fim)
    ].copy()
    utm_inst = (
        df_utm_inst[(df_utm_inst["date"] >= dt_ini) & (df_utm_inst["date"] <= dt_fim)].copy()
        if not df_utm_inst.empty else pd.DataFrame()
    )

    st.caption("BURITI EMPREENDIMENTOS · Buriti Institucional – GA4 · BTSA | Site Institucional")

    if ov_inst.empty:
        st.info("Nenhum dado institucional no período.")
    else:
        kpis({
            "Sessões":          f"{int(ov_inst['sessions'].sum()):,.0f}",
            "Usuários":         f"{int(ov_inst['totalUsers'].sum()):,.0f}",
            "Taxa de Rejeição": f"{ov_inst['bounceRate'].mean():.1%}",
            "Taxa de Engaj.":   f"{ov_inst['engagementRate'].mean():.1%}",
            "Duração Média":    f"{ov_inst['averageSessionDuration'].mean():.0f}s",
        })
        st.divider()

        ov_inst_m = ov_inst.copy()
        ov_inst_m["month"] = ov_inst_m["date"].dt.to_period("M").dt.to_timestamp()
        ov_inst_m["nome"]  = ov_inst_m["property_name"].map(_nome_curto)

        col1, col2 = st.columns(2)
        with col1:
            monthly_inst = ov_inst_m.groupby("month", as_index=False)["sessions"].sum()
            grafico_barras_mensais(monthly_inst, "month", "sessions", "Sessões por mês")
        with col2:
            if not utm_inst.empty:
                canal_inst = utm_inst.groupby("canal", as_index=False)["sessions"].sum()
                grafico_barras_h_card(canal_inst, "sessions", "canal", "Distribuição por Canal")

        if not utm_inst.empty:
            st.divider()
            col3, col4 = st.columns(2)
            with col3:
                src_inst = utm_inst.groupby("sessionSource", as_index=False)["sessions"].sum()
                grafico_barras_h_card(src_inst, "sessions", "sessionSource", "Top Sources")
            with col4:
                camp_inst = utm_inst.groupby("sessionCampaignName", as_index=False)["sessions"].sum()
                grafico_barras_h_card(camp_inst, "sessions", "sessionCampaignName", "Top Campaigns")


# ════════════════════════════════════════════════════════════════════════════
# ABA 5 — Tabela Bruta
# ════════════════════════════════════════════════════════════════════════════
with aba_tab:
    sub = st.radio("Tabela", ["Empreendimentos", "UTM"], horizontal=True)
    df_tab = (
        ov.sort_values("date", ascending=False)
        if sub == "Empreendimentos"
        else (utm.sort_values("date", ascending=False) if not utm.empty else pd.DataFrame())
    )

    st.download_button(
        label="⬇️ Exportar CSV",
        data=df_tab.to_csv(index=False).encode("utf-8"),
        file_name=f"ga4_buriti_{sub.lower()}_{dt_ini.date()}_{dt_fim.date()}.csv",
        mime="text/csv",
    )
    tabela(df_tab)
