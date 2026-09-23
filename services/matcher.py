import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple

# Broad catalog of popular quick-commerce brands across all categories in India:
# Dairy, Bakery, Beverages, Snacks, Staples, Personal Care, Household & Baby
KNOWN_BRANDS = [
    # Dairy & Breakfast
    "amul", "mother dairy", "nandini", "nestle", "nestlé", "heritage", 
    "country delight", "akshayakalpa", "arokya", "humpy farms", "yakult", 
    "gowardhan", "epigamia", "danone", "milky mist", "sid's farm", "godrej jersey",
    "harvest gold", "english oven", "the health factory", "britannia", 
    "modern", "bisk farm", "kellogg's", "kelloggs", "quaker", "saffola fittify",

    # Staples, Atta, Rice, Oil & Spices
    "aashirvaad", "fortune", "saffola", "tata sampann", "tata", "dhara", 
    "gemini", "emami", "sundrop", "figaro", "borges", "del monte", "daawat", 
    "india gate", "kohinoor", "24 mantra", "nature fresh", "pillsbury", 
    "catch", "everest", "mdh", "badshah", "tata salt",

    # Snacks, Biscuits & Confectionery
    "lays", "lay's", "kurkure", "bingo", "haldiram's", "haldiram", "bikaji", 
    "doritos", "pringles", "balaji", "cadbury", "kitkat", "kit kat", "ferrero", 
    "parle", "sunfeast", "oreo", "dark fantasy", "5 star", "snickers",

    # Beverages (Hot & Cold)
    "coca-cola", "coca cola", "coke", "pepsi", "sprite", "thums up", "7up", 
    "fanta", "mirinda", "limca", "mountain dew", "maaza", "slice", "frooti", 
    "real", "tropicana", "paper boat", "red bull", "monster", "nescafe", 
    "nescafé", "bru", "tata tea", "brooke bond", "red label", "taj mahal", 
    "wagh bakri", "tetley", "twinings", "bournvita", "horlicks", "boost", "complan",

    # Personal Care, Hygiene & Baby
    "dettol", "lifebuoy", "dove", "nivea", "pears", "lux", "fiama", "colgate", 
    "pepsodent", "sensodyne", "close up", "oral-b", "head & shoulders", "pantene", 
    "sunsilk", "tresemme", "l'oreal", "garnier", "himalaya", "parachute", 
    "bajaj", "vaseline", "pond's", "boroline", "whisper", "stayfree", 
    "gillette", "old spice", "pampers", "mamypoko", "huggies", "sebamed", 
    "johnson's", "cerelac", "aptamil", "dabur", "patanjali",

    # Household & Cleaning
    "surf excel", "ariel", "tide", "rin", "henko", "wheel", "vim", "pril", 
    "exo", "scotch-brite", "harpic", "lizol", "domex", "colin", "comfort", 
    "godrej aer", "odonil", "good knight", "all out", "hit", "mortein", "safal"
]

# Common conflicting variant pairs across FMCG (if item A has variant 1 and item B has variant 2, they cannot match)
MUTUALLY_EXCLUSIVE_VARIANTS = [
    # Bread variants
    {"brown", "white"},
    {"multigrain", "white"},
    {"atta", "white"},
    {"milk bread", "brown bread"},
    # Drink / Sugar variants
    {"diet", "regular"},
    {"zero", "classic"},
    {"zero sugar", "original"},
    {"sugar free", "regular"},
    # Dairy fat / types
    {"toned", "full cream"},
    {"toned", "double toned"},
    {"skimmed", "full cream"},
    {"lactose free", "regular"},
    {"cow", "buffalo"},
    # Coffee / Tea
    {"instant", "filter"},
    {"green tea", "black tea"},
    # Toothpaste / Personal care
    {"maxfresh", "total"},
    {"active salt", "total"},
    # Snack flavours
    {"magic masala", "classic salted"},
    {"cream & onion", "classic salted"},
    {"cream and onion", "classic salted"},
    {"pudina", "classic salted"},
    # Oil types
    {"mustard", "sunflower"},
    {"mustard", "refined"},
    {"olive", "mustard"},
    {"sunflower", "groundnut"},
    {"soyabean", "mustard"},
]


