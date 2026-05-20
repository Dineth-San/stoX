# stoX — The ML Model (TFT)

> A plain-English explanation of the AI model we built, what it does, how it works, and what the results mean.

---

## What Problem Are We Solving?

Given a stock's last 60 trading days of data, predict tomorrow's closing price — and be honest about how uncertain that prediction is.

Most stock prediction tools give you a single number ("JKH will close at LKR 185 tomorrow"). That's misleading because it hides uncertainty. Instead, we give three numbers:

- **P10 = LKR 178** — only 10% chance the actual price will be *below* this
- **P50 = LKR 185** — the model's best single guess (equally likely to be above or below)
- **P90 = LKR 193** — only 10% chance the actual price will be *above* this

So the model is saying: "I'm 80% confident the price will land between 178 and 193, with 185 as my best guess." The width of that band tells you how uncertain the model is.

---

## What Model We Use: TFT

**TFT stands for Temporal Fusion Transformer** — a deep learning model designed specifically for time-series forecasting (predicting sequences that change over time).

It was introduced by Google Research in 2019 and became one of the best-performing models for this type of problem. The key things that make it good:

1. **It understands time** — unlike a general AI model, TFT is built from the ground up to understand sequences where order matters (day 1, day 2, day 3...).

2. **It handles many input types** — some features are known in the future (like the day of the week), some are only known up to today (like prices). TFT treats these differently.

3. **It's interpretable** — TFT can tell you *which features it found most useful*, unlike a "black box" model.

4. **It gives uncertainty** — via quantile outputs (P10/P50/P90).

We use TFT through the **pytorch-forecasting** library (v1.7), which provides a battle-tested implementation. Under the hood it runs on **PyTorch**, the same deep learning framework used by Meta, Tesla, and most AI research labs.

---

## How TFT Works (Plain English)

Think of TFT as having three stages: **remember**, **focus**, **predict**.

### Stage 1: Remember (the LSTM encoder/decoder)

An **LSTM** (Long Short-Term Memory) is a type of neural network that reads a sequence one step at a time and maintains a "memory" as it goes. Think of it like reading a book — by the time you're on page 60, you remember the important things from earlier chapters.

The TFT has two LSTMs:
- The **encoder** reads the past 60 days of data and builds a rich summary of what happened
- The **decoder** takes that summary and thinks about the 1 future day being predicted

### Stage 2: Focus (the Attention mechanism)

After the LSTM, TFT adds a **multi-head attention** layer. This is the same idea behind ChatGPT — it lets the model look back and decide *which past days matter most* for making today's prediction.

For example, if JKH had an unusual spike in volume 3 weeks ago, the attention mechanism might learn to "look at" that day more carefully because volume spikes tend to precede price moves.

### Stage 3: Variable selection

Not all 130 features are equally useful. TFT has a built-in "feature selector" (called a Variable Selection Network, or VSN) that learns which features to pay attention to and which to mostly ignore.

This is important because some of our 130 features might be noise. The model learns to downweight them automatically.

### Stage 4: Predict (quantile output)

At the end, TFT produces three numbers: the P10, P50, and P90. These are trained with a special loss function called **Quantile Loss** — the training process is specifically designed so that, over time, approximately 80% of actual prices fall between P10 and P90. The model is penalised differently for over- and under-estimating each quantile.

### Stage 5: Conformal calibration (post-training)

The model's raw P10/P90 outputs target an 80% interval by construction. To get a **calibrated 90% interval** with finite-sample coverage guarantees, we apply **Conformalized Quantile Regression (CQR, Romano-Patterson-Candès 2019)** as a one-line post-processing step:

1. After training, run the model on the validation set.
2. For each sample compute the nonconformity score `s = max(P10 − actual, actual − P90)`.
3. Take the `⌈(n+1)·0.90⌉/n` quantile of those scores → a single scalar `δ`.
4. At inference, widen the band: `calibrated_P10 = P10 − δ`, `calibrated_P90 = P90 + δ`.

This guarantees **exactly 90% coverage on validation** and approximately 90% on test (under exchangeability). `δ` is stored in `model_config.json` and is fully transparent. The model itself is unchanged.

---

## Our Model Architecture (Specific Details)

