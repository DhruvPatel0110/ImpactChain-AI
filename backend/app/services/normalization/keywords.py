"""
Normalization Pipeline — Keywords & Watchlists

Central registry for all domain-specific terms used across the pipeline:
- Commodity terms (PhraseMatcher in Step 2)
- Supply chain signal terms (PhraseMatcher in Step 2)
- Company watchlist (relevance filter in Step 3A)
- Logistics locations (relevance filter in Step 3A)
- Source credibility rankings (primary selection in Step 3C)

Extend these lists as you discover gaps in extraction/filtering.
"""


# =============================================================================
# COMMODITY TERMS — matched via spaCy PhraseMatcher in Step 2
# =============================================================================

COMMODITY_TERMS = [
    # Energy
    "crude oil", "brent crude", "brent", "WTI", "natural gas", "LNG", "LPG",
    "coal", "petroleum", "diesel", "jet fuel", "kerosene", "gasoline",
    "heating oil", "fuel oil", "oil", "gas",

    # Metals & Mining
    "lithium", "cobalt", "copper", "aluminium", "aluminum", "iron ore",
    "nickel", "zinc", "rare earth", "palladium", "platinum", "gold",
    "silver", "tin", "manganese", "titanium", "tungsten", "uranium",

    # Agricultural
    "wheat", "corn", "soybean", "soybeans", "rice", "sugar", "cotton",
    "palm oil", "fertilizer", "urea", "coffee", "cocoa", "rubber",
    "timber", "lumber",

    # Tech / Industrial
    "semiconductor", "chip", "microchip", "silicon wafer", "DRAM",
    "NAND flash", "GPU", "CPU", "display panel", "battery",
    "lithium-ion", "EV battery", "solar panel", "polysilicon",

    # Logistics-adjacent commodities
    "shipping container", "freight", "cargo", "tanker", "bulk carrier",
    "steel", "cement", "glass",
]


# =============================================================================
# SUPPLY CHAIN SIGNAL TERMS — matched via spaCy PhraseMatcher in Step 2
# =============================================================================

SUPPLY_CHAIN_SIGNALS = [
    # Disruption signals
    "shortage", "supply disruption", "supply chain", "bottleneck", "backlog",
    "port congestion", "strike", "blockade", "sanctions", "trade restriction",
    "tariff", "embargo", "export ban", "import ban", "trade war",
    "production halt", "factory shutdown", "factory closure", "plant shutdown",
    "force majeure", "disruption", "supply crunch", "inventory shortage",

    # Logistics signals
    "port", "strait", "canal", "shipping lane", "warehouse", "logistics hub",
    "rerouting", "logistics", "shipping", "shipping delay", "shipping cost",
    "freight rate", "container shortage", "vessel", "grounded",

    # Price/market signals
    "price spike", "price surge", "price drop", "price hike", "rate increase",
    "inflationary", "cost pressure", "margin pressure", "price volatility",
    "market crash", "demand surge", "oversupply", "undersupply",
    "stockpile", "reserve", "quota", "output cut", "production cut",
]


# =============================================================================
# COMPANY WATCHLIST — checked during relevance filter (Step 3A)
# Case-insensitive matching performed at filter time
# =============================================================================

COMPANY_WATCHLIST = [
    # Tech / Semiconductors
    "Tesla", "TSMC", "Samsung", "Apple", "Intel", "Foxconn", "Nvidia",
    "AMD", "Qualcomm", "SK Hynix", "Micron", "ASML", "MediaTek",
    "Sony", "Huawei", "BYD", "CATL", "Panasonic",

    # Energy / Oil & Gas
    "Reliance", "Reliance Industries", "ONGC", "BPCL", "IOC",
    "Indian Oil", "HPCL", "Saudi Aramco", "ExxonMobil", "Chevron",
    "Shell", "BP", "TotalEnergies", "ConocoPhillips", "Gazprom",
    "Rosneft", "Petrobras", "ADNOC",

    # Shipping / Logistics
    "Maersk", "Hapag-Lloyd", "MSC", "CMA CGM", "COSCO",
    "Evergreen", "ONE", "Yang Ming", "ZIM", "FedEx", "UPS", "DHL",

    # Mining / Materials
    "BHP", "Rio Tinto", "Vale", "Glencore", "Freeport-McMoRan",
    "Albemarle", "SQM", "Tata Steel", "POSCO", "ArcelorMittal",

    # Industrials / Auto
    "Toyota", "Volkswagen", "SAIC", "General Motors", "Ford",
    "Boeing", "Airbus", "Siemens", "General Electric", "Caterpillar",

    # Orgs / Trade bodies
    "OPEC", "OPEC+", "WTO", "IMF", "World Bank",
]


# =============================================================================
# LOGISTICS LOCATIONS — strategic locations for relevance filter (Step 3A)
# Matched against geo_locations and gpe_locations arrays
# =============================================================================

LOGISTICS_LOCATIONS = [
    # Canals & Straits
    "Suez Canal", "Panama Canal", "Strait of Hormuz", "Strait of Malacca",
    "Bab el-Mandeb", "Bosphorus", "Dardanelles", "Strait of Gibraltar",
    "Taiwan Strait",

    # Seas / Waterways
    "Red Sea", "South China Sea", "Persian Gulf", "Gulf of Aden",
    "Arabian Sea", "Gulf of Mexico", "Mediterranean Sea",

    # Major Ports / Hubs
    "Singapore", "Rotterdam", "Shanghai", "Shenzhen", "Hong Kong",
    "Busan", "Jebel Ali", "Dubai", "Mundra", "Mumbai",
    "Los Angeles", "Long Beach", "Antwerp", "Hamburg",

    # Generic logistics terms (if found in location context)
    "port", "shipping lane", "logistics hub", "trade route",
    "free trade zone", "special economic zone",
]


# =============================================================================
# SOURCE CREDIBILITY RANK — tiebreaker for primary source selection (Step 3C)
# Lower number = higher credibility. Used ONLY when quantitative_score is tied.
# =============================================================================

SOURCE_CREDIBILITY_RANK = {
    "reuters": 1,
    "bloomberg": 2,
    "financial times": 3,
    "financial_times": 3,
    "ft": 3,
    "wsj": 4,
    "wall street journal": 4,
    "cnbc": 5,
    "bbc": 6,
    "bbc world": 6,
    "al jazeera": 7,
    "nikkei": 8,
    "nikkei asia": 8,
    "economic times": 9,
    "economic_times": 9,
    "newsapi": 10,
    "other": 99,
}


def get_source_rank(source_name: str) -> int:
    """Get credibility rank for a source. Lower = more credible."""
    if not source_name:
        return SOURCE_CREDIBILITY_RANK["other"]
    normalized = source_name.lower().strip()
    return SOURCE_CREDIBILITY_RANK.get(normalized, SOURCE_CREDIBILITY_RANK["other"])
