"""
eval_checkpoint.py — Post-training evaluation for an existing checkpoint.

Run after train_model.py succeeds so that evaluation metrics get logged to
MLflow and model_config.json is written without re-training.

Usage:
    python eval_checkpoint.py [--ckpt models/tft_v1/best-v1.ckpt]
"""

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

import mlflow
import numpy as np
from pytorch_forecasting import TemporalFusionTransformer as TFT

from sl20_ml.model.dataset import build_tft_datasets, make_dataloaders, prepare_tft_dataframe
from sl20_ml.model.evaluate import compute_metrics
from sl20_ml.utils.config import get_ml_dir, load_config

import pandas as pd

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(ckpt_path: Path):
    cfg       = load_config()
    ml_dir    = get_ml_dir()
    panel_path = ml_dir / cfg["paths"]["features"]["panel"]
    model_cfg  = cfg["model"]
    ckpt_dir   = ml_dir / cfg["model"]["checkpoint_dir"]

    logger.info(f"Loading checkpoint: {ckpt_path}")

    # ── Rebuild datasets (needed for dataloaders) ─────────────────────────────
    logger.info("Loading feature panel ...")
    panel = pd.read_parquet(panel_path)

    logger.info("Preparing TFT dataframe ...")
    df = prepare_tft_dataframe(panel)

    logger.info("Building datasets ...")
    training, validation, test = build_tft_datasets(df, cfg)
    _, val_dl, test_dl = make_dataloaders(training, validation, test, cfg)

    # ── Load checkpoint ───────────────────────────────────────────────────────
    best_model = TFT.load_from_checkpoint(str(ckpt_path))
    logger.info("Checkpoint loaded.")

    # ── Evaluate ──────────────────────────────────────────────────────────────
    logger.info("Evaluating on val set ...")
    val_metrics  = compute_metrics(best_model, val_dl,  split_name="val")

    logger.info("Evaluating on test set ...")
    test_metrics = compute_metrics(best_model, test_dl, split_name="test")

    # ── Log to MLflow ─────────────────────────────────────────────────────────
    mlflow.set_tracking_uri((ml_dir / cfg["mlflow"]["tracking_uri"]).as_uri())
    mlflow.set_experiment(cfg["mlflow"]["experiment"])

    with mlflow.start_run(run_name="tft-v1-eval") as run:
        mlflow.log_params({
            "checkpoint": str(ckpt_path),
            "hidden_size": model_cfg["hidden_size"],
            "encoder_length": model_cfg["encoder_length"],
        })
        for split, metrics in [("val", val_metrics), ("test", test_metrics)]:
            for k, v in metrics.items():
                if not np.isnan(v):
                    mlflow.log_metric(f"{split}_{k}", v)
        mlflow.log_artifact(str(ckpt_path))

        # ── Save model_config.json ────────────────────────────────────────────
        # Read architecture from the actual checkpoint (not pipeline.yaml),
        # since the checkpoint may have been trained with different settings.
        actual_hidden_size            = best_model.hparams.get("hidden_size",            model_cfg["hidden_size"])
        actual_attention_head_size    = best_model.hparams.get("attention_head_size",    model_cfg["attention_head_size"])
        actual_hidden_continuous_size = best_model.hparams.get("hidden_continuous_size", model_cfg["hidden_continuous_size"])
        actual_dropout                = best_model.hparams.get("dropout",                model_cfg["dropout"])

        config_out = {
            "model_version":          "tft_v1",
            "checkpoint":             str(ckpt_path),
            "encoder_length":         model_cfg["encoder_length"],
            "prediction_length":      model_cfg["prediction_length"],
            "hidden_size":            actual_hidden_size,
            "attention_head_size":    actual_attention_head_size,
            "dropout":                actual_dropout,
            "hidden_continuous_size": actual_hidden_continuous_size,
            "quantiles":              model_cfg["quantiles"],
            "learning_rate":          model_cfg["learning_rate"],
            "n_tickers":              int(df["ticker"].nunique()),
            "val_metrics":            val_metrics,
            "test_metrics":           test_metrics,
            "mlflow_run_id":          run.info.run_id,
        }
        config_path = ckpt_dir / "model_config.json"
        config_path.write_text(json.dumps(config_out, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(config_path))
        logger.info(f"Model config saved: {config_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"  Val   MAE={val_metrics['mae']:.4f}  "
                f"DA={val_metrics['directional_accuracy']:.2%}  "
                f"QC={val_metrics['quantile_coverage']:.2%}")
    logger.info(f"  Test  MAE={test_metrics['mae']:.4f}  "
                f"DA={test_metrics['directional_accuracy']:.2%}  "
                f"QC={test_metrics['quantile_coverage']:.2%}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default="models/tft_v1/best.ckpt",
                        help="Path to checkpoint (relative to ml/)")
    args = parser.parse_args()

    ckpt = ML_DIR / args.ckpt
    if not ckpt.exists():
        print(f"Checkpoint not found: {ckpt}")
        sys.exit(1)

    main(ckpt)
