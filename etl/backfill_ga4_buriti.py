"""
One-shot: carrega os checkpoints CSV já existentes no BigQuery.
Execute UMA VEZ após criar as tabelas. Não reprocessa linhas já carregadas.

Uso:
  python etl/backfill_ga4_buriti.py --checkpoint-dir ../ga4_checkpoints
"""
import argparse
import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT_ID     = "buriti-marketing-analytics"
DATASET_RAW    = "buriti_marketing_raw"
TABLE_OVERVIEW = f"{PROJECT_ID}.{DATASET_RAW}.ga4_overview_raw"

EXPECTED_COLS = [
    "property_id", "property_name", "date",
    "sessions", "totalUsers", "newUsers", "engagedSessions",
    "engagementRate", "bounceRate", "screenPageViews", "averageSessionDuration",
]

CHUNK_SIZE = 50_000


def _load_chunk(df: pd.DataFrame, bq: bigquery.Client) -> int:
    df = df.copy()
    df["_loaded_at"] = datetime.now(timezone.utc)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        autodetect=True,
    )
    bq.load_table_from_dataframe(df, TABLE_OVERVIEW, job_config=job_config).result()
    return len(df)


def main(checkpoint_dir: str) -> None:
    bq = bigquery.Client(project=PROJECT_ID)

    csv_files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".csv")]
    print(f"{len(csv_files)} arquivos de checkpoint encontrados em '{checkpoint_dir}'")

    total = 0
    for i, fname in enumerate(csv_files, 1):
        path = os.path.join(checkpoint_dir, fname)
        try:
            df = pd.read_csv(path, dtype=str)
            if df.empty:
                continue

            # Mantém só colunas conhecidas, na ordem certa
            existing = [c for c in EXPECTED_COLS if c in df.columns]
            df = df[existing]

            # Carrega em chunks para evitar timeout no BQ
            for start in range(0, len(df), CHUNK_SIZE):
                chunk = df.iloc[start : start + CHUNK_SIZE]
                total += _load_chunk(chunk, bq)

            print(f"  [{i}/{len(csv_files)}] {fname} — {len(df)} linhas")
        except Exception as exc:
            print(f"  [ERRO] {fname} — {exc}")

    print(f"\n[OK] {total} linhas carregadas em {TABLE_OVERVIEW}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "ga4_checkpoints"),
        help="Diretório com os CSVs de checkpoint",
    )
    args = parser.parse_args()
    main(args.checkpoint_dir)
