"""
Static stock info and key stats for all 20 SL20 tickers.
Sections 10 of SPEC.md — hardcoded because:
  - Company blurbs don't change often
  - Market cap / P/E are not computable from our feature panel
"""
from typing import Optional

from app.models.stocks import StockInfo, StockKeyStats

# ── Ordered list of SL20 tickers ──────────────────────────────────────────────
SL20_TICKERS: list[str] = [
    "AEL", "BUKI", "CARG", "CCS", "COMB",
    "CTC", "DFCC", "DIAL", "HAYL", "HHL",
    "HNB", "JKH", "LIOC", "LION", "MELS",
    "NTB", "SAMP", "SPEN", "TKYO", "VONE",
]

# ── Company info (blurbs) ──────────────────────────────────────────────────────
_STOCK_INFO_RAW: dict[str, dict] = {
    "JKH": {
        "name": "John Keells Holdings PLC",
        "sector": "Diversified",
        "blurb": "Sri Lanka's largest listed conglomerate with interests in transportation, leisure, property, consumer foods, financial services, and IT. JKH is widely regarded as a bellwether for the Sri Lankan economy.",
    },
    "COMB": {
        "name": "Commercial Bank of Ceylon PLC",
        "sector": "Banking",
        "blurb": "The largest private sector bank in Sri Lanka by assets, providing retail, corporate, and international banking services. COMB is a key indicator of Sri Lanka's broader credit market health.",
    },
    "DIAL": {
        "name": "Dialog Axiata PLC",
        "sector": "Telecommunications",
        "blurb": "Sri Lanka's largest mobile telecommunications provider, offering mobile, broadband, satellite, and digital services. Dialog is a subsidiary of Malaysia's Axiata Group.",
    },
    "SAMP": {
        "name": "Sampath Bank PLC",
        "sector": "Banking",
        "blurb": "One of Sri Lanka's leading commercial banks, known for innovation in retail banking and digital financial services.",
    },
    "HAYL": {
        "name": "Hayleys PLC",
        "sector": "Diversified",
        "blurb": "A diversified conglomerate with operations in agriculture, manufacturing, transportation, consumer, and IT sectors. Hayleys is one of Sri Lanka's oldest and most respected companies.",
    },
    "CTC": {
        "name": "Ceylon Tobacco Company PLC",
        "sector": "Consumer Staples",
        "blurb": "The sole manufacturer and distributor of cigarettes in Sri Lanka, operating under license from British American Tobacco. CTC is known for its high dividend yield.",
    },
    "HNB": {
        "name": "Hatton National Bank PLC",
        "sector": "Banking",
        "blurb": "One of Sri Lanka's largest commercial banks, with a strong presence in both urban and rural lending. HNB is the leading bank serving Sri Lanka's plantation sector.",
    },
    "LIOC": {
        "name": "Lanka IOC PLC",
        "sector": "Energy",
        "blurb": "Sri Lanka's second largest fuel retailer, a subsidiary of Indian Oil Corporation. LIOC operates petroleum product distribution and retail fuel stations across the island.",
    },
    "SPEN": {
        "name": "Aitken Spence PLC",
        "sector": "Diversified",
        "blurb": "A Sri Lankan conglomerate active in tourism, maritime logistics, power generation, printing, and garment manufacturing.",
    },
    "DFCC": {
        "name": "DFCC Bank PLC",
        "sector": "Banking",
        "blurb": "Sri Lanka's first development bank, now a full-service commercial bank offering personal, SME, and corporate banking solutions.",
    },
    "NTB": {
        "name": "Nations Trust Bank PLC",
        "sector": "Banking",
        "blurb": "A mid-sized commercial bank in Sri Lanka focused on retail and SME banking, known for its American Express card franchise in the country.",
    },
    "BUKI": {
        "name": "Bukit Darah PLC",
        "sector": "Diversified",
        "blurb": "The holding company of the Carson Cumberbatch group, with investments in palm oil, beverages, real estate, and financial services.",
    },
    "CARG": {
        "name": "Cargills (Ceylon) PLC",
        "sector": "Consumer Staples",
        "blurb": "Sri Lanka's leading food retail chain and FMCG manufacturer, operating the Cargills Food City supermarket network and producing Cargills Magic ice cream and other branded foods.",
    },
    "CCS": {
        "name": "Ceylon Cold Stores PLC",
        "sector": "Consumer Staples",
        "blurb": "The manufacturer of Elephant House soft drinks and ice creams, one of Sri Lanka's most iconic consumer brands. A subsidiary of John Keells Holdings.",
    },
    "HHL": {
        "name": "Hemas Holdings PLC",
        "sector": "Diversified",
        "blurb": "A diversified company with leading businesses in healthcare, consumer products (Baby Cheramy, Clogard), and transportation.",
    },
    "LION": {
        "name": "Lion Brewery (Ceylon) PLC",
        "sector": "Consumer Staples",
        "blurb": "Sri Lanka's largest brewery and the producer of Lion Lager, Carlsberg, and other beer brands. A subsidiary of the Carson Cumberbatch group.",
    },
    "MELS": {
        "name": "Melstacorp PLC",
        "sector": "Diversified",
        "blurb": "The holding company of the Distilleries Company of Sri Lanka group, with interests in beverages (arrack), insurance, and telecommunications.",
    },
    "TKYO": {
        "name": "Tokyo Cement Company (Lanka) PLC",
        "sector": "Construction Materials",
        "blurb": "Sri Lanka's leading cement manufacturer, producing both ordinary Portland cement and blended cements under the Tokyo Super and Tokyo Supercrete brands.",
    },
    "VONE": {
        "name": "Vallibel One PLC",
        "sector": "Diversified",
        "blurb": "A diversified holding company with interests in tiles (Royal Ceramics), aluminium, banking (LB Finance), and leisure.",
    },
    "AEL": {
        "name": "Access Engineering PLC",
        "sector": "Construction",
        "blurb": "A leading Sri Lankan construction company specialising in infrastructure, civil engineering, and road construction. Involved in many of the country's major infrastructure projects.",
    },
}

