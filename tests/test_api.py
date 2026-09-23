import os
import sys

# Ensure repository root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    print("[PASS] GET / returned 200 OK")


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "images" in data
    print("[PASS] GET /api/health returned 200 OK")


def test_demo():
    response = client.get("/api/demo")
    assert response.status_code == 200
    data = response.json()
    assert "matched_deals" in data
    assert "summary" in data
    assert data["summary"]["total_matched"] > 0

    matched = data["matched_deals"]
    print(f"[PASS] GET /api/demo returned {len(matched)} matched deals")

    first = matched[0]
    print(
        f"Top deal: {first['canonical_name']} -> Lowest: Rs. {first['lowest_price']} at {first['cheapest_store']} (Savings: Rs. {first['savings']})"
    )
    assert first["lowest_price"] <= first["highest_price"]
    assert first["savings"] >= 0


def test_web_ui():
    # 1. Test HTML served at /app
    response = client.get("/app")
    assert response.status_code == 200
    assert "QuickCompare" in response.text
    assert "text/html" in response.headers.get("content-type", "")
    print("[PASS] GET /app returned 200 OK with HTML content")

    # 2. Test CSS served at /static/style.css
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert "QuickCompare" in css_res.text
    print("[PASS] GET /static/style.css returned 200 OK")

    # 3. Test JS served at /static/app.js
    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "executeSearch" in js_res.text
    print("[PASS] GET /static/app.js returned 200 OK")


if __name__ == "__main__":
    test_root()
    test_health()
    test_demo()
    test_web_ui()
    print("\nALL API & WEB APPLICATION TESTS PASSED SUCCESSFULLY!")
