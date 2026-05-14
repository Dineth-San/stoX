"""
build_validation.py — Phase 5 entry point: validate the feature panel.

Reads   : data/features/sl20_feature_panel.parquet
Produces:
  data/features/validation_report.md   — full validation summary
  data/features/data_dictionary.md     — column reference (all 130 cols)
  data/features/feature_stats.parquet  — machine-readable per-column stats

Run from ml/:
    python build_validation.py
"""

import logging
import sys
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config, get_ml_dir
from sl20_ml.validation.schema import build_feature_panel_schema
from sl20_ml.validation.report import run_validation

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors as PanderaSchemaErrors

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "build_validation.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    ml_dir      = get_ml_dir()
    panel_path  = ml_dir / cfg["paths"]["features"]["panel"]
    report_path = ml_dir / cfg["paths"]["features"]["validation"]
    dict_path   = ml_dir / cfg["paths"]["features"]["dictionary"]
    stats_path  = ml_dir / cfg["paths"]["features"]["stats"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 5: Validation")
    logger.info("=" * 60)

    # ── Load feature panel ─────────────────────────────────────────────────────
    logger.info(f"\n[1/4] Loading feature panel from {panel_path} ...")
    if not panel_path.exists():
        logger.error(f"Feature panel not found: {panel_path}")
        logger.error("Run build_features.py first.")
        sys.exit(1)
    panel = pd.read_parquet(panel_path)
    logger.info(f"  Loaded: {len(panel):,} rows × {panel.shape[1]} columns")

    # ── Pandera schema validation ──────────────────────────────────────────────
    logger.info("\n[2/4] Running Pandera schema validation ...")
    sl20 = cfg["tickers"]["sl20"]
    schema = build_feature_panel_schema(sl20)
    schema_errors: list[str] = []
    try:
        schema.validate(panel, lazy=True)
        logger.info("  Schema validation: PASS — no errors")
    except PanderaSchemaErrors as exc:
        error_df = exc.failure_cases
        schema_errors = [
            f"{row['schema_context']} | {row['column']} | {row['check']} | "
            f"failure_case={row['failure_case']}"
            for _, row in error_df.iterrows()
        ]
        logger.warning(f"  Schema validation: {len(schema_errors)} error(s) found")
        for err in schema_errors[:5]:
            logger.warning(f"    {err}")
        if len(schema_errors) > 5:
            logger.warning(f"    ... and {len(schema_errors) - 5} more (see report)")

    # ── Run all checks and build reports ──────────────────────────────────────
    logger.info("\n[3/4] Running checks and building reports ...")
    validation_md, dictionary_md, feature_stats = run_validation(
        panel, cfg, schema_errors
    )

    # ── Save outputs ───────────────────────────────────────────────────────────
    logger.info("\n[4/4] Saving outputs ...")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(validation_md, encoding="utf-8")
    dict_path.write_text(dictionary_md, encoding="utf-8")
    feature_stats.to_parquet(stats_path, engine="pyarrow")

    logger.info(f"  Validation report  : {report_path}")
    logger.info(f"  Data dictionary    : {dict_path}")
    logger.info(f"  Feature stats      : {stats_path}")

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    schema_status = "✓ PASS" if not schema_errors else f"✗ FAIL ({len(schema_errors)} errors)"
    logger.info(f"  Schema validation  : {schema_status}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
