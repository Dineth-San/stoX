"""
test_model.py — Phase 6 model architecture and data-preparation tests.

These tests verify the model can be built and run a forward pass without
requiring a fully trained checkpoint (they use a tiny synthetic dataset).

Run from ml/:
    pytest tests/test_model.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

ML_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ML_DIR / "src"))

from sl20_ml.utils.config import load_config


def _load_checkpoint_cpu_safe(ckpt_path: str):
    """
    Load a TFT checkpoint with correct device handling.

    Checkpoints trained on Colab CUDA store `_device='cuda:0'` inside each
    torchmetrics Metric object.  When loading on a CPU-only machine, Lightning
    calls model.to(device) which triggers torchmetrics' _apply(), which tries
    to create a dummy tensor on 'cuda:0' and crashes.

    Fix: patch Metric._apply to reset cached device to CPU when CUDA is absent.
    """
    from pytorch_forecasting import TemporalFusionTransformer as TFT
    if not torch.cuda.is_available():
        try:
            from torchmetrics import Metric
            _orig = Metric._apply
            def _safe(self, fn):
                if hasattr(self, "_device") and "cuda" in str(self._device):
                    self._device = torch.device("cpu")
                return _orig(self, fn)
            Metric._apply = _safe
            try:
                return TFT.load_from_checkpoint(ckpt_path, map_location="cpu")
            finally:
                Metric._apply = _orig   # always restore
        except ImportError:
            return TFT.load_from_checkpoint(ckpt_path, map_location="cpu")
    else:
        return TFT.load_from_checkpoint(ckpt_path)

cfg        = load_config()
PANEL_PATH = ML_DIR / cfg["paths"]["features"]["panel"]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def panel():
    if not PANEL_PATH.exists():
        pytest.skip(f"Feature panel not found: {PANEL_PATH}")
    return pd.read_parquet(PANEL_PATH)


@pytest.fixture(scope="module")
def tft_df(panel):
    """Prepared TFT dataframe (expensive — run once per test session)."""
    try:
        from sl20_ml.model.dataset import prepare_tft_dataframe
    except ImportError as e:
        pytest.skip(f"pytorch-forecasting not installed: {e}")
    return prepare_tft_dataframe(panel)


@pytest.fixture(scope="module")
def tft_datasets(tft_df):
    """Build train/val/test TimeSeriesDataSets."""
    try:
        from sl20_ml.model.dataset import build_tft_datasets
    except ImportError as e:
        pytest.skip(f"pytorch-forecasting not installed: {e}")
    return build_tft_datasets(tft_df, cfg)


@pytest.fixture(scope="module")
def tft_model(tft_datasets):
    """Build the untrained TFT model."""
    training, _, _ = tft_datasets
    try:
        from sl20_ml.model.tft_model import build_tft
    except ImportError as e:
        pytest.skip(f"pytorch-forecasting not installed: {e}")
    return build_tft(training, cfg)


# ── Data preparation tests ────────────────────────────────────────────────────

def test_tft_df_has_time_idx(tft_df):
    """Every ticker must have a monotonic time_idx starting at 0."""
    for ticker, grp in tft_df.groupby("ticker"):
        idx = grp["time_idx"].values
        assert idx[0] == 0, f"Ticker {ticker}: time_idx doesn't start at 0"
        assert (np.diff(idx) == 1).all(), f"Ticker {ticker}: time_idx has gaps"


def test_tft_df_no_null_log_target(tft_df):
    """log_target must be finite for all rows (NaN rows were dropped)."""
    bad = (~np.isfinite(tft_df["log_target"])).sum()
    assert bad == 0, f"{bad:,} non-finite log_target values"


def test_tft_df_log_target_plausible(tft_df):
    """log_target (next-day log return) should almost always be in [-1, 1]."""
    extreme = (tft_df["log_target"].abs() > 1.0).sum()
    pct = extreme / len(tft_df)
    assert pct < 0.001, (
        f"Too many extreme log_target values (|log_ret| > 1): "
        f"{extreme:,} rows ({pct:.2%})"
    )


def test_tft_df_cyclic_features(tft_df):
    """Cyclic calendar features must be in [-1, 1]."""
    for col in ["dow_sin", "dow_cos", "month_sin", "month_cos"]:
        assert col in tft_df.columns, f"Missing cyclic feature: {col}"
        assert tft_df[col].between(-1, 1).all(), f"{col} has values outside [-1, 1]"


def test_tft_df_no_nan_in_features(tft_df):
    """After forward-fill, continuous features must have no NaN."""
    from sl20_ml.model.dataset import TIME_VARYING_UNKNOWN_REALS, TIME_VARYING_KNOWN_REALS
    for col in TIME_VARYING_UNKNOWN_REALS + TIME_VARYING_KNOWN_REALS:
        if col not in tft_df.columns:
            continue
        n = tft_df[col].isna().sum()
        assert n == 0, f"Column {col} still has {n:,} NaN after forward-fill"


def test_tft_df_row_count(tft_df):
    """Prepared df should have fewer rows than raw panel (NaN targets dropped)."""
    raw = pd.read_parquet(PANEL_PATH)
    assert len(tft_df) < len(raw), "prepare_tft_dataframe should drop some rows"
    assert len(tft_df) > 0.90 * len(raw), "Too many rows dropped (>10%)"


# ── Dataset tests ─────────────────────────────────────────────────────────────

def test_datasets_created(tft_datasets):
    training, validation, test = tft_datasets
    assert len(training) > 0,   "Training dataset is empty"
    assert len(validation) > 0, "Validation dataset is empty"
    assert len(test) > 0,       "Test dataset is empty"


def test_train_larger_than_val(tft_datasets):
    training, validation, _ = tft_datasets
    assert len(training) > len(validation), "Training should be larger than val"


def test_no_data_leakage_across_splits(tft_df):
    """No training-set date should appear in the test set."""
    train_dates = set(tft_df[tft_df["date"] < pd.Timestamp(cfg["dates"]["val_start"])]["date"])
    test_dates  = set(tft_df[tft_df["date"] >= pd.Timestamp(cfg["dates"]["test_start"])]["date"])
    overlap = train_dates & test_dates
    assert len(overlap) == 0, f"{len(overlap)} dates appear in both train and test sets"


# ── Model construction tests ──────────────────────────────────────────────────

def test_model_builds(tft_model):
    """TFT model should build without errors."""
    assert tft_model is not None


def test_model_has_trainable_params(tft_model):
    """Model must have trainable parameters."""
    n_params = sum(p.numel() for p in tft_model.parameters() if p.requires_grad)
    assert n_params > 0, "TFT has no trainable parameters"


def test_model_forward_pass(tft_datasets, tft_model):
    """Single forward pass should produce quantile predictions of correct shape."""
    training, _, _ = tft_datasets
    dl = training.to_dataloader(train=False, batch_size=4, num_workers=0)
    batch = next(iter(dl))
    x, y = batch

    tft_model.eval()
    with torch.no_grad():
        out = tft_model(x)

    # pytorch-forecasting 1.x returns a named tuple; access via .prediction
    pred = out.prediction
    assert pred is not None, "Model output .prediction is None"
    # Expected: (batch, pred_len=1, n_quantiles=3)
    assert pred.ndim == 3, f"Expected 3D prediction tensor, got shape {pred.shape}"
    assert pred.shape[1] == cfg["model"]["prediction_length"], "Wrong prediction length"
    assert pred.shape[2] == len(cfg["model"]["quantiles"]), "Wrong number of quantiles"


def test_quantiles_ordered():
    """
    P10 <= P50 <= P90 — only verifiable on a trained checkpoint.
    Quantile ordering is a learned property (enforced by QuantileLoss),
    not a structural guarantee of the untrained model.
    """
    ckpt_dir = ML_DIR / cfg["model"]["checkpoint_dir"]
    best     = ckpt_dir / "best.ckpt"
    if not best.exists():
        pytest.skip("Skipping quantile ordering — no trained checkpoint yet")

    from pytorch_forecasting import TemporalFusionTransformer
    import pandas as pd
    from sl20_ml.model.dataset import prepare_tft_dataframe, build_tft_datasets, make_dataloaders

    panel    = pd.read_parquet(ML_DIR / cfg["paths"]["features"]["panel"])
    df       = prepare_tft_dataframe(panel)
    training, validation, _ = build_tft_datasets(df, cfg)
    _, val_dl, _ = make_dataloaders(training, validation, validation, cfg)

    model = _load_checkpoint_cpu_safe(str(best))
    model.eval()

    batch = next(iter(val_dl))
    x, _ = batch
    with torch.no_grad():
        pred = model(x).prediction[:, 0, :]   # (batch, 3)

    p10, p50, p90 = pred[:, 0], pred[:, 1], pred[:, 2]
    assert (p10 <= p50).all(), "P10 > P50 in trained model — quantile cross detected"
    assert (p50 <= p90).all(), "P50 > P90 in trained model — quantile cross detected"


# ── Checkpoint tests ──────────────────────────────────────────────────────────

def test_checkpoint_loadable():
    """If a trained checkpoint exists, verify it loads without error."""
    ckpt_dir = ML_DIR / cfg["model"]["checkpoint_dir"]
    best     = ckpt_dir / "best.ckpt"
    if not best.exists():
        pytest.skip("No checkpoint found — run train_model.py first")

    try:
        model = _load_checkpoint_cpu_safe(str(best))
        assert model is not None
    except Exception as e:
        pytest.fail(f"Checkpoint failed to load: {e}")


def test_model_config_json_exists():
    """model_config.json must be created after training."""
    config_path = ML_DIR / cfg["model"]["checkpoint_dir"] / "model_config.json"
    if not config_path.exists():
        pytest.skip("model_config.json not found — run train_model.py first")

    import json
    config = json.loads(config_path.read_text())
    assert "val_metrics" in config
    assert "test_metrics" in config
    assert config["val_metrics"]["mae"] > 0
