import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "buriti-marketing-analytics"
DATASET    = "buriti_marketing_raw"

_NUMERIC_OVERVIEW = [
    "sessions", "totalUsers", "newUsers", "engagedSessions",
    "engagementRate", "bounceRate", "screenPageViews", "averageSessionDuration",
]
_NUMERIC_UTM = ["sessions", "totalUsers", "engagedSessions", "screenPageViews"]


def _criar_client() -> bigquery.Client:
    if "gcp_service_account" in st.secrets:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        return bigquery.Client(credentials=creds, project=PROJECT_ID)
    return bigquery.Client(project=PROJECT_ID)


def _parse_date(df: pd.DataFrame) -> pd.DataFrame:
    """GA4 retorna datas como YYYYMMDD string → converte para datetime."""
    if "date" in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")
    return df


@st.cache_data(ttl=3600)
def carregar_overview() -> pd.DataFrame:
    client = _criar_client()
    query  = f"""
        SELECT * EXCEPT(rn)
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY property_id, date
                       ORDER BY _loaded_at DESC
                   ) AS rn
            FROM `{PROJECT_ID}.{DATASET}.ga4_overview_raw`
        )
        WHERE rn = 1
        ORDER BY date DESC
    """
    df = client.query(query).to_dataframe()
    df = _parse_date(df)
    for col in _NUMERIC_OVERVIEW:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def carregar_utm() -> pd.DataFrame:
    client = _criar_client()
    query  = f"""
        SELECT * EXCEPT(rn)
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY property_id, date, landingPage,
                                    sessionSource, sessionMedium,
                                    sessionCampaignName, sessionManualAdContent
                       ORDER BY _loaded_at DESC
                   ) AS rn
            FROM `{PROJECT_ID}.{DATASET}.ga4_utm_raw`
        )
        WHERE rn = 1
        ORDER BY date DESC
    """
    df = client.query(query).to_dataframe()
    df = _parse_date(df)
    for col in _NUMERIC_UTM:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
