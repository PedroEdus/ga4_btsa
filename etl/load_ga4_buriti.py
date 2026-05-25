"""
ETL diário GA4 — extrai ontem para todas as properties.
Dois relatórios por property:
  1. overview  → ga4_overview_raw   (date + métricas de sessão)
  2. utm       → ga4_utm_raw        (date + landingPage + dimensões UTM + métricas)
Auth: token.pkl (OAuth2) para GA4 API + service account para BigQuery.
"""
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv
from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
)
from google.auth.transport.requests import Request
from google.cloud import bigquery

load_dotenv()

PROJECT_ID    = "buriti-marketing-analytics"
DATASET_RAW   = "buriti_marketing_raw"
DATASET_SILV  = "buriti_marketing_silver"
TABLE_OVERVIEW = f"{PROJECT_ID}.{DATASET_RAW}.ga4_overview_raw"
TABLE_UTM      = f"{PROJECT_ID}.{DATASET_RAW}.ga4_utm_raw"
TABLE_AUDIT    = f"{PROJECT_ID}.{DATASET_SILV}.controle_cargas_ga4_buriti"

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH   = os.getenv("GA4_TOKEN_PATH", os.path.join(_SCRIPT_DIR, "..", "..", "token.pkl"))
MAX_WORKERS  = 5

_OVERVIEW_DIM     = ["date"]
_OVERVIEW_METRICS = [
    "sessions", "totalUsers", "newUsers", "engagedSessions",
    "engagementRate", "bounceRate", "screenPageViews", "averageSessionDuration",
]
_UTM_DIM = [
    "date", "landingPage",
    "sessionSource", "sessionMedium", "sessionCampaignName", "sessionManualAdContent",
]
_UTM_METRICS = ["sessions", "totalUsers", "engagedSessions", "screenPageViews"]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _load_creds():
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def _get_property_names(creds) -> dict:
    admin = AnalyticsAdminServiceClient(credentials=creds)
    mapping = {}
    for account in admin.list_account_summaries():
        acc = account.display_name
        for prop in account.property_summaries:
            pid = prop.property.replace("properties/", "")
            mapping[pid] = f"{acc} — {prop.display_name}"
    return mapping


# ── Extração ──────────────────────────────────────────────────────────────────

def _run_report_paged(
    client, property_id: str, dimensions: list, metrics: list,
    target_date: str, retries: int = 5,
) -> pd.DataFrame:
    all_rows, offset, limit, headers = [], 0, 10_000, []

    while True:
        req = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date=target_date, end_date=target_date)],
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            limit=limit,
            offset=offset,
        )
        for attempt in range(retries):
            try:
                resp = client.run_report(req)
                break
            except Exception as exc:
                err = str(exc)
                if any(c in err for c in ("429", "503", "500")) and attempt < retries - 1:
                    time.sleep(10 * (attempt + 1))
                else:
                    raise

        if offset == 0:
            headers = (
                [h.name for h in resp.dimension_headers]
                + [h.name for h in resp.metric_headers]
            )

        if not resp.rows:
            break

        for r in resp.rows:
            all_rows.append(
                [v.value for v in r.dimension_values]
                + [v.value for v in r.metric_values]
            )

        if len(resp.rows) < limit:
            break
        offset += limit

    return pd.DataFrame(all_rows, columns=headers) if all_rows else pd.DataFrame()


def _extract_property(pid: str, name: str, creds, target_date: str):
    client = BetaAnalyticsDataClient(credentials=creds)

    overview = _run_report_paged(client, pid, _OVERVIEW_DIM, _OVERVIEW_METRICS, target_date)
    if not overview.empty:
        overview.insert(0, "property_id", pid)
        overview.insert(1, "property_name", name)

    utm = _run_report_paged(client, pid, _UTM_DIM, _UTM_METRICS, target_date)
    if not utm.empty:
        utm.insert(0, "property_id", pid)
        utm.insert(1, "property_name", name)

    return overview, utm


# ── BigQuery ──────────────────────────────────────────────────────────────────

def _load_to_bq(df: pd.DataFrame, table: str, bq: bigquery.Client) -> int:
    if df.empty:
        return 0
    df = df.copy()
    df["_loaded_at"] = datetime.now(timezone.utc)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        autodetect=True,
    )
    bq.load_table_from_dataframe(df, table, job_config=job_config).result()
    return len(df)


def _audit(bq: bigquery.Client, rows_ov: int, rows_utm: int, status: str) -> None:
    audit = pd.DataFrame([{
        "fonte":            "ga4_buriti",
        "qtd_overview":     rows_ov,
        "qtd_utm":          rows_utm,
        "carregado_em":     datetime.now(timezone.utc),
        "status":           status,
    }])
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
    bq.load_table_from_dataframe(audit, TABLE_AUDIT, job_config=job_config).result()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    target_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Extraindo GA4 para {target_date} ...")

    creds = _load_creds()
    property_names = _get_property_names(creds)
    print(f"{len(property_names)} properties encontradas.\n")

    bq = bigquery.Client(project=PROJECT_ID)
    all_overview, all_utm = [], []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_extract_property, pid, name, creds, target_date): pid
            for pid, name in property_names.items()
        }
        for i, future in enumerate(as_completed(futures), 1):
            pid = futures[future]
            try:
                ov, utm = future.result()
                if not ov.empty:
                    all_overview.append(ov)
                if not utm.empty:
                    all_utm.append(utm)
                print(f"  [{i}/{len(futures)}] {pid}")
            except Exception as exc:
                print(f"  [ERRO] {pid} — {exc}")

    df_ov  = pd.concat(all_overview, ignore_index=True) if all_overview else pd.DataFrame()
    df_utm = pd.concat(all_utm,      ignore_index=True) if all_utm      else pd.DataFrame()

    try:
        rows_ov  = _load_to_bq(df_ov,  TABLE_OVERVIEW, bq)
        rows_utm = _load_to_bq(df_utm, TABLE_UTM,      bq)
        _audit(bq, rows_ov, rows_utm, "OK")
        print(f"\n[OK] overview={rows_ov} linhas | utm={rows_utm} linhas")
    except Exception as exc:
        _audit(bq, 0, 0, f"ERRO: {exc}")
        raise


if __name__ == "__main__":
    main()
