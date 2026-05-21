"""Static news fixtures — sentiment model is deferred (Section 18)."""
from app.models.news import NewsItem

# 20 hardcoded items (Section 11 of SPEC.md)
_RAW: list[dict] = [
    {"id": "n01", "source": "EconomyNext", "isLocal": True,  "headline": "CSE benchmark index edges higher on banking sector gains",                   "url": "https://economynext.com",         "sentiment": "Positive", "timeAgo": "1h ago"},
    {"id": "n02", "source": "Daily FT",    "isLocal": True,  "headline": "Sri Lanka central bank holds policy rates steady for third consecutive month", "url": "https://ft.lk",                   "sentiment": "Neutral",  "timeAgo": "2h ago"},
    {"id": "n03", "source": "Reuters",     "isLocal": False, "headline": "Asian markets mixed as Fed rate outlook weighs on sentiment",                  "url": "https://reuters.com",             "sentiment": "Neutral",  "timeAgo": "3h ago"},
    {"id": "n04", "source": "LBO",         "isLocal": True,  "headline": "JKH reports strong quarterly earnings driven by leisure recovery",             "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "4h ago"},
    {"id": "n05", "source": "EconomyNext", "isLocal": True,  "headline": "Foreign investor net selling continues on CSE for second week",                "url": "https://economynext.com",         "sentiment": "Negative", "timeAgo": "5h ago"},
    {"id": "n06", "source": "Reuters",     "isLocal": False, "headline": "Oil prices rise on Middle East supply concerns",                               "url": "https://reuters.com",             "sentiment": "Negative", "timeAgo": "6h ago"},
    {"id": "n07", "source": "Daily FT",    "isLocal": True,  "headline": "Dialog Axiata to invest LKR 15bn in 5G infrastructure rollout",               "url": "https://ft.lk",                   "sentiment": "Positive", "timeAgo": "7h ago"},
    {"id": "n08", "source": "LBO",         "isLocal": True,  "headline": "Sri Lanka rupee stable against dollar ahead of IMF review",                   "url": "https://lankabusinessonline.com", "sentiment": "Neutral",  "timeAgo": "8h ago"},
    {"id": "n09", "source": "Reuters",     "isLocal": False, "headline": "Gold hits three-month high on dollar weakness",                                "url": "https://reuters.com",             "sentiment": "Positive", "timeAgo": "10h ago"},
    {"id": "n10", "source": "EconomyNext", "isLocal": True,  "headline": "Commercial Bank posts record profit; dividend declared",                       "url": "https://economynext.com",         "sentiment": "Positive", "timeAgo": "12h ago"},
    {"id": "n11", "source": "Daily FT",    "isLocal": True,  "headline": "Tourism arrivals hit post-crisis high boosting leisure stocks",                "url": "https://ft.lk",                   "sentiment": "Positive", "timeAgo": "1d ago"},
    {"id": "n12", "source": "Reuters",     "isLocal": False, "headline": "VIX spikes as US inflation data beats expectations",                           "url": "https://reuters.com",             "sentiment": "Negative", "timeAgo": "1d ago"},
    {"id": "n13", "source": "LBO",         "isLocal": True,  "headline": "Cargills Ceylon expands retail footprint with 20 new stores",                  "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "1d ago"},
    {"id": "n14", "source": "EconomyNext", "isLocal": True,  "headline": "CSE suspends trading in two small-cap stocks on disclosure concerns",          "url": "https://economynext.com",         "sentiment": "Negative", "timeAgo": "1d ago"},
    {"id": "n15", "source": "Reuters",     "isLocal": False, "headline": "S&P 500 closes at record high on tech earnings optimism",                      "url": "https://reuters.com",             "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n16", "source": "Daily FT",    "isLocal": True,  "headline": "Hatton National Bank targets 15% loan growth in FY2025",                       "url": "https://ft.lk",                   "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n17", "source": "LBO",         "isLocal": True,  "headline": "IMF approves next tranche of Sri Lanka bailout facility",                      "url": "https://lankabusinessonline.com", "sentiment": "Positive", "timeAgo": "2d ago"},
    {"id": "n18", "source": "Reuters",     "isLocal": False, "headline": "China factory output slows, raising concerns for Asian exports",                "url": "https://reuters.com",             "sentiment": "Negative", "timeAgo": "3d ago"},
    {"id": "n19", "source": "EconomyNext", "isLocal": True,  "headline": "Ceylon Tobacco pays special dividend; yield exceeds 8%",                       "url": "https://economynext.com",         "sentiment": "Positive", "timeAgo": "3d ago"},
    {"id": "n20", "source": "Daily FT",    "isLocal": True,  "headline": "Sri Lanka inflation falls to 4.2%, lowest in four years",                      "url": "https://ft.lk",                   "sentiment": "Positive", "timeAgo": "4d ago"},
]

# Pre-build the model objects once at import time
NEWS_ITEMS: list[NewsItem] = [NewsItem(**item) for item in _RAW]


def get_news() -> list[NewsItem]:
    return NEWS_ITEMS
