import base64
import os

import pandas as pd
import plotly.express as px
import streamlit as st

_ASSETS     = os.path.join(os.path.dirname(__file__), "assets")
LOGO_CLARA  = os.path.join(_ASSETS, "logo_preta.png")
LOGO_ESCURA = os.path.join(_ASSETS, "logo_branca.png")

# ── Classificação de canal ────────────────────────────────────────────────────

CANAL_COLORS = {
    "Orgânico":   "#008140",
    "Pago":       "#004d26",
    "Direto":     "#888888",
    "Social":     "#33aa77",
    "Referência": "#00b359",
    "Outros":     "#444444",
}

_PAID_MEDIUMS   = {"cpc","cpm","paid","lead_ad","native_ad","link_ad",
                   "banner_300x250","reconhecimento","formulario","story","lamina"}
_SOCIAL_MEDIUMS = {"whatsapp","instagram_buriti","social","instagram"}
_SOCIAL_SOURCES = {"linktree","l.wl.co","facebook.com","instagram.com"}


def classificar_canal(medium: str, source: str) -> str:
    m = str(medium).lower().strip()
    s = str(source).lower().strip()
    if m == "organic":
        return "Orgânico"
    if s == "(direct)" and m in {"(none)", "", "(not set)"}:
        return "Direto"
    if m in _PAID_MEDIUMS:
        return "Pago"
    if m in _SOCIAL_MEDIUMS or s in _SOCIAL_SOURCES:
        return "Social"
    if m == "referral":
        return "Referência"
    return "Outros"


