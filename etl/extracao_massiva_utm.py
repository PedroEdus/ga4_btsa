"""
Extração histórica de UTM para todas as properties GA4.
Salva um CSV de checkpoint por property em ga4_checkpoints_utm/.
Execute localmente — pode levar horas dependendo do volume.

Uso:
  python etl/extracao_massiva_utm.py
  python etl/extracao_massiva_utm.py --start 2025-01-01 --end 2025-12-31
"""
import argparse
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from dotenv import load_dotenv
from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest,
)
from google.auth.transport.requests import Request

load_dotenv()

_SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH      = os.getenv("GA4_TOKEN_PATH", os.path.join(_SCRIPT_DIR, "..", "..", "token.pkl"))
CHECKPOINT_DIR  = os.getenv("UTM_CHECKPOINT_DIR", os.path.join(_SCRIPT_DIR, "..", "..", "ga4_checkpoints_utm"))
MAX_WORKERS     = 3   # UTM retorna muito mais linhas — workers menores evitam 429

UTM_DIMENSIONS = [
    "date", "landingPage",
    "sessionSource", "sessionMedium", "sessionCampaign", "sessionManualAdContent",
]
UTM_METRICS = ["sessions", "totalUsers", "engagedSessions", "screenPageViews"]


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


# ── Checkpoint ────────────────────────────────────────────────────────────────

def _checkpoint_path(pid: str) -> str:
    return os.path.join(CHECKPOINT_DIR, f"{pid}.csv")


def _load_done_dates(pid: str) -> set:
    path = _checkpoint_path(pid)
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str, usecols=["date"])
        return set(df["date"].unique())
    return set()


def _save_checkpoint(pid: str, df_new: pd.DataFrame) -> None:
    path = _checkpoint_path(pid)
    if os.path.exists(path):
        df_old = pd.read_csv(path, dtype=str)
        df_all = pd.concat([df_old, df_new.astype(str)], ignore_index=True)
        # Deduplica por todas as dimensões UTM
        dedup_cols = ["property_id", "date", "landingPage",
                      "sessionSource", "sessionMedium",
                      "sessionCampaign", "sessionManualAdContent"]
        dedup_cols = [c for c in dedup_cols if c in df_all.columns]
        df_all = df_all.drop_duplicates(subset=dedup_cols, keep="last")
    else:
        df_all = df_new.astype(str)
    df_all.to_csv(path, index=False, encoding="utf-8")


# ── Extração ──────────────────────────────────────────────────────────────────

def _run_report_paged(client, pid: str, target_date: str, retries: int = 5) -> pd.DataFrame:
    all_rows, offset, limit, headers = [], 0, 10_000, []

    while True:
        req = RunReportRequest(
            property=f"properties/{pid}",
            date_ranges=[DateRange(start_date=target_date, end_date=target_date)],
            dimensions=[Dimension(name=d) for d in UTM_DIMENSIONS],
            metrics=[Metric(name=m) for m in UTM_METRICS],
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
                    wait = 15 * (attempt + 1)
                    print(f"    [retry {attempt+1}] {pid} {target_date} — aguardando {wait}s...")
                    time.sleep(wait)
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


def _extract_property(pid: str, name: str, creds, all_days: list) -> int:
    # Renova token se necessário (thread-safe para leitura, suficiente aqui)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    client   = BetaAnalyticsDataClient(credentials=creds)
    done     = _load_done_dates(pid)
    pending  = [d for d in all_days if d not in done]

    if not pending:
        return 0

    saved = 0
    for day in pending:
        try:
            df = _run_report_paged(client, pid, day)
            if not df.empty:
                df.insert(0, "property_id", pid)
                df.insert(1, "property_name", name)
                _save_checkpoint(pid, df)
                saved += len(df)
        except Exception as exc:
            print(f"  [{pid}] ERRO {day} — {exc}")
        time.sleep(0.15)

    return saved


# ── Main ──────────────────────────────────────────────────────────────────────

def main(start_date: str, end_date: str) -> None:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    creds = _load_creds()
    property_names = _get_property_names(creds)
    all_days = pd.date_range(start_date, end_date).strftime("%Y-%m-%d").tolist()

    print(f"{len(property_names)} properties | {len(all_days)} dias ({start_date} → {end_date})")
    print(f"Checkpoints em: {os.path.abspath(CHECKPOINT_DIR)}\n")

    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_extract_property, pid, name, creds, all_days): pid
            for pid, name in property_names.items()
        }
        for future in as_completed(futures):
            pid = futures[future]
            try:
                rows = future.result()
                completed += 1
                status = f"{rows} linhas novas" if rows else "já completo"
                print(f"[{completed}/{len(futures)}] {pid} — {status}")
            except Exception as exc:
                print(f"[ERRO FATAL] {pid} — {exc}")

    print(f"\nFinalizado. Checkpoints em '{CHECKPOINT_DIR}'.")
    print("Próximo passo: python etl/backfill_ga4_buriti.py --type utm")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end",   default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    main(args.start, args.end)
