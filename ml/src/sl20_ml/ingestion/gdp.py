"""
gdp.py — Loader for World Bank World Development Indicators (WDI) export.

Source file: data/raw/fundamentals/GDP.csv
  Format: World Bank WDI CSV export — all indicators for Sri Lanka (LKA).
  Layout:
    Row 0 : "Data Source", "World Development Indicators"
    Row 1 : blank
    Row 2 : "Last Updated Date", "<date>"
    Row 3 : blank
    Row 4 : column headers — Country Name, Country Code, Indicator Name,
                             Indicator Code, 1960, 1961, ..., 2025
    Row 5+: data — one row per indicator (1,486 rows total for LKA)

We extract a small set of macroeconomic indicators relevant to the ML model.
The indicator codes to extract are defined in configs/pipeline.yaml under
`wdi_indicators`.

Output is a tidy (long-then-pivoted) annual DataFrame:
  year (int), gdp_growth_pct, gdp_constant_usd, inflation_pct, unemployment_pct
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_CSV_SKIP_ROWS   = 4     # Skip rows 0-3 (metadata); row 4 becomes the header
_COUNTRY_CODE    = "LKA"
_FIRST_DATA_YEAR = 1960  # WDI data starts here


def load_wdi(fundamentals_dir: Path, indicators: dict[str, str]) -> pd.DataFrame:
    """
    Load and extract macro indicators from the World Bank WDI export.

    Parameters
    ----------
    fundamentals_dir : Path
        Directory containing GDP.csv.
    indicators : dict[str, str]
        Mapping of output_column_name -> WDI indicator code.
        Example: {"gdp_growth_pct": "NY.GDP.MKTP.KD.ZG", ...}
        Typically loaded from cfg["wdi_indicators"].

    Returns
    -------
    pd.DataFrame with columns: year (int) + one column per indicator.
    Rows: one per year with data available (typically 2011–2024).
    Missing years or indicators produce NaN, not dropped rows.
    """
    path = _find_gdp_csv(fundamentals_dir)
    logger.info(f"Loading WDI indicators from {path.name} ...")
    logger.info(f"  Extracting {len(indicators)} indicators for {_COUNTRY_CODE}")

    # Read the full CSV; first 4 rows are metadata
    df = pd.read_csv(path, skiprows=_CSV_SKIP_ROWS, dtype=str)

    # Filter to Sri Lanka only
    df = df[df["Country Code"] == _COUNTRY_CODE].copy()

    # Year columns are strings like "1960", "1961", ..., "2025"
    year_cols = [c for c in df.columns if c.isdigit() and int(c) >= _FIRST_DATA_YEAR]

    results = {}
    for col_name, indicator_code in indicators.items():
        row = df[df["Indicator Code"] == indicator_code]
        if row.empty:
            logger.warning(f"  Indicator not found: {indicator_code} ({col_name})")
            results[col_name] = pd.Series(dtype=float)
            continue

        # Take the first matching row (should be exactly one)
        series = (
            row[year_cols]
            .iloc[0]
            .rename(col_name)
            .pipe(pd.to_numeric, errors="coerce")
        )
        series.index = series.index.astype(int)   # year as int
        n_vals = series.notna().sum()
        last_year = int(series.dropna().index.max()) if n_vals else None
        logger.info(
            f"  {col_name:<22s} ({indicator_code}): "
            f"{n_vals} annual values, latest: {last_year}"
        )
        results[col_name] = series

    # Combine into a DataFrame indexed by year
    out = pd.DataFrame(results)
    out.index.name = "year"
    out = out.reset_index()
    out["year"] = out["year"].astype(int)

    # Drop rows where every indicator is NaN (pre-data years)
    indicator_cols = list(indicators.keys())
    out = out.dropna(subset=indicator_cols, how="all").reset_index(drop=True)

    logger.info(
        f"  -> {len(out)} annual rows | "
        f"years {int(out['year'].min())}–{int(out['year'].max())}"
    )
    return out


def _find_gdp_csv(fundamentals_dir: Path) -> Path:
    """Locate GDP.csv (exact name) in the fundamentals directory."""
    path = fundamentals_dir / "GDP.csv"
    if not path.exists():
        # Try case-insensitive glob
        matches = sorted(fundamentals_dir.glob("GDP*.csv"))
        if not matches:
            raise FileNotFoundError(
                f"GDP.csv not found in {fundamentals_dir}. "
                "Expected: data/raw/fundamentals/GDP.csv"
            )
        path = matches[0]
    return path