def parse_price(val: Any) -> Optional[float]:
    """Parse various price representations ('₹30', '33', '1,295', 30.0) into a clean float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    
    val_str = str(val).strip().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", val_str)
    if match:
        try:
            return round(float(match.group(1)), 2)
        except ValueError:
            return None
    return None


def _normalize_unit(val: float, unit_str: str) -> Tuple[Optional[str], float]:
    """
    Normalizes volume to ml, weight to g, and counts to pcs.
    """
    unit_str = unit_str.lower().strip()
    
    # Volume units
    if unit_str in ["l", "ltr", "liter", "litres", "litre"]:
        return "ml", round(val * 1000.0, 1)
    if unit_str in ["ml", "milliliters", "millilitres"]:
        return "ml", round(val, 1)
        
    # Weight units
    if unit_str in ["kg", "kgs", "kilo", "kilogram", "kilograms"]:
        return "g", round(val * 1000.0, 1)
    if unit_str in ["g", "gm", "gms", "gram", "grams"]:
        return "g", round(val, 1)
        
    # Piece / count units
    count_units = [
        "pcs", "piece", "pieces", "unit", "units", "pack", "packs",
        "tablet", "tablets", "capsule", "capsules", "sachet", "sachets",
        "wipe", "wipes", "roll", "rolls", "can", "cans", "bottle", "bottles",
        "pouch", "pouches", "bar", "bars", "diaper", "diapers", "sheet", "sheets"
    ]
    if unit_str in count_units:
        return "pcs", round(val, 1)

    return None, val


def parse_quantity(text: str) -> Dict[str, Any]:
    """
    Extract volume, weight, or unit count and convert to base units (ml, g, or pcs).
    Handles multi-packs ('2 x 200 ml', 'pack of 3 (100g)', '4 x 75g', '1.2kg', etc.).
    """
    if not text:
        return {"raw": "", "value": None, "unit": None, "display": ""}

    cleaned = str(text).replace("\n", " ").strip()

    # 1. Multi-pack patterns like '2 x 200 ml', '3x400g', 'pack of 2 (200 ml)'
    multi_match = re.search(
        r"(\d+)\s*(?:x|\*|packs?\s*of)\s*(\d+(?:\.\d+)?)\s*(ml|l|ltr|liter|litres|litre|g|gm|gms|gram|grams|kg|kgs|pcs|pieces?|tablets?|bars?|cans?|bottles?|wipes?|rolls?)\b",
        cleaned,
        re.IGNORECASE
    )
    if multi_match:
        multiplier = float(multi_match.group(1))
        unit_val = float(multi_match.group(2))
        unit_str = multi_match.group(3).lower()
        total_val = multiplier * unit_val
        
        base_unit, normalized_val = _normalize_unit(total_val, unit_str)
        display = f"{int(multiplier)} x {int(unit_val) if unit_val.is_integer() else unit_val} {unit_str.upper()}"
        return {
            "raw": cleaned,
            "value": normalized_val,
            "unit": base_unit,
            "display": display
        }

    # 2. Extract specific volume or weight unit (ml, l, g, kg) EVEN IF inside parentheses like '1 pack (500 ml)'
    vol_weight_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(ml|l|ltr|liter|litres|litre|g|gm|gms|gram|grams|kg|kgs)\b",
        cleaned,
        re.IGNORECASE
    )
    if vol_weight_match:
        unit_val = float(vol_weight_match.group(1))
        unit_str = vol_weight_match.group(2).lower()
        base_unit, normalized_val = _normalize_unit(unit_val, unit_str)
        
        # Friendly display
        if base_unit == "ml" and normalized_val >= 1000:
            display = f"{normalized_val/1000:g} L"
        elif base_unit == "g" and normalized_val >= 1000:
            display = f"{normalized_val/1000:g} kg"
        elif base_unit:
            display = f"{normalized_val:g} {base_unit}"
        else:
            display = cleaned

        return {
            "raw": cleaned,
            "value": normalized_val,
            "unit": base_unit,
            "display": display
        }

    # 3. Fallback to generic piece / count units
    count_match = re.search(
        r"(\d+)\s*(?:pcs|piece|pieces|units?|tablets?|capsules?|wipes?|rolls?|bars?|cans?|bottles?|pouches?|diapers?|sheets?)\b",
        cleaned,
        re.IGNORECASE
    )
    if count_match:
        cnt = float(count_match.group(1))
        return {"raw": cleaned, "value": cnt, "unit": "pcs", "display": f"{int(cnt)} pcs"}

    # 4. Fallback: single number with 'pack'
    pack_match = re.search(r"(\d+)\s*packs?\b", cleaned, re.IGNORECASE)
    if pack_match:
        cnt = float(pack_match.group(1))
        return {"raw": cleaned, "value": cnt, "unit": "pcs", "display": f"{int(cnt)} pack"}

    return {"raw": cleaned, "value": None, "unit": None, "display": cleaned}


def extract_brand(title: str, query_brand: Optional[str] = None) -> Optional[str]:
    """
    Detect brand name from product title or user query.
    Uses known FMCG brand list, delimiter prefixes, and query context.
    """
    if not title:
        return query_brand

    lower_title = str(title).lower().strip()

    # 1. If query brand exists and is in the title, trust that match
    if query_brand and query_brand in lower_title:
        return query_brand

    # 2. Check known multi-category brands (sort by length descending to match compound names like 'mother dairy' first)
    sorted_brands = sorted(KNOWN_BRANDS, key=len, reverse=True)
    for brand in sorted_brands:
        pattern = r"\b" + re.escape(brand) + r"\b"
        if re.search(pattern, lower_title):
            if brand == "nestlé":
                return "nestle"
            if brand == "lay's":
                return "lays"
            if brand in ["coca cola", "coca-cola"]:
                return "coke"
            return brand

    # 3. Check prefix before standard e-commerce title delimiters (e.g. 'Amul - Taaza', 'Fortune: Refined Oil')
    prefix_match = re.match(r"^([a-zA-Z\s]{2,20})[-:|]", title.strip())
    if prefix_match:
        cand = prefix_match.group(1).strip().lower()
        skip_words = {"the", "new", "fresh", "pure", "best", "organic", "premium", "daily"}
        if len(cand) > 2 and cand not in skip_words:
            return cand

    return query_brand


def clean_title(title: str, brand: Optional[str] = None) -> str:
    """
    General, domain-agnostic title cleaning for semantic comparison.
    Removes container wrappers, promotional text, shelf life claims, quantities, and formatting noise.
    """
    if not title:
        return ""
    
    t = str(title)
    # Remove HTML entities & newlines
    t = t.replace("\n", " ").replace("&nbsp;", " ").replace("\r", " ")
    
    # 1. Remove retailer packaging noise and containers across categories
    container_patterns = [
        r"\|\s*(pouch|tetra\s*pack|pet\s*bottle|bottle|tin|can|jar|tub|box|carton|brick|dispenser|refill|sachet|pack|brik)\b",
        r"\((fino\s*pouch|tetra\s*pack|pouch|bottle|can|carton|tin|tub|refill|dispenser|brik|brick|pet\s*bottle|value\s*pack|combo\s*pack|promo\s*pack)\)",
        r"\b(tetra\s*pack\s*brick|tetra\s*pack|fino\s*pouch|pouch\s*brik|pet\s*bottle)\b",
        r"\b(pouch|carton|tetrapack|brick)\b"
    ]
    for cp in container_patterns:
        t = re.sub(cp, " ", t, flags=re.IGNORECASE)

    # 2. Remove marketing and promotional noise phrases
    promo_patterns = [
        r"\b\d+\s*days?\s*shelf\s*life\b",
        r"\b\d+\s*months?\s*shelf\s*life\b",
        r"\b(special\s*offer|extra\s*\d+%|save\s*₹?\d+|\d+%\s*off|buy\s*\d+\s*get\s*\d+|free|bogo|best\s*price|super\s*saver|mega\s*saver)\b",
        r"\b(value\s*pack|combo\s*pack|promo\s*pack|family\s*pack|twin\s*pack|trial\s*pack)\b",
        r"\b(zero\s*cholesterol|no\s*preservatives|100%\s*pure|natural)\b",
        r"\b1\s*pack\b",
        r"\bpack\s*of\s*\d+\b"
    ]
    for pp in promo_patterns:
        t = re.sub(pp, " ", t, flags=re.IGNORECASE)

    # 3. Strip standalone quantities from title so they don't skew title similarity
    t = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|l|ltr|liter|litres|litre|g|gm|gms|gram|grams|kg|kgs|pcs|pieces?|tablets?|bars?|cans?|bottles?|wipes?|rolls?)\b", " ", t, flags=re.IGNORECASE)

    # 4. Remove punctuation & special characters
    t = re.sub(r"[^A-Za-z0-9\s]", " ", t)
    
    # 5. Remove brand name if known to isolate core product identity
    if brand:
        b_clean = re.sub(r"[^A-Za-z0-9]", "", brand)
        t = re.sub(r"\b" + re.escape(brand) + r"\b", " ", t, flags=re.IGNORECASE)
        if b_clean != brand:
            t = re.sub(r"\b" + re.escape(b_clean) + r"\b", " ", t, flags=re.IGNORECASE)

    # 6. Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def analyze_query(query: Optional[str], extra_terms: Optional[set] = None) -> Dict[str, Any]:
    """
    Parses search query to extract query brand, target quantity, and core category/product tokens.
    `extra_terms` lets callers widen relevance (e.g. 'bread' also accepting 'pav').
    """
    if not query:
        return {"raw_query": "", "brand": None, "qty_info": {}, "tokens": set(), "core_terms": []}

    q = str(query).strip().lower()
    
    # Extract brand from query
    query_brand = None
    sorted_brands = sorted(KNOWN_BRANDS, key=len, reverse=True)
    for b in sorted_brands:
        if re.search(r"\b" + re.escape(b) + r"\b", q):
            query_brand = "nestle" if b == "nestlé" else ("lays" if b == "lay's" else ("coke" if b in ["coca cola", "coca-cola"] else b))
            break

    # Extract target quantity from query (e.g. 'amul milk 500ml', 'fortune oil 5l')
    qty_info = parse_quantity(q)

    # Clean query tokens
    q_clean = re.sub(r"[^a-zA-Z0-9\s]", " ", q)
    raw_tokens = q_clean.split()
    
    # Remove stopwords and query fluff
    stopwords = {
        "the", "a", "an", "and", "or", "in", "at", "for", "with", "buy", "online", 
        "price", "pack", "of", "packet", "bottle", "box", "near", "me"
    }
    if qty_info.get("unit"):
        stopwords.update(["ml", "l", "ltr", "liter", "g", "gm", "gram", "kg", "kgs", "pcs", "piece"])

    core_tokens = [tok for tok in raw_tokens if tok not in stopwords and len(tok) > 1]

    # Widen relevance with caller supplied terms (category synonyms, aliases, ...)
    if extra_terms:
        seen = set(core_tokens)
        for term in extra_terms:
            term = str(term).strip().lower()
            if term and term not in seen:
                core_tokens.append(term)
                seen.add(term)

    return {
        "raw_query": query,
        "normalized_query": q,
        "brand": query_brand,
        "qty_info": qty_info,
        "tokens": set(core_tokens),
        "core_terms": core_tokens
    }


def is_relevant_to_query(title: str, query_info: Dict[str, Any]) -> bool:
    """
    Filters out off-topic / sponsored / cross-sell products returned by quick-commerce search engines.
    For example:
      - Query 'milk' filters out 'Multigrain Mixture Namkeen' or 'Brown Bread'.
      - Query 'amul butter' filters out 'Mother Dairy Milk' or 'Bread'.
    """
    tokens = query_info.get("tokens")
    if not tokens:
        return True

    if not title:
        return False

    title_lower = title.lower()

    # If the user queried a specific brand, reject products that explicitly belong to a different known brand
    q_brand = query_info.get("brand")
    detected_brand = extract_brand(title)
    if q_brand:
        if detected_brand and detected_brand != q_brand:
            return False

    # Check for keyword presence with basic stemming / plural tolerance
    def token_matches_title(tok: str) -> bool:
        if re.search(r"\b" + re.escape(tok) + r"\b", title_lower):
            return True
        # Handle plurals: 'bread' <-> 'breads', 'egg' <-> 'eggs', 'chip' <-> 'chips'
        if tok.endswith("s") and len(tok) > 3:
            singular = tok[:-1]
            if re.search(r"\b" + re.escape(singular) + r"\b", title_lower):
                return True
        else:
            plural = tok + "s"
            if re.search(r"\b" + re.escape(plural) + r"\b", title_lower):
                return True
        return False

    # Check if at least one non-brand core query term is in the product title
    non_brand_tokens = [t for t in tokens if t != q_brand]
    if non_brand_tokens:
        matches = any(token_matches_title(t) for t in non_brand_tokens)
        return matches

    # If query was ONLY a brand (e.g. query='amul' or query='coke'), check if title matches detected brand or contains brand term
    if q_brand:
        return (detected_brand == q_brand) or (q_brand in title_lower)

    return True


def has_conflicting_variants(title_a: str, title_b: str) -> bool:
    """
    Checks if two products represent mutually exclusive product variants.
    (e.g., Brown Bread vs White Bread, Coke Zero vs Regular Coke, Toned vs Full Cream Milk)
    """
    ta = title_a.lower()
    tb = title_b.lower()

    for variant_pair in MUTUALLY_EXCLUSIVE_VARIANTS:
        v_list = list(variant_pair)
        v1, v2 = v_list[0], v_list[1]
        
        p1 = r"\b" + re.escape(v1) + r"\b"
        p2 = r"\b" + re.escape(v2) + r"\b"
        
        has_v1_a = bool(re.search(p1, ta))
        has_v2_a = bool(re.search(p2, ta))
        has_v1_b = bool(re.search(p1, tb))
        has_v2_b = bool(re.search(p2, tb))

        if (has_v1_a and has_v2_b and not has_v2_a and not has_v1_b) or \
           (has_v2_a and has_v1_b and not has_v1_a and not has_v2_b):
            return True

    return False


def calculate_similarity(
    item_a: Dict[str, Any], 
    item_b: Dict[str, Any], 
    query_info: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate semantic similarity score between two normalized products.
    Returns score between 0.0 and 1.0 with strict guardrails.
    """
    brand_a = item_a.get("brand")
    brand_b = item_b.get("brand")

    # Guardrail 1: Conflicting brands CANNOT match (e.g. Nestle vs Amul, Coke vs Pepsi)
    if brand_a and brand_b and brand_a != brand_b:
        return 0.0

    # Guardrail 2: Quantity & unit mismatch check
    qty_a = item_a.get("qty_info", {})
    qty_b = item_b.get("qty_info", {})
    val_a = qty_a.get("value")
    val_b = qty_b.get("value")
    unit_a = qty_a.get("unit")
    unit_b = qty_b.get("unit")

    if unit_a and unit_b:
        # Incompatible units (e.g. grams vs ml, or pcs vs ml)
        if unit_a != unit_b:
            return 0.0
        # If sizes differ by more than 15% (e.g. 500ml vs 1000ml, 1kg vs 5kg), reject match
        if val_a and val_b:
            ratio = min(val_a, val_b) / max(val_a, val_b)
            if ratio < 0.85:
                return 0.0

    # Guardrail 3: Mutually exclusive variant check (e.g. Brown Bread vs White Bread)
    raw_a = item_a.get("raw_name", "")
    raw_b = item_b.get("raw_name", "")
    if has_conflicting_variants(raw_a, raw_b):
        return 0.0

    # Guardrail 4: Core title similarity
    name_a = item_a.get("cleaned_name", "")
    name_b = item_b.get("cleaned_name", "")
    
    if not name_a or not name_b:
        # If both cleaned titles are empty but brand and quantities match exactly
        if brand_a and brand_b and brand_a == brand_b and val_a and val_b and val_a == val_b:
            return 0.85
        return 0.0

    # Sequence matcher ratio
    seq_ratio = SequenceMatcher(None, name_a, name_b).ratio()

    # Token overlap (Blends Jaccard union with Containment/Overlap coefficient for descriptive titles)
    tokens_a = set(name_a.split())
    tokens_b = set(name_b.split())
    if tokens_a and tokens_b:
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        overlap = len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))
        token_ratio = (jaccard * 0.35) + (overlap * 0.65)
    else:
        token_ratio = 0.0

    # Weighted combined score
    combined = (seq_ratio * 0.35) + (token_ratio * 0.65)

    # Boost if brand matches exactly
    if brand_a and brand_b and brand_a == brand_b:
        combined = min(1.0, combined + 0.10)

    # If query specified target quantity and both items match it, boost confidence
    if query_info and query_info.get("qty_info", {}).get("value"):
        target_val = query_info["qty_info"]["value"]
        if val_a and val_b and abs(val_a - target_val) < 1.0 and abs(val_b - target_val) < 1.0:
            combined = min(1.0, combined + 0.05)

    return round(combined, 3)