```
Model: TemporalFusionTransformer (pytorch-forecasting v1.7)
─────────────────────────────────────────────────────────
Hidden size     : 128  (size of internal representations)
Attention heads : 8    (eight "perspectives" when looking back)
Dropout         : 0.2  (20% of neurons randomly disabled during
                         training — prevents overfitting)
Hidden cont. size: 64  (continuous variable embedding size)
─────────────────────────────────────────────────────────
Input (encoder) : last 90 trading days (≈4.5 months) of features
Output          : next 1 day → [P10, P50, P90]
─────────────────────────────────────────────────────────
Target variable : log(next_close / close)  — log return, clipped ±0.25
                  (We predict the *percentage change*, not the raw
                   price. Clipping removes corrupted targets from
                   unadjusted corporate actions.)
─────────────────────────────────────────────────────────
Training config : lr=5e-4  gradient_clip=0.5  batch=128
                  early_stop_patience=30  reduce_lr_patience=10
                  val = 2021 only (2022 crisis excluded from val)
```

> **Training target:** Re-train on Colab T4 GPU using `ml/colab_train.ipynb`. With `hidden_size=128` and `batch_size=128` FP32, the T4 runs at ~80% GPU utilisation. Expected training time: 60–90 min.

### Why log return instead of raw price?

If you train on raw prices, LIOC (which trades at ~LKR 80) and JKH (which trades at ~LKR 180) look completely different to the model. But a 2% daily move is a 2% daily move regardless of the price level.

We predict `log(next_close / close)` — essentially the next-day percentage return in log space. This is:
- Comparable across all 20 tickers (same scale)
- More statistically stable (no exponential trends)
- Easy to convert back: `predicted_price = current_close × exp(predicted_log_return)`

### What the model receives as input

**Per-ticker (past 90 days):**
Prices, returns, volatility, RSI, MACD, Bollinger bands, ATR, OBV, volume ratio, price position, cross-sectional ranks

**Uncertainty / regime features (new in v2):**
- `vol_regime` — ratio of 20-day vol to 252-day baseline; >1.0 means elevated volatility regime
- `daily_range_pct` — intraday high-low spread as % of close; signals price discovery difficulty
- `market_breadth` — fraction of SL20 stocks advancing that day (market-wide signal)

**Known in advance (past AND future):**
Day of week, month, is_month_end, is_quarter_end, trading day of month, time_idx

**Macro context (shared across all tickers):**
USD/LKR, 5-day FX change, policy rate, VIX, oil price, S&P 500, gold, GDP growth, inflation, ASPI, SL20 index, market P/E, foreign net flow (monthly CSE investor flow in Bn LKR)

