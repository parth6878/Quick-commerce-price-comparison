import pandas as pd
from services.matcher import cluster_products, analyze_query, is_relevant_to_query, parse_quantity, extract_brand

def test_milk_dataset_with_query_relevance():
    """Test milk dataset to ensure off-topic items (Namkeen, Bread) are filtered out and milk items match properly."""
    b_df = pd.read_csv(r"blinkit\blinkit_data.csv")
    z_df = pd.read_csv(r"zepto\zepto_data.csv")
    a_df = pd.read_csv(r"amazon\amazon_data.csv")

    b_items = [
        {"store": "Blinkit", "name": row["B_Product_name"], "price": row["B_Price"], "quantity": row["B_Quantity"]}
        for _, row in b_df.iterrows()
    ]
    z_items = [
        {"store": "Zepto", "name": row["Z_Product_name"], "price": row["Z_Price"], "quantity": row["Z_Quantity"]}
        for _, row in z_df.iterrows()
    ]
    a_items = [
        {"store": "Amazon", "name": row["A_Product_name"], "price": row["A_Price"], "quantity": row["A_Quantity"]}
        for _, row in a_df.iterrows()
    ]

    print("\n" + "=" * 80)
    print("TEST 1: Milk Query Relevance & Matching")
    print("=" * 80)

    # 1. Verify query relevance logic directly
    q_info = analyze_query("milk")
    assert not is_relevant_to_query("Let's Try Lite Multigrain Mixture Namkeen", q_info), "Namkeen must not match query 'milk'"
    assert not is_relevant_to_query("Harvest Gold White Bread", q_info), "Bread must not match query 'milk'"
    assert is_relevant_to_query("Amul Taaza Toned Milk", q_info), "Amul Milk must match query 'milk'"
    print("[PASS] Off-topic items (Namkeen, Bread) successfully flagged as irrelevant to 'milk'!")

    # 2. Run clustering with query="milk"
    result = cluster_products(b_items, z_items, a_items, query="milk")
    matched = result["matched_deals"]
    single = result["single_store_items"]

    print(f"Loaded: Blinkit={len(b_items)}, Zepto={len(z_items)}, Amazon={len(a_items)}")
    print(f"Matched Deals: {len(matched)} | Single Store Items: {len(single)}")

    for i, deal in enumerate(matched[:5], 1):
        stores_str = ", ".join([f"{s}: Rs. {p}" for s, p in deal["prices"].items()])
        print(f"[{i}] {deal['canonical_name']} ({deal['quantity']})")
        print(f"    Brand: {deal['brand']} | Stores: {stores_str}")
        print(f"    Cheapest: {deal['cheapest_store']} (Rs. {deal['lowest_price']}) | Savings: Rs. {deal['savings']}")

    # Assertions
    for deal in matched:
        # Check 1: No Namkeen or Bread in matched milk deals
        assert "namkeen" not in deal["canonical_name"].lower(), f"Namkeen leaked into milk deals: {deal['canonical_name']}"
        assert "bread" not in deal["canonical_name"].lower(), f"Bread leaked into milk deals: {deal['canonical_name']}"
        
        # Check 2: Zero cross-brand contamination
        brands_in_deal = set()
        for s, det in deal["store_details"].items():
            b = det.get("brand")
            if b:
                brands_in_deal.add(b)
        assert len(brands_in_deal) <= 1, f"Cross-brand contamination detected in {deal['canonical_name']}: {brands_in_deal}"

    print("[PASS] Zero cross-brand contamination and zero off-topic leakage in milk test!")