def prepare_product(raw_item: Dict[str, Any], query_brand: Optional[str] = None) -> Dict[str, Any]:
    """Enrich raw scraped product with parsed attributes."""
    store = raw_item.get("store", "Unknown")
    name = raw_item.get("name", "")
    price = parse_price(raw_item.get("price"))
    qty_str = raw_item.get("quantity", "")
    image_url = raw_item.get("image_url") or ""

    # If quantity is not separately provided, search in product name
    qty_info = parse_quantity(qty_str)
    if qty_info["value"] is None:
        qty_info = parse_quantity(name)

    brand = extract_brand(name, query_brand)
    cleaned = clean_title(name, brand)

    # Calculate unit price based on base unit (per 100ml, per 100g, or per piece)
    unit_price = None
    if price and qty_info["value"] and qty_info["value"] > 0:
        val = qty_info["value"]
        if qty_info["unit"] in ["ml", "g"]:
            unit_price = round((price / val) * 100.0, 2)
        elif qty_info["unit"] == "pcs":
            unit_price = round(price / val, 2)

    return {
        "store": store,
        "raw_name": name,
        "price": price,
        "quantity_str": qty_info.get("display") or qty_str,
        "qty_info": qty_info,
        "brand": brand,
        "cleaned_name": cleaned,
        "unit_price": unit_price,
        "image_url": image_url
    }


