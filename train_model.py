"""
train_model.py — Phase 6 entry point: train the TFT model on the feature panel.

Reads   : data/features/sl20_feature_panel.parquet
Produces:
  models/tft_v1/best.ckpt        — best checkpoint (lowest val_loss)
  models/tft_v1/model_config.json — hyperparameters + feature lists
  mlruns/                        — MLflow experiment with all metrics

Run from ml/:
    python train_model.py

The model predicts next-day log return for each of the 20 SL20 tickers,
with P10 / P50 / P90 quantiles.  P50 is the point forecast;
P10–P90 is the 80% prediction interval.
"""

import json
import logging
import sys
import warnings
from pathlib import Path

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR / "src"))

import mlflow
import numpy as np
import pandas as pd
import lightning.pytorch as pl
import torch
from lightning.pytorch.callbacks import (
    EarlyStopping,
    LearningRateMonitor,
    ModelCheckpoint,
)

from sl20_ml.model.dataset import (
    build_tft_datasets,
    make_dataloaders,
    prepare_tft_dataframe,
)
from sl20_ml.model.evaluate import compute_metrics
from sl20_ml.model.tft_model import build_tft
from sl20_ml.utils.config import get_ml_dir, load_config

cfg = load_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler(ML_DIR / "train_model.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Suppress noisy pytorch-forecasting / lightning warnings
warnings.filterwarnings("ignore", ".*does not have many workers.*")
warnings.filterwarnings("ignore", ".*MisconfigurationException.*")


def main():
    ml_dir        = get_ml_dir()
    panel_path    = ml_dir / cfg["paths"]["features"]["panel"]
    ckpt_dir      = ml_dir / cfg["model"]["checkpoint_dir"]
    model_cfg     = cfg["model"]

    logger.info("=" * 60)
    logger.info("stoX — Phase 6: TFT Model Training")
    logger.info("=" * 60)

    # ── 1. Load feature panel ──────────────────────────────────────────────────
    logger.info(f"\n[1/5] Loading feature panel ...")
    if not panel_path.exists():
        logger.error(f"Panel not found: {panel_path}. Run build_features.py first.")
        sys.exit(1)
    panel = pd.read_parquet(panel_path)
    logger.info(f"  Loaded: {len(panel):,} rows × {panel.shape[1]} columns")

    # ── 2. Prepare TFT dataframe ───────────────────────────────────────────────
    logger.info("\n[2/5] Preparing TFT dataframe ...")
    df = prepare_tft_dataframe(panel)

    # ── 3. Build datasets & dataloaders ───────────────────────────────────────
    logger.info("\n[3/5] Building TimeSeriesDataSets ...")
    training, validation, test = build_tft_datasets(df, cfg)
    train_dl, val_dl, test_dl  = make_dataloaders(training, validation, test, cfg)

    # ── 4. Build model ────────────────────────────────────────────────────────
    logger.info("\n[4/5] Building TFT model ...")
    tft = build_tft(training, cfg)

    # ── 5. Train ──────────────────────────────────────────────────────────────
    logger.info("\n[5/5] Training ...")
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=model_cfg["early_stopping_patience"],
            mode="min",
            verbose=True,
        ),
        ModelCheckpoint(
            monitor="val_loss",
            dirpath=str(ckpt_dir),
            filename="best",
            save_top_k=1,
            mode="min",
        ),
        LearningRateMonitor(logging_interval="epoch"),
    ]

    # Detect available accelerator
    if torch.cuda.is_available():
        accelerator = "gpu"
    else:
        accelerator = "cpu"
    logger.info(f"  Accelerator: {accelerator}")

    # Set up MLflow — use file:// URI so Windows absolute paths work correctly
    mlflow.set_tracking_uri((ml_dir / cfg["mlflow"]["tracking_uri"]).as_uri())
    mlflow.set_experiment(cfg["mlflow"]["experiment"])

    with mlflow.start_run(run_name="tft-v1-training") as run:
        # Log hyperparameters
        mlflow.log_params({
            "encoder_length":        model_cfg["encoder_length"],
            "prediction_length":     model_cfg["prediction_length"],
            "hidden_size":           model_cfg["hidden_size"],
            "attention_head_size":   model_cfg["attention_head_size"],
            "dropout":               model_cfg["dropout"],
            "learning_rate":         model_cfg["learning_rate"],
            "max_epochs":            model_cfg["max_epochs"],
            "batch_size":            model_cfg["batch_size"],
            "train_samples":         len(training),
            "val_samples":           len(validation),
            "n_tickers":             df["ticker"].nunique(),
        })

        # Note: mlflow.pytorch.autolog is incompatible with pf 1.x (class mismatch).
        # We log metrics manually after training instead.

        trainer = pl.Trainer(
            max_epochs=model_cfg["max_epochs"],
            accelerator=accelerator,
            devices=1,
            gradient_clip_val=model_cfg["gradient_clip_val"],
            callbacks=callbacks,
            enable_progress_bar=True,
            logger=True,
            log_every_n_steps=10,
        )

        trainer.fit(tft, train_dataloaders=train_dl, val_dataloaders=val_dl)

        best_ckpt_path = callbacks[1].best_model_path
        logger.info(f"\n  Best checkpoint: {best_ckpt_path}")
        logger.info(f"  Best val_loss  : {callbacks[1].best_model_score:.6f}")

        # ── Evaluate on val and test ─────────────────────────────────────────
        logger.info("\n  Evaluating on val set ...")
        from pytorch_forecasting import TemporalFusionTransformer as TFT
        best_model = TFT.load_from_checkpoint(best_ckpt_path)

        val_metrics  = compute_metrics(best_model, val_dl,  split_name="val")
        test_metrics = compute_metrics(best_model, test_dl, split_name="test")

        # Log final metrics to MLflow
        for split, metrics in [("val", val_metrics), ("test", test_metrics)]:
            for k, v in metrics.items():
                if not np.isnan(v):
                    mlflow.log_metric(f"{split}_{k}", v)

        mlflow.log_artifact(best_ckpt_path)

        # ── Save model config JSON ────────────────────────────────────────────
        config_path = ckpt_dir / "model_config.json"
        config_out = {
            "model_version":          "tft_v1",
            "checkpoint":             str(best_ckpt_path),
            "encoder_length":         model_cfg["encoder_length"],
            "prediction_length":      model_cfg["prediction_length"],
            "hidden_size":            model_cfg["hidden_size"],
            "attention_head_size":    model_cfg["attention_head_size"],
            "dropout":                model_cfg["dropout"],
            "hidden_continuous_size": model_cfg["hidden_continuous_size"],
            "quantiles":              model_cfg["quantiles"],
            "learning_rate":          model_cfg["learning_rate"],
            "n_tickers":              int(df["ticker"].nunique()),
            "val_metrics":            val_metrics,
            "test_metrics":           test_metrics,
            "mlflow_run_id":          run.info.run_id,
        }
        config_path.write_text(json.dumps(config_out, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(config_path))
        logger.info(f"  Model config saved: {config_path}")

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Training complete.")
    logger.info(f"  Checkpoint : {best_ckpt_path}")
    logger.info(f"  Val  MAE={val_metrics['mae']:.4f}  "
                f"DA={val_metrics['directional_accuracy']:.2%}  "
                f"QC={val_metrics['quantile_coverage']:.2%}")
    logger.info(f"  Test MAE={test_metrics['mae']:.4f}  "
                f"DA={test_metrics['directional_accuracy']:.2%}  "
                f"QC={test_metrics['quantile_coverage']:.2%}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