# ── Estimated market cap (LKR millions) and P/E ratios ────────────────────────
_KEY_STATS_RAW: dict[str, dict] = {
    "JKH":  {"marketCap": 285_000, "peRatio": 18.5},
    "COMB": {"marketCap": 135_000, "peRatio": 8.2},
    "DIAL": {"marketCap": 95_000,  "peRatio": 12.4},
    "SAMP": {"marketCap": 78_000,  "peRatio": 7.1},
    "HAYL": {"marketCap": 42_000,  "peRatio": 11.3},
    "CTC":  {"marketCap": 190_000, "peRatio": 15.8},
    "HNB":  {"marketCap": 110_000, "peRatio": 7.8},
    "LIOC": {"marketCap": 28_000,  "peRatio": 9.2},
    "SPEN": {"marketCap": 38_000,  "peRatio": 13.1},
    "DFCC": {"marketCap": 32_000,  "peRatio": 6.4},
    "NTB":  {"marketCap": 22_000,  "peRatio": 7.9},
    "BUKI": {"marketCap": 18_000,  "peRatio": None},
    "CARG": {"marketCap": 65_000,  "peRatio": 22.1},
    "CCS":  {"marketCap": 88_000,  "peRatio": 19.6},
    "HHL":  {"marketCap": 45_000,  "peRatio": 14.2},
    "LION": {"marketCap": 72_000,  "peRatio": 11.7},
    "MELS": {"marketCap": 35_000,  "peRatio": 8.9},
    "TKYO": {"marketCap": 25_000,  "peRatio": 10.3},
    "VONE": {"marketCap": 20_000,  "peRatio": None},
    "AEL":  {"marketCap": 15_000,  "peRatio": 16.4},
}

# Pre-build StockInfo objects once at import time
STOCK_INFO: dict[str, StockInfo] = {
    ticker: StockInfo(ticker=ticker, **data)
    for ticker, data in _STOCK_INFO_RAW.items()
}

# Static portion of StockKeyStats (dynamic 52w/volume added by price_service in Iteration 4)
STOCK_KEY_STATS_STATIC: dict[str, dict] = _KEY_STATS_RAW


def get_stock_info(ticker: str) -> Optional[StockInfo]:
    return STOCK_INFO.get(ticker.upper())


def get_static_key_stats(ticker: str) -> Optional[dict]:
    """Returns {'marketCap': float, 'peRatio': float|None} or None if unknown."""
    return STOCK_KEY_STATS_STATIC.get(ticker.upper())