def test_bread_category():
    """Test general query matching for Bread category (Brown Bread vs White Bread vs Atta Bread)."""
    print("\n" + "=" * 80)
    print("TEST 2: Bread Category Matching (query='bread')")
    print("=" * 80)

    blinkit_items = [
        {"store": "Blinkit", "name": "Harvest Gold White Bread 400g", "price": 30, "quantity": "400 g"},
        {"store": "Blinkit", "name": "English Oven Brown Bread 400g", "price": 45, "quantity": "400 g"},
        {"store": "Blinkit", "name": "Britannia 100% Whole Wheat Atta Bread", "price": 50, "quantity": "400 g"},
        {"store": "Blinkit", "name": "Lays Classic Salted Potato Chips 50g", "price": 20, "quantity": "50 g"}  # Off-topic sponsored item
    ]
    zepto_items = [
        {"store": "Zepto", "name": "Harvest Gold White Bread (400g)", "price": 28, "quantity": "400g"},
        {"store": "Zepto", "name": "English Oven Brown Bread", "price": 44, "quantity": "400 g"},
        {"store": "Zepto", "name": "English Oven 100% Atta Bread", "price": 48, "quantity": "400 g"}
    ]
    amazon_items = [
        {"store": "Amazon", "name": "Harvest Gold - White Bread, 400 g", "price": 29, "quantity": "400 g"},
        {"store": "Amazon", "name": "English Oven Brown Bread 400 grams", "price": 45, "quantity": "400 g"}
    ]

    result = cluster_products(blinkit_items, zepto_items, amazon_items, query="bread")
    matched = result["matched_deals"]
    
    print(f"Found {len(matched)} matched bread deals:")
    for deal in matched:
        print(f" - {deal['canonical_name']} | Brand: {deal['brand']} | Stores: {list(deal['prices'].keys())}")

    # Assertions
    # 1. Lays chips must be filtered out by query="bread"
    all_deal_names = [d["canonical_name"].lower() for d in matched]
    all_single_names = [d["canonical_name"].lower() for d in result["single_store_items"]]
    assert not any("lays" in n for n in all_deal_names + all_single_names), "Lays chips must be filtered out for query 'bread'"

    # 2. Harvest Gold White Bread should match across 3 stores
    hg_deal = next((d for d in matched if "harvest gold" in d["canonical_name"].lower()), None)
    assert hg_deal is not None, "Harvest Gold White Bread should be matched"
    assert hg_deal["store_count"] == 3, f"Harvest Gold should be in 3 stores, got {hg_deal['store_count']}"

    # 3. English Oven Brown Bread should match across 3 stores
    eo_deal = next((d for d in matched if "english oven" in d["canonical_name"].lower() and "brown" in d["canonical_name"].lower()), None)
    assert eo_deal is not None, "English Oven Brown Bread should be matched"
    assert eo_deal["store_count"] == 3

    # 4. Britannia and English Oven should never merge
    for deal in matched:
        brands = [d["brand"] for d in deal["store_details"].values() if d.get("brand")]
        assert len(set(brands)) <= 1

    print("[PASS] Bread category matching successfully passed!")


