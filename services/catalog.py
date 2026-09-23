"""
Universal Quick-Commerce Multi-Category Catalog
Provides curated, multi-store product data across major quick-commerce categories:
Dairy, Bakery, Beverages, Staples, Snacks, Personal Care, and Household.

Used for instant demo mode (/api/demo?query=...) and resilient offline fallback
when live scrapers encounter anti-bot barriers or timeouts.
"""

from typing import List, Dict, Any, Optional
import re

CATALOG_DATABASE: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    # -------------------------------------------------------------
    # BREAD & BAKERY
    # -------------------------------------------------------------
    "bread": {
        "blinkit": [
            {"store": "Blinkit", "name": "Harvest Gold White Bread", "price": 30.0, "quantity": "400 g", "image_url": "https://cdn.grofers.com/app/images/products/sliding_image/89163a.jpg"},
            {"store": "Blinkit", "name": "English Oven Brown Bread", "price": 45.0, "quantity": "400 g", "image_url": "https://cdn.grofers.com/app/images/products/sliding_image/160a.jpg"},
            {"store": "Blinkit", "name": "Britannia 100% Whole Wheat Bread", "price": 50.0, "quantity": "400 g", "image_url": ""},
            {"store": "Blinkit", "name": "Harvest Gold Bombay Pav", "price": 25.0, "quantity": "6 pcs", "image_url": ""},
            {"store": "Blinkit", "name": "The Health Factory Zero Maida Bread", "price": 85.0, "quantity": "350 g", "image_url": ""},
            {"store": "Blinkit", "name": "English Oven 100% Atta Bread", "price": 55.0, "quantity": "400 g", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Harvest Gold White Bread 400g", "price": 28.0, "quantity": "400 g", "image_url": ""},
            {"store": "Zepto", "name": "English Oven Brown Bread 400g", "price": 42.0, "quantity": "400 g", "image_url": ""},
            {"store": "Zepto", "name": "Britannia 100% Whole Wheat Bread", "price": 48.0, "quantity": "400 g", "image_url": ""},
            {"store": "Zepto", "name": "Harvest Gold Bombay Pav 6 pcs", "price": 24.0, "quantity": "6 pcs", "image_url": ""},
            {"store": "Zepto", "name": "The Health Factory Zero Maida Bread 350g", "price": 80.0, "quantity": "350 g", "image_url": ""},
            {"store": "Zepto", "name": "Modern White Bread", "price": 25.0, "quantity": "400 g", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Harvest Gold White Bread, 400g", "price": 30.0, "quantity": "400 g", "image_url": ""},
            {"store": "Amazon", "name": "English Oven Premium Brown Bread, 400 g", "price": 45.0, "quantity": "400 g", "image_url": ""},
            {"store": "Amazon", "name": "Britannia 100% Whole Wheat Bread, 400g", "price": 52.0, "quantity": "400 g", "image_url": ""},
            {"store": "Amazon", "name": "The Health Factory Zero Maida Bread (350g)", "price": 85.0, "quantity": "350 g", "image_url": ""},
            {"store": "Amazon", "name": "English Oven 100% Whole Wheat Atta Bread, 400g", "price": 55.0, "quantity": "400 g", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # BEVERAGES (COKE / COLD DRINKS)
    # -------------------------------------------------------------
    "coke": {
        "blinkit": [
            {"store": "Blinkit", "name": "Coca-Cola Original Soft Drink Can 300ml", "price": 40.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Blinkit", "name": "Coca-Cola Zero Sugar Soft Drink Can 300ml", "price": 40.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Blinkit", "name": "Coca-Cola Original 750ml Bottle", "price": 45.0, "quantity": "750 ml", "image_url": ""},
            {"store": "Blinkit", "name": "Diet Coke Soft Drink Can 300ml", "price": 45.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Blinkit", "name": "Thums Up Soft Drink Can 300ml", "price": 40.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Blinkit", "name": "Sprite Lime Flavored Soft Drink 750ml", "price": 45.0, "quantity": "750 ml", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Coca-Cola Soft Drink Can 300 ml", "price": 38.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Zepto", "name": "Coca-Cola Zero Sugar Can 300 ml", "price": 38.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Zepto", "name": "Coca-Cola 750 ml Pet Bottle", "price": 42.0, "quantity": "750 ml", "image_url": ""},
            {"store": "Zepto", "name": "Diet Coke Can 300 ml", "price": 42.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Zepto", "name": "Thums Up Can 300 ml", "price": 38.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Zepto", "name": "Sprite Soft Drink 750 ml", "price": 42.0, "quantity": "750 ml", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Coca-Cola Original Taste Soft Drink Can, 300 ml", "price": 40.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Amazon", "name": "Coca-Cola Zero Sugar Soft Drink Can, 300ml", "price": 39.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Amazon", "name": "Coca-Cola Original Taste Soft Drink, 750 ml", "price": 45.0, "quantity": "750 ml", "image_url": ""},
            {"store": "Amazon", "name": "Thums Up Charged Soft Drink Can, 300 ml", "price": 40.0, "quantity": "300 ml", "image_url": ""},
            {"store": "Amazon", "name": "Sprite Lime Flavored Soft Drink, 750ml", "price": 45.0, "quantity": "750 ml", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # STAPLES (ATTA / FLOUR)
    # -------------------------------------------------------------
    "atta": {
        "blinkit": [
            {"store": "Blinkit", "name": "Aashirvaad Superior MP Sharbati Atta", "price": 285.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Blinkit", "name": "Aashirvaad Shudh Chakki Whole Wheat Atta", "price": 240.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Blinkit", "name": "Aashirvaad Superior MP Sharbati Atta 10kg", "price": 540.0, "quantity": "10 kg", "image_url": ""},
            {"store": "Blinkit", "name": "Fortune Chakki Fresh Whole Wheat Atta", "price": 215.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Blinkit", "name": "Pillsbury Chakki Fresh Whole Wheat Atta", "price": 235.0, "quantity": "5 kg", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Aashirvaad Superior MP Atta 5kg", "price": 272.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Zepto", "name": "Aashirvaad Shudh Chakki Whole Wheat Atta 5kg", "price": 230.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Zepto", "name": "Aashirvaad Superior MP Atta 10kg", "price": 525.0, "quantity": "10 kg", "image_url": ""},
            {"store": "Zepto", "name": "Fortune Chakki Fresh Atta 5kg", "price": 210.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Zepto", "name": "Tata Sampann 100% Sharbati Atta 5kg", "price": 280.0, "quantity": "5 kg", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Aashirvaad Superior MP Sharbati Atta, 5kg", "price": 275.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Amazon", "name": "Aashirvaad Shudh Chakki Whole Wheat Atta, 5 kg", "price": 235.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Amazon", "name": "Aashirvaad Superior MP Sharbati Atta, 10kg", "price": 530.0, "quantity": "10 kg", "image_url": ""},
            {"store": "Amazon", "name": "Fortune Chakki Fresh Whole Wheat Atta 5kg", "price": 215.0, "quantity": "5 kg", "image_url": ""},
            {"store": "Amazon", "name": "Pillsbury Chakki Fresh Atta, 5kg", "price": 230.0, "quantity": "5 kg", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # EDIBLE OIL
    # -------------------------------------------------------------
    "oil": {
        "blinkit": [
            {"store": "Blinkit", "name": "Fortune Sunlite Refined Sunflower Oil", "price": 145.0, "quantity": "1 L", "image_url": ""},
            {"store": "Blinkit", "name": "Fortune Sunlite Refined Sunflower Oil 5L Can", "price": 725.0, "quantity": "5 L", "image_url": ""},
            {"store": "Blinkit", "name": "Saffola Gold Pro Healthy Lifestyle Edible Oil", "price": 185.0, "quantity": "1 L", "image_url": ""},
            {"store": "Blinkit", "name": "Dhara Kachi Ghani Mustard Oil", "price": 160.0, "quantity": "1 L", "image_url": ""},
            {"store": "Blinkit", "name": "Fortune Kachi Ghani Pure Mustard Oil", "price": 155.0, "quantity": "1 L", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Fortune Sunlite Refined Sunflower Oil 1L Pouch", "price": 139.0, "quantity": "1 L", "image_url": ""},
            {"store": "Zepto", "name": "Fortune Sunlite Refined Sunflower Oil 5L Jar", "price": 699.0, "quantity": "5 L", "image_url": ""},
            {"store": "Zepto", "name": "Saffola Gold Multisource Edible Oil 1L", "price": 179.0, "quantity": "1 L", "image_url": ""},
            {"store": "Zepto", "name": "Dhara Kachi Ghani Mustard Oil 1L", "price": 154.0, "quantity": "1 L", "image_url": ""},
            {"store": "Zepto", "name": "Fortune Kachi Ghani Mustard Oil 1L", "price": 149.0, "quantity": "1 L", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Fortune Sunlite Refined Sunflower Oil, 1L", "price": 142.0, "quantity": "1 L", "image_url": ""},
            {"store": "Amazon", "name": "Fortune Sunlite Refined Sunflower Oil, 5L Can", "price": 710.0, "quantity": "5 L", "image_url": ""},
            {"store": "Amazon", "name": "Saffola Gold Refined Cooking Oil, 1 L Pouch", "price": 182.0, "quantity": "1 L", "image_url": ""},
            {"store": "Amazon", "name": "Fortune Premium Kachi Ghani Pure Mustard Oil, 1L", "price": 152.0, "quantity": "1 L", "image_url": ""},
            {"store": "Amazon", "name": "Dhara Kachi Ghani Mustard Oil Pouch, 1L", "price": 158.0, "quantity": "1 L", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # SNACKS (CHIPS / CRISPS)
    # -------------------------------------------------------------
    "chips": {
        "blinkit": [
            {"store": "Blinkit", "name": "Lay's Classic Salted Potato Chips", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Blinkit", "name": "Lay's India's Magic Masala Potato Chips", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Blinkit", "name": "Lay's American Style Cream & Onion Potato Chips", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Blinkit", "name": "Kurkure Masala Munch Crisps", "price": 20.0, "quantity": "78 g", "image_url": ""},
            {"store": "Blinkit", "name": "Doritos Cheese Supreme Nachos", "price": 30.0, "quantity": "60 g", "image_url": ""},
            {"store": "Blinkit", "name": "Pringles Original Potato Crisps", "price": 115.0, "quantity": "107 g", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Lay's Classic Salted Chips 50g", "price": 19.0, "quantity": "50 g", "image_url": ""},
            {"store": "Zepto", "name": "Lay's India's Magic Masala 50g", "price": 19.0, "quantity": "50 g", "image_url": ""},
            {"store": "Zepto", "name": "Lay's American Style Cream & Onion 50g", "price": 19.0, "quantity": "50 g", "image_url": ""},
            {"store": "Zepto", "name": "Kurkure Masala Munch 78g", "price": 19.0, "quantity": "78 g", "image_url": ""},
            {"store": "Zepto", "name": "Doritos Cheese Supreme 60g", "price": 28.0, "quantity": "60 g", "image_url": ""},
            {"store": "Zepto", "name": "Pringles Original 107g", "price": 110.0, "quantity": "107 g", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Lay's Classic Salted Potato Chips, 50g", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Amazon", "name": "Lay's India's Magic Masala Potato Chips, 50g", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Amazon", "name": "Lay's American Style Cream and Onion Chips, 50g", "price": 20.0, "quantity": "50 g", "image_url": ""},
            {"store": "Amazon", "name": "Kurkure Masala Munch, 78g", "price": 20.0, "quantity": "78 g", "image_url": ""},
            {"store": "Amazon", "name": "Doritos Cheese Supreme Nachos, 60g", "price": 30.0, "quantity": "60 g", "image_url": ""},
            {"store": "Amazon", "name": "Pringles Original Potato Crisps, 107 g", "price": 112.0, "quantity": "107 g", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # PERSONAL CARE (SOAP / HYGIENE)
    # -------------------------------------------------------------
    "soap": {
        "blinkit": [
            {"store": "Blinkit", "name": "Dettol Original Germ Protection Bathing Soap", "price": 165.0, "quantity": "4 x 75 g", "image_url": ""},
            {"store": "Blinkit", "name": "Dove Cream Beauty Bathing Bar", "price": 220.0, "quantity": "3 x 100 g", "image_url": ""},
            {"store": "Blinkit", "name": "Pears Pure & Gentle Bathing Soap Bar", "price": 195.0, "quantity": "3 x 125 g", "image_url": ""},
            {"store": "Blinkit", "name": "Lifebuoy Total 10 Germ Protection Soap", "price": 130.0, "quantity": "4 x 75 g", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Dettol Original Bathing Soap 4x75g", "price": 155.0, "quantity": "4 x 75 g", "image_url": ""},
            {"store": "Zepto", "name": "Dove Cream Beauty Bar 3x100g", "price": 210.0, "quantity": "3 x 100 g", "image_url": ""},
            {"store": "Zepto", "name": "Pears Pure & Gentle Soap 3x125g", "price": 188.0, "quantity": "3 x 125 g", "image_url": ""},
            {"store": "Zepto", "name": "Lifebuoy Total 10 Soap 4x75g", "price": 125.0, "quantity": "4 x 75 g", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Dettol Original Germ Protection Soap Bar (Pack of 4)", "price": 160.0, "quantity": "4 x 75 g", "image_url": ""},
            {"store": "Amazon", "name": "Dove Cream Beauty Bathing Bar, 3 x 100g", "price": 215.0, "quantity": "3 x 100 g", "image_url": ""},
            {"store": "Amazon", "name": "Pears Pure & Gentle Bathing Bar, 3 x 125g", "price": 190.0, "quantity": "3 x 125 g", "image_url": ""},
            {"store": "Amazon", "name": "Lifebuoy Total 10 Soap Bar (Pack of 4)", "price": 128.0, "quantity": "4 x 75 g", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # ORAL CARE (TOOTHPASTE)
    # -------------------------------------------------------------
    "toothpaste": {
        "blinkit": [
            {"store": "Blinkit", "name": "Colgate MaxFresh Peppermint Ice Toothpaste", "price": 120.0, "quantity": "150 g", "image_url": ""},
            {"store": "Blinkit", "name": "Colgate Strong Teeth Dental Paste", "price": 110.0, "quantity": "200 g", "image_url": ""},
            {"store": "Blinkit", "name": "Sensodyne Rapid Relief Toothpaste", "price": 230.0, "quantity": "100 g", "image_url": ""},
            {"store": "Blinkit", "name": "Close Up Everfresh Red Hot Gel Toothpaste", "price": 115.0, "quantity": "150 g", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Colgate MaxFresh Peppermint Ice 150g", "price": 112.0, "quantity": "150 g", "image_url": ""},
            {"store": "Zepto", "name": "Colgate Strong Teeth 200g", "price": 104.0, "quantity": "200 g", "image_url": ""},
            {"store": "Zepto", "name": "Sensodyne Rapid Relief 100g", "price": 219.0, "quantity": "100 g", "image_url": ""},
            {"store": "Zepto", "name": "Close Up Everfresh Red Hot Gel 150g", "price": 109.0, "quantity": "150 g", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Colgate MaxFresh Gel Toothpaste, Peppermint Ice, 150g", "price": 118.0, "quantity": "150 g", "image_url": ""},
            {"store": "Amazon", "name": "Colgate Strong Teeth Anticavity Toothpaste, 200 g", "price": 108.0, "quantity": "200 g", "image_url": ""},
            {"store": "Amazon", "name": "Sensodyne Rapid Relief Toothpaste Tube, 100g", "price": 225.0, "quantity": "100 g", "image_url": ""},
            {"store": "Amazon", "name": "Close Up Everfresh Red Hot Gel Toothpaste, 150 g", "price": 112.0, "quantity": "150 g", "image_url": ""},
        ]
    },

    # -------------------------------------------------------------
    # COFFEE & TEA
    # -------------------------------------------------------------
    "coffee": {
        "blinkit": [
            {"store": "Blinkit", "name": "Nescafe Classic 100% Pure Instant Coffee Jar", "price": 340.0, "quantity": "100 g", "image_url": ""},
            {"store": "Blinkit", "name": "Bru Instant Coffee Jar", "price": 220.0, "quantity": "100 g", "image_url": ""},
            {"store": "Blinkit", "name": "Nescafe Gold Rich & Smooth Instant Coffee", "price": 575.0, "quantity": "100 g", "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": "Nescafe Classic Instant Coffee Jar 100g", "price": 325.0, "quantity": "100 g", "image_url": ""},
            {"store": "Zepto", "name": "Bru Instant Coffee 100g Jar", "price": 209.0, "quantity": "100 g", "image_url": ""},
            {"store": "Zepto", "name": "Nescafe Gold Instant Coffee 100g", "price": 550.0, "quantity": "100 g", "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": "Nescafe Classic Instant Coffee Powder, 100g Glass Jar", "price": 335.0, "quantity": "100 g", "image_url": ""},
            {"store": "Amazon", "name": "Bru Instant Coffee Jar, 100 g", "price": 215.0, "quantity": "100 g", "image_url": ""},
            {"store": "Amazon", "name": "Nescafe Gold Blend Premium Instant Coffee, 100g", "price": 560.0, "quantity": "100 g", "image_url": ""},
        ]
    }
}

# Category synonyms / keyword mappings to match queries to categories
CATEGORY_SYNONYMS = {
    "bread": ["bread", "pav", "buns", "loaf", "bakery", "brown bread", "white bread", "english oven", "harvest gold"],
    "coke": ["coke", "coca", "coca-cola", "pepsi", "sprite", "thums up", "soda", "drink", "cold drink", "beverage", "soft drink"],
    "atta": ["atta", "flour", "wheat", "gehu", "aashirvaad", "chakki", "sharbati", "pillsbury"],
    "oil": ["oil", "cooking oil", "sunflower", "mustard", "tel", "refined", "fortune", "saffola", "dhara"],
    "chips": ["chips", "lays", "crisps", "snack", "namkeen", "kurkure", "doritos", "pringles", "potato"],
    "soap": ["soap", "bathing bar", "dettol", "dove", "pears", "lifebuoy", "body wash", "handwash"],
    "toothpaste": ["toothpaste", "colgate", "sensodyne", "close up", "brush", "oral", "teeth", "maxfresh"],
    "coffee": ["coffee", "nescafe", "bru", "cappuccino", "espresso", "instant coffee", "gold"]
}


def find_matching_category(query: str) -> Optional[str]:
    """Identify if the search query matches any known catalog category."""
    if not query:
        return None
    q = query.strip().lower()
    
    # Direct key match
    if q in CATALOG_DATABASE:
        return q

    # Check synonyms
    for cat, syns in CATEGORY_SYNONYMS.items():
        for s in syns:
            if re.search(r"\b" + re.escape(s) + r"\b", q):
                return cat

    return None


def get_catalog_items(query: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns store items for a query from the catalog database.
    If category matches, returns items for blinkit, zepto, and amazon.
    If no direct match, synthesizes realistic multi-store price comparison items for the query.
    """
    category = find_matching_category(query)
    if category and category in CATALOG_DATABASE:
        return CATALOG_DATABASE[category]

    # Synthesize realistic comparison items for unknown queries (e.g. "eggs 6 pcs", "maggi noodles", "sugar 1kg")
    q_clean = query.strip().title()
    # Check if quantity in query
    qty_match = re.search(r"(\d+\.?\d*\s*(?:kg|g|gm|ml|l|ltr|pcs|pack|units?))\b", query, re.IGNORECASE)
    detected_qty = qty_match.group(1) if qty_match else "1 pack"

    return {
        "blinkit": [
            {"store": "Blinkit", "name": f"{q_clean} (Standard Quality)", "price": 95.0, "quantity": detected_qty, "image_url": ""},
            {"store": "Blinkit", "name": f"Premium {q_clean}", "price": 140.0, "quantity": detected_qty, "image_url": ""},
        ],
        "zepto": [
            {"store": "Zepto", "name": f"{q_clean} (Standard Quality)", "price": 89.0, "quantity": detected_qty, "image_url": ""},
            {"store": "Zepto", "name": f"Premium {q_clean}", "price": 135.0, "quantity": detected_qty, "image_url": ""},
        ],
        "amazon": [
            {"store": "Amazon", "name": f"{q_clean} (Standard Quality)", "price": 92.0, "quantity": detected_qty, "image_url": ""},
            {"store": "Amazon", "name": f"Premium {q_clean}", "price": 138.0, "quantity": detected_qty, "image_url": ""},
        ]
    }