# ── CSS compartilhado (design system meta_ads) ────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
.pub-card {
    background: #1c1c1c;
    border-radius: 8px;
    padding: 18px 20px 14px;
    margin-bottom: 4px;
}
.pub-card-title {
    font-family: 'Manrope', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 16px;
}
.pub-bar-list { display: flex; flex-direction: column; gap: 9px; }
.pub-bar-row {
    display: grid;
    grid-template-columns: minmax(0, 38%) 1fr 58px;
    align-items: center;
    gap: 8px;
}
.pub-bar-name {
    font-family: 'Manrope', sans-serif;
    font-size: 12px;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
}
.pub-bar-track {
    height: 16px;
    background: #262626;
    border-radius: 3px;
    overflow: hidden;
}
.pub-bar-fill {
    height: 100%;
    border-radius: 3px;
}
.pub-bar-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: rgba(255,255,255,0.72);
    text-align: right;
    font-variant-numeric: tabular-nums;
}
/* ── Tabela de resumo ── */
.rs-table { width:100%; border-collapse:collapse; font-family:'Manrope',sans-serif; }
.rs-th {
    padding: 9px 14px;
    font-size: 11px;
    font-weight: 500;
    color: rgba(255,255,255,0.45);
    border-bottom: 1px solid #2a2a2a;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.rs-th.num { text-align: right; }
.rs-td {
    padding: 9px 14px;
    font-size: 13px;
    color: #ffffff;
    border-bottom: 1px solid #1f1f1f;
}
.rs-td-name {
    padding: 9px 14px;
    font-size: 13px;
    color: #ffffff;
    border-bottom: 1px solid #1f1f1f;
    max-width: 320px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.rs-td.num {
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: rgba(255,255,255,0.85);
    font-variant-numeric: tabular-nums;
}
.rs-td.pct {
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: rgba(255,255,255,0.72);
}
tr.rs-total .rs-td {
    font-weight: 700;
    border-top: 1px solid #3a3a3a;
    border-bottom: none;
    color: #ffffff;
}
tr.rs-total .rs-td.num { color: #ffffff; }
tr:last-child .rs-td { border-bottom: none; }
</style>
"""


def _html(content: str) -> None:
    if hasattr(st, "html"):
        st.html(_CSS + content)
    else:
        st.markdown(_CSS + content, unsafe_allow_html=True)


def _tema() -> str:
    return "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"


def _br(valor, decimais: int = 0, prefixo: str = "") -> str:
    fmt = f"{float(valor):,.{decimais}f}"
    fmt = fmt.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{prefixo}{fmt}"


# ── Logo ──────────────────────────────────────────────────────────────────────

def exibir_logo() -> None:
    existe_clara  = os.path.exists(LOGO_CLARA)
    existe_escura = os.path.exists(LOGO_ESCURA)
    if not existe_clara and not existe_escura:
        return
    caminho_claro  = LOGO_CLARA  if existe_clara  else LOGO_ESCURA
    caminho_escuro = LOGO_ESCURA if existe_escura else LOGO_CLARA
    def b64(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    st.markdown(f"""
        <style>
            .logo-container{{display:flex;justify-content:flex-start;margin-bottom:0.75rem;}}
            .logo-container img{{width:min(220px,55vw);height:auto;}}
            .logo-dark{{display:none;}}
            @media(prefers-color-scheme:dark){{.logo-light{{display:none;}}.logo-dark{{display:block;}}}}
        </style>
        <div class="logo-container">
            <img class="logo-light" src="data:image/png;base64,{b64(caminho_claro)}">
            <img class="logo-dark"  src="data:image/png;base64,{b64(caminho_escuro)}">
        </div>""", unsafe_allow_html=True)


# ── KPIs ──────────────────────────────────────────────────────────────────────

def kpis(metricas: dict) -> None:
    cols = st.columns(len(metricas))
    for col, (label, valor) in zip(cols, metricas.items()):
        col.metric(label, valor)


# ── Gráfico de barras mensais (plotly) ───────────────────────────────────────

def grafico_barras_mensais(
    df: pd.DataFrame,
    x: str,
    y: str,
    titulo: str,
    color: str | None = None,
    color_map: dict | None = None,
) -> None:
    df = df.copy()
    # Converte coluna datetime → string "Mmm/AAAA" ordenada (evita eixo duplicado)
    if pd.api.types.is_datetime64_any_dtype(df[x]):
        df = df.sort_values(x)
        df[x] = df[x].dt.strftime("%b/%Y")

    kwargs = dict(x=x, y=y, title=titulo, barmode="stack" if color else "relative")
    if color:
        kwargs["color"] = color
    if color_map:
        kwargs["color_discrete_map"] = color_map
    fig = px.bar(df, **kwargs)

    # Extende eixo Y 20% acima do máximo para os labels não cortarem
    if not color:
        y_max = float(df[y].max()) if not df.empty else 1
        y_range = [0, y_max * 1.22]
    else:
        y_range = None

    fig.update_layout(
        template=_tema(),
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(title=None, type="category"),
        yaxis=dict(title=None, gridcolor="#2a2a2a", range=y_range),
        legend=dict(orientation="h", y=-0.22, title=None),
        bargap=0.28,
        plot_bgcolor="#1c1c1c",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope, sans-serif", color="#ffffff"),
        title=dict(font=dict(family="Manrope, sans-serif", size=15, color="#ffffff"), x=0, xanchor="left", pad=dict(l=4)),
    )
    if not color:
        # Formata labels em padrão BR (1.234.567)
        text_br = [_br(v) for v in df[y]]
        fig.update_traces(
            marker_color="#008140",
            text=text_br,
            texttemplate="%{text}",
            textposition="outside",
            textfont=dict(size=11, color="rgba(255,255,255,0.75)"),
            cliponaxis=False,
        )
    st.plotly_chart(fig, use_container_width=True)


# ── Barra horizontal em pub-card ─────────────────────────────────────────────

def grafico_barras_h_card(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    titulo: str,
    top_n: int = 15,
    color: str = "#008140",
) -> None:
    df_top = df.nlargest(top_n, x_col).copy()
    max_val = float(df_top[x_col].max()) or 1

    rows_html = ""
    for _, row in df_top.sort_values(x_col, ascending=False).iterrows():
        val      = float(row[x_col])
        name     = str(row[y_col])
        bar_w    = val / max_val * 100
        name_tr  = (name[:38] + "…") if len(name) > 38 else name
        val_str  = _br(val)
        rows_html += (
            f'<div class="pub-bar-row">'
            f'<div class="pub-bar-name" title="{name}">{name_tr}</div>'
            f'<div class="pub-bar-track">'
            f'<div class="pub-bar-fill" style="width:{bar_w:.2f}%;background:{color};"></div>'
            f'</div>'
            f'<div class="pub-bar-value">{val_str}</div>'
            f'</div>'
        )

    _html(f"""
        <div class="pub-card">
            <div class="pub-card-title">{titulo}</div>
            <div class="pub-bar-list">{rows_html}</div>
        </div>
    """)


# ── Rosca (plotly) ────────────────────────────────────────────────────────────

def grafico_rosca(
    df: pd.DataFrame,
    names: str,
    values: str,
    titulo: str,
    color_map: dict | None = None,
) -> None:
    kwargs = dict(names=names, values=values, title=titulo, hole=0.5)
    if color_map:
        kwargs["color"] = names
        kwargs["color_discrete_map"] = color_map
    fig = px.pie(df, **kwargs)
    fig.update_traces(textinfo="label+percent", textfont_size=11)
    fig.update_layout(
        template=_tema(),
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", y=-0.2, title=None),
        font=dict(family="Manrope, sans-serif", color="#ffffff"),
        title=dict(font=dict(family="Manrope, sans-serif", size=15, color="#ffffff"), x=0, xanchor="left", pad=dict(l=4)),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tabela de resumo agregada ─────────────────────────────────────────────────

def tabela_resumo(
    df: pd.DataFrame,
    titulo: str,
    col_nome: str,
    metricas: list,
    col_nome_label: str | None = None,
) -> None:
    """
    Tabela de resumo estilizada com linha de TOTAL.

    metricas: lista de dicts com chaves:
        col     → nome da coluna no df
        label   → texto do cabeçalho
        fmt     → função de formatação (str)
        agg     → "sum" | "mean" | None (não aparece no total)
    """
    import numpy as np

    df_s = df.sort_values(metricas[0]["col"], ascending=False)

    def _th(label, num=True):
        cls = "rs-th num" if num else "rs-th"
        return f'<th class="{cls}">{label}</th>'

    def _td(val, cls="num"):
        return f'<td class="rs-td {cls}">{val}</td>'

    # Cabeçalho
    _nome_hdr = col_nome_label if col_nome_label is not None else col_nome
    headers = _th(_nome_hdr, num=False) + "".join(_th(m["label"]) for m in metricas)

    # Linhas de dados
    rows_html = ""
    for _, row in df_s.iterrows():
        cells = _td(str(row[col_nome]), cls="rs-td-name") + "".join(
            _td(m["fmt"](row[m["col"]]), cls=m.get("cls", "num"))
            for m in metricas
        )
        rows_html += f"<tr>{cells}</tr>"

    # Linha de total
    total_cells = _td("<strong>TOTAL</strong>", cls="rs-td-name")
    for m in metricas:
        agg = m.get("agg")
        if agg == "sum":
            val = df_s[m["col"]].sum()
        elif agg == "mean":
            val = df_s[m["col"]].mean()
        else:
            val = None
        total_cells += _td(m["fmt"](val) if val is not None else "—", cls=m.get("cls", "num"))
    rows_html += f'<tr class="rs-total">{total_cells}</tr>'

    _html(f"""
        <div class="pub-card">
            <div class="pub-card-title">{titulo}</div>
            <div style="overflow-x:auto">
                <table class="rs-table">
                    <thead><tr>{headers}</tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>
    """)


# ── Tabela simples ────────────────────────────────────────────────────────────

def tabela(df: pd.DataFrame) -> None:
    st.dataframe(df, hide_index=True, use_container_width=True)