def cluster_products(
    blinkit_items: List[Dict[str, Any]],
    zepto_items: List[Dict[str, Any]],
    amazon_items: List[Dict[str, Any]],
    query: Optional[str] = None,
    similarity_threshold: float = 0.65,
    extra_terms: Optional[set] = None
) -> Dict[str, Any]:
    """
    Groups products across Blinkit, Zepto, and Amazon Fresh driven by the search query.
    1. Filters out off-topic / sponsored items using query relevance.
    2. Clusters true equivalent products across stores.
    3. Calculates best deals and cross-store savings.
    """
    query_info = analyze_query(query, extra_terms) if query else None
    query_brand = query_info.get("brand") if query_info else None

    # 1. Prepare and normalize items
    def prepare_and_filter(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for raw in items:
            name = raw.get("name")
            if not name:
                continue
            # Apply query relevance filter if query was provided
            if query_info and not is_relevant_to_query(name, query_info):
                continue
            prepared = prepare_product(raw, query_brand)
            result.append(prepared)
        return result

    prepared_blinkit = prepare_and_filter(blinkit_items)
    prepared_zepto = prepare_and_filter(zepto_items)
    prepared_amazon = prepare_and_filter(amazon_items)

    all_items = prepared_blinkit + prepared_zepto + prepared_amazon

    # 2. Cluster items across stores
    clusters: List[Dict[str, Any]] = []

    for item in all_items:
        store = item["store"]
        best_cluster = None
        best_score = 0.0

        for cluster in clusters:
            # A cluster can only hold one product per store
            if store in cluster["stores"]:
                continue

            # Compare against the cluster's representative product
            rep = cluster["representative"]
            score = calculate_similarity(item, rep, query_info)

            # Adaptive threshold: if both items share the exact same brand and normalized quantity,
            # allow a slightly lower title threshold (0.58 instead of 0.65)
            effective_threshold = similarity_threshold
            item_qty = item.get("qty_info", {}).get("value")
            rep_qty = rep.get("qty_info", {}).get("value")
            if (
                item.get("brand") and rep.get("brand")
                and item["brand"] == rep["brand"]
                and item_qty and rep_qty and abs(item_qty - rep_qty) < 1.0
            ):
                effective_threshold = 0.58

            if score >= effective_threshold and score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster:
            best_cluster["stores"][store] = item
            best_cluster["items"].append(item)
        else:
            # Create a new cluster
            display_brand = (item["brand"] or "").capitalize()
            disp_name = item["raw_name"].strip()
            clusters.append({
                "canonical_name": disp_name,
                "brand": display_brand,
                "quantity": item["quantity_str"],
                "representative": item,
                "stores": {store: item},
                "items": [item]
            })

    # 3. Analyze prices & determine winners for each cluster
    matched_deals = []
    single_store_items = []

    for cluster in clusters:
        stores_data = cluster["stores"]
        prices = {}
        images = {}
        quantities = {}

        for store_name, prod in stores_data.items():
            if prod["price"] is not None:
                prices[store_name] = prod["price"]
            if prod.get("image_url"):
                images[store_name] = prod["image_url"]
            if prod.get("quantity_str"):
                quantities[store_name] = prod["quantity_str"]

        if not prices:
            continue

        valid_prices = list(prices.values())
        min_price = min(valid_prices)
        max_price = max(valid_prices)
        savings = round(max_price - min_price, 2)
        savings_pct = round((savings / max_price) * 100, 1) if max_price > 0 else 0.0

        # Stores that offer the lowest price
        cheapest_stores = [s for s, p in prices.items() if p == min_price]

        # Representative image
        rep_image = next((url for url in images.values() if url), "")

        deal_data = {
            "canonical_name": cluster["canonical_name"],
            "brand": cluster["brand"],
            "quantity": cluster["quantity"],
            "prices": prices,
            "images": images,
            "representative_image": rep_image,
            "lowest_price": min_price,
            "highest_price": max_price,
            "savings": savings,
            "savings_percentage": savings_pct,
            "cheapest_store": cheapest_stores[0] if len(cheapest_stores) == 1 else "Tie",
            "cheapest_stores": cheapest_stores,
            "store_count": len(prices),
            "store_details": {
                s: {
                    "raw_name": prod["raw_name"],
                    "price": prod["price"],
                    "quantity": prod["quantity_str"],
                    "unit_price": prod["unit_price"],
                    "image_url": prod["image_url"]
                }
                for s, prod in stores_data.items()
            }
        }

        # If present in 2 or 3 stores, it's a multi-store deal
        if len(prices) >= 2:
            matched_deals.append(deal_data)
        else:
            single_store_items.append(deal_data)

    # Sort matched deals by savings descending (best deals first)
    matched_deals.sort(key=lambda x: (x["savings"], x["savings_percentage"]), reverse=True)

    return {
        "matched_deals": matched_deals,
        "single_store_items": single_store_items,
        "summary": {
            "total_matched": len(matched_deals),
            "total_single_store": len(single_store_items),
            "total_products": len(matched_deals) + len(single_store_items)
        }
    }