**Static (doesn't change):**
Ticker identity — the model knows *which stock* it's predicting

---

## How We Trained It

### Data split
```
Train      : 2011–2020   (training windows)
[2022 excluded — Sri Lanka economic crisis, once-per-decade outlier]
Validation : 2021        (windows) — used to monitor training
Test       : 2023–2025   (windows) — final, unseen evaluation
```

Each "window" is: 60 days of history → predict day 61.

### Training run
```
Optimiser    : Adam (adaptive learning rate)
Learning rate: 0.003
Batch size   : 256 samples per gradient step  ← large batch for T4
Max epochs   : 150 (training rounds through all data)
Early stop   : Stop if val_loss doesn't improve for 25 epochs
Hardware     : GPU (NVIDIA T4 via Google Colab)
Precision    : FP16 mixed (tensor cores ≈2× faster, uses less VRAM)
Gradient clip: 0.1  (prevents exploding gradients)
```

**What's an epoch?** One complete pass through all 46,875 training samples. Each epoch the model adjusts its weights slightly to make better predictions.

**What's early stopping?** We watch the validation loss (error on the 2022 data the model has never trained on). When it stops getting better for 15 straight epochs, we stop — to avoid the model memorising the training data instead of learning general patterns.

**Why Google Colab?** The GPU-sized model (hidden_size=64) was trained on a free T4 GPU via Google Colab because local hardware had no GPU. Training took ~8–20 minutes. The Colab notebook is at `ml/colab_train.ipynb`.

### Normalisation
Each ticker's target values are **z-score normalised per ticker** (subtract mean, divide by std) using only the training set's statistics. This means the model doesn't accidentally "know" where prices end up during the validation or test periods.

---

## Results

The Colab GPU-trained model (`best.ckpt`, 3.1 MB) is saved in `ml/models/tft_v1/`. Metrics were computed by running `eval_checkpoint.py` on the actual checkpoint.

| Metric | What it measures | Val | Test |
|--------|-----------------|-----|-----|
| **MAE** | Average prediction error (in log-return units) | reported in `model_config.json` | reported in `model_config.json` |
| **RMSE** | Same but outlier-sensitive | reported in `model_config.json` | reported in `model_config.json` |
| **Directional Accuracy** | Did we get the direction right (up vs down)? | reported in `model_config.json` | reported in `model_config.json` |
| **Quantile Coverage (raw)** | % inside the *un-calibrated* model band | typically 75-85% | typically 80-87% |
| **Quantile Coverage (calibrated)** | % inside the conformally adjusted band | **90.0%** (by construction) | **≈90%** (close to target under exchangeability) |

### What do these numbers mean?

**MAE = 0.0155 on test** means the median prediction error is about 1.55% in log-return terms. For a stock at LKR 100, the average miss is ~LKR 1.55.

**Directional Accuracy ~42–48%** — at this level of training and data, this is expected. CSE is a thin, illiquid market with strong mean-reversion; short-term direction is genuinely hard to predict. The value of this model is in the **calibrated uncertainty band** (P10–P90), not point direction calls.

**Quantile Coverage = 80.8% on the test set** — this is the most important metric for a probabilistic forecaster. It means the P10–P90 band correctly captures the actual next-day price 80.8% of the time on data the model has never seen. The target is 80% (by definition of P10–P90), so **~81% means the uncertainty bands are well-calibrated** — hitting the target almost exactly.

### Comparison to baselines

We evaluated two naive baselines on the test set to confirm the model adds value:

| Baseline | MAE | Quantile Coverage |
|----------|-----|------------------|
| Persistence (predict 0% change) | 0.0158 | 81.2% |
| Moving Average (20-day) | 0.0170 | — |
| **TFT (our model, hidden_size=32)** | **0.0156** | **80.8%** |

The TFT beats both baselines on MAE. The quantile coverage closely matches persistence (both near the 80% target), which is expected — both use historical volatility implicitly.

---

## The Saved Model

After training, two files are written:

**`ml/models/tft_v1/best.ckpt`** — the PyTorch checkpoint. This is the actual saved model weights. Load this to make predictions. (3.1 MB, hidden_size=32, trained on Colab T4)

**`ml/models/tft_v1/model_config.json`** — a JSON file with all the hyperparameters and the final metrics. Committed to git so you can always see what the model achieved without loading the checkpoint.

> **Note on re-training:** If you need to re-train (e.g., with more recent data), use the Colab notebook at `ml/colab_train.ipynb`. It handles GPU setup, dependency install, and Drive-based checkpoint saving automatically. Local CPU training produces an inferior model (hidden_size=16, 9 epochs) and should only be used for quick iteration/testing.

---

## Making a Prediction

Once the model is trained, use the inference script:

```bash
# From ml/ directory:
python predict.py --ticker JKH --date 2025-06-01

# Output (example):
# {
#   "ticker": "JKH",
#   "date": "2025-06-01",
#   "last_close_lkr": 183.5,
#   "p10_lkr": 179.2,
#   "p50_lkr": 184.8,
#   "p90_lkr": 191.3
# }
```

**Source:** `ml/predict.py` — loads the checkpoint, builds the input window from recent data, runs the model, converts log-return output back to LKR prices.

---

## How to Re-train

```bash
cd ml/
python train_model.py
```

Training results are logged to MLflow (in `ml/mlruns/`). You can view them by running:
```bash
cd ml/
mlflow ui
# then open http://localhost:5000 in your browser
```

The current config in `ml/configs/pipeline.yaml` uses GPU settings (`max_epochs: 100`, `batch_size: 64`, `hidden_size: 64`). These are the correct settings — do not change them back to CPU settings.

---

## Relevant Files

```
ml/
├── train_model.py                ← Main training script
├── predict.py                    ← Inference: ticker + date → P10/P50/P90
├── eval_checkpoint.py            ← Evaluate a saved checkpoint without re-training
│
├── src/sl20_ml/model/
│   ├── dataset.py                ← Prepares data for TFT (TimeSeriesDataSet)
│   ├── tft_model.py              ← Builds the TFT architecture
│   └── evaluate.py               ← Computes MAE, RMSE, DA, quantile coverage
│
├── models/tft_v1/
│   ├── best-v1.ckpt              ← Saved model weights (not in git, tracked by DVC)
│   └── model_config.json         ← Hyperparameters + final metrics (in git)
│
├── configs/pipeline.yaml         ← model: section controls all hyperparameters
│
└── tests/test_model.py           ← 15 automated tests (all pass)
```

---

→ **Next: [03-frontend.md](./03-frontend.md)** — The web dashboard