def test_beverages_variants():
    """Test beverages matching distinguishing Coca-Cola Classic vs Coke Zero and pack sizes."""
    print("\n" + "=" * 80)
    print("TEST 3: Beverages / Soft Drinks Category (query='coke')")
    print("=" * 80)

    blinkit_items = [
        {"store": "Blinkit", "name": "Coca-Cola Original Taste Soft Drink Can 300ml", "price": 40, "quantity": "300 ml"},
        {"store": "Blinkit", "name": "Coca-Cola Zero Sugar Soft Drink Can 300ml", "price": 40, "quantity": "300 ml"},
        {"store": "Blinkit", "name": "Coca-Cola Original 750ml Bottle", "price": 45, "quantity": "750 ml"},
        {"store": "Blinkit", "name": "Pepsi Can 300ml", "price": 40, "quantity": "300 ml"}
    ]
    zepto_items = [
        {"store": "Zepto", "name": "Coke Soft Drink Can 300 ml", "price": 38, "quantity": "300 ml"},
        {"store": "Zepto", "name": "Coke Zero Sugar Can (300 ml)", "price": 39, "quantity": "300 ml"},
        {"store": "Zepto", "name": "Coca-Cola 750 ml Pet Bottle", "price": 42, "quantity": "750 ml"}
    ]
    amazon_items = [
        {"store": "Amazon", "name": "Coca-Cola - Soft Drink, 300 ml Can", "price": 37, "quantity": "300 ml"},
        {"store": "Amazon", "name": "Coca-Cola Zero Sugar Can, 300ml", "price": 38, "quantity": "300 ml"}
    ]

    result = cluster_products(blinkit_items, zepto_items, amazon_items, query="coke")
    matched = result["matched_deals"]

    print(f"Found {len(matched)} matched Coke deals:")
    for deal in matched:
        print(f" - {deal['canonical_name']} ({deal['quantity']}) | Stores: {deal['store_count']}")

    # Assertions
    # 1. Coke Zero and Classic Coke MUST NOT match together
    for deal in matched:
        raw_names = [d["raw_name"].lower() for d in deal["store_details"].values()]
        has_zero = any("zero" in rn for rn in raw_names)
        has_original = any("original" in rn or "classic" in rn for rn in raw_names)
        assert not (has_zero and has_original), f"Coke Zero and Classic Coke incorrectly merged in {deal['canonical_name']}!"

    # 2. 300ml and 750ml MUST NOT match together
    for deal in matched:
        sizes = [d["quantity"] for d in deal["store_details"].values()]
        assert not ("300 ml" in sizes and "750 ml" in sizes), "300ml and 750ml merged!"

    # 3. Pepsi should never merge with Coke
    for deal in matched:
        brands = [d["brand"] for d in deal["store_details"].values() if d.get("brand")]
        assert "pepsi" not in brands or len(deal["store_details"]) == 1

    print("[PASS] Beverage variant isolation (Zero Sugar vs Classic & 300ml vs 750ml) passed!")


def test_staples_and_units():
    """Test staples with kg and multi-pack parsing (Atta, Oil)."""
    print("\n" + "=" * 80)
    print("TEST 4: Staples & Unit Conversion (Atta 5kg vs 10kg, Oil 1L vs 5L)")
    print("=" * 80)

    # Validate unit parser for counts, multi-packs, grams, kg
    p1 = parse_quantity("5 kg")
    assert p1["value"] == 5000.0 and p1["unit"] == "g"

    p2 = parse_quantity("2 x 500 ml")
    assert p2["value"] == 1000.0 and p2["unit"] == "ml"

    p3 = parse_quantity("4 pcs")
    assert p3["value"] == 4.0 and p3["unit"] == "pcs"

    blinkit_items = [
        {"store": "Blinkit", "name": "Aashirvaad Superior MP Whole Wheat Sharbati Atta 5kg", "price": 280, "quantity": "5 kg"},
        {"store": "Blinkit", "name": "Fortune Sunlite Refined Sunflower Oil 1L Pouch", "price": 140, "quantity": "1 L"}
    ]
    zepto_items = [
        {"store": "Zepto", "name": "Aashirvaad Sharbati Atta (5 kg)", "price": 275, "quantity": "5 kg"},
        {"store": "Zepto", "name": "Fortune Refined Sunflower Oil 1L", "price": 138, "quantity": "1 L"}
    ]

    result = cluster_products(blinkit_items, zepto_items, [], query="atta")
    matched = result["matched_deals"]
    assert len(matched) == 1, "Only Atta should be matched when query='atta'"
    assert "aashirvaad" in matched[0]["canonical_name"].lower()
    assert matched[0]["cheapest_store"] == "Zepto"
    assert matched[0]["savings"] == 5.0

    print("[PASS] Staples and multi-unit parsing passed!")


if __name__ == "__main__":
    test_milk_dataset_with_query_relevance()
    test_bread_category()
    test_beverages_variants()
    test_staples_and_units()
    print("\n" + "=" * 80)
    print("ALL GENERAL QUERY-DRIVEN MATCHER TESTS PASSED PERFECTLY!")
    print("=" * 80)
