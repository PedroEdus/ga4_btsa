"""
One-shot: carrega os checkpoints CSV no BigQuery.
Execute após cada extração massiva (overview ou utm).

Uso:
  python etl/backfill_ga4_buriti.py --type overview
  python etl/backfill_ga4_buriti.py --type utm
  python etl/backfill_ga4_buriti.py --type overview --checkpoint-dir ../ga4_checkpoints
  python etl/backfill_ga4_buriti.py --type utm     --checkpoint-dir ../ga4_checkpoints_utm
"""
import argparse
import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT_ID  = "buriti-marketing-analytics"
DATASET_RAW = "buriti_marketing_raw"

CONFIGS = {
    "overview": {
        "table":   f"{PROJECT_ID}.{DATASET_RAW}.ga4_overview_raw",
        "default_dir": r"C:\Users\pedro.moura\Documents\Ext GA4\ga4_checkpoints",
        "cols": [
            "property_id", "property_name", "date",
            "sessions", "totalUsers", "newUsers", "engagedSessions",
            "engagementRate", "bounceRate", "screenPageViews", "averageSessionDuration",
        ],
    },
    "utm": {
        "table":   f"{PROJECT_ID}.{DATASET_RAW}.ga4_utm_raw",
        "default_dir": r"C:\Users\pedro.moura\Documents\Ext GA4\ga4_checkpoints_utm",
        "cols": [
            "property_id", "property_name", "date", "landingPage",
            "sessionSource", "sessionMedium", "sessionCampaignName", "sessionManualAdContent",
            "sessions", "totalUsers", "engagedSessions", "screenPageViews",
        ],
    },
}

CHUNK_SIZE = 50_000


def _load_chunk(df: pd.DataFrame, table: str, bq: bigquery.Client) -> int:
    df = df.copy()
    df["_loaded_at"] = datetime.now(timezone.utc)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", autodetect=True)
    bq.load_table_from_dataframe(df, table, job_config=job_config).result()
    return len(df)


def main(tipo: str, checkpoint_dir: str) -> None:
    cfg   = CONFIGS[tipo]
    table = cfg["table"]
    cols  = cfg["cols"]

    bq = bigquery.Client(project=PROJECT_ID)

    csv_files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".csv")]
    print(f"[{tipo}] {len(csv_files)} arquivos em '{checkpoint_dir}' → {table}\n")

    total = 0
    for i, fname in enumerate(csv_files, 1):
        path = os.path.join(checkpoint_dir, fname)
        try:
            df = pd.read_csv(path, dtype=str)
            if df.empty:
                continue

            existing = [c for c in cols if c in df.columns]
            df = df[existing]

            for start in range(0, len(df), CHUNK_SIZE):
                chunk = df.iloc[start : start + CHUNK_SIZE]
                total += _load_chunk(chunk, table, bq)

            print(f"  [{i}/{len(csv_files)}] {fname} — {len(df)} linhas")
        except Exception as exc:
            print(f"  [ERRO] {fname} — {exc}")

    print(f"\n[OK] {total} linhas carregadas em {table}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--type", choices=["overview", "utm"], required=True,
        help="Tipo de dado a carregar"
    )
    parser.add_argument(
        "--checkpoint-dir", default=None,
        help="Diretório com os CSVs (usa padrão do tipo se omitido)"
    )
    args = parser.parse_args()

    chk_dir = args.checkpoint_dir or CONFIGS[args.type]["default_dir"]
    main(args.type, chk_dir)
