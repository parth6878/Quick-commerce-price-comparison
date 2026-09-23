"""
Persistent local store of real product photos scraped from the quick-commerce
sites (Blinkit / Zepto / Amazon Fresh).

Why local files instead of hot-linking:
  * store CDNs block hot-linking / expire signed URLs (we saw 403s already)
  * serving from /static/img is instant and works offline
  * the UI keeps a generated-SVG fallback only for genuinely unknown products

Layout:
  static/img/<sha1(image_url)>.<jpg|png>   <- downloaded, resized photos
  data/image_index.json                    <- name -> file mapping + provenance

Lookup resolution order used by the app (see app._with_images):
  1. lookup(store, name)       exact / fuzzy match for that store
  2. the item's own remote image_url (fresh live scrape) is kept as-is
  3. lookup_any(name)          same product photo from ANOTHER store
  4. lookup_query(query, name) any photo scraped for this query
  5. generated SVG placeholder

Cross-process note: seeding runs in a separate process (seed_images.py) from
the uvicorn app, so the index file's mtime is re-checked on every lookup and
writes merge with whatever landed on disk since we last read it.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Set

import requests

try:  # matcher pulls in variant conflict rules (Zero vs Regular, 500ml vs 1L ...)
    from services.matcher import has_conflicting_variants
except Exception:  # pragma: no cover - flat-module import
    try:
        from matcher import has_conflicting_variants
    except Exception:
        def has_conflicting_variants(title_a: str, title_b: str) -> bool:
            return False

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(_ROOT_DIR, "static", "img")
INDEX_PATH = os.path.join(_ROOT_DIR, "data", "image_index.json")

MAX_EDGE = 640          # longest side after resize (cards render ~320-400 px)
JPEG_QUALITY = 85
MIN_IMAGE_BYTES = 1500  # smaller than this is an icon/spacer, not a product photo
MIN_EDGE = 80           # reject 16x16 favicons etc.

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

REFERERS = {
    "blinkit": "https://blinkit.com/",
    "zepto": "https://www.zeptonow.com/",
    "amazon": "https://www.amazon.in/",
}

_STORE_NAME_TO_KEY = {
    "blinkit": "blinkit",
    "zepto": "zepto",
    "amazon": "amazon",
    "amazon fresh": "amazon",
    "amazonfresh": "amazon",
}

# Generic tokens dropped from BOTH sides of every comparison so synthetic
# catalogue rows ("Premium X (Standard Quality)") match real scraped titles.
_STOP_TOKENS = {"standard", "quality", "premium", "pack"}

# matched-name thresholds (jaccard over normalised tokens)
SAME_STORE_MIN_SCORE = 0.60
ANY_STORE_MIN_SCORE = 0.60
QUERY_POOL_MIN_SCORE = 0.50

_JUNK_URL_PARTS = (
    "logo", "icon", "sprite", "banner", "placeholder", "not-found",
    "arrow", "favicon", "category", ".svg",
)

_lock = threading.RLock()
_index: Optional[Dict[str, Any]] = None
_index_mtime: int = -1


def store_key(store: Any) -> str:
    """'Amazon Fresh' -> 'amazon'."""
    text = str(store or "").strip().lower()
    return _STORE_NAME_TO_KEY.get(text, re.sub(r"[^a-z]", "", text))


def normalize(name: Any) -> str:
    """
    Normalise a product title for matching:
      'Amul Taaza Toned Milk 500 ml' -> 'amul taaza toned milk 500'
      (case, punctuation, stop words and single-letter unit tokens folded away)
    """
    text = str(name or "").replace("\u20b9", " ").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [
        t for t in text.split()
        if (len(t) >= 2 or t.isdigit()) and t not in _STOP_TOKENS
    ]
    return " ".join(tokens)


def _tokens(norm: str) -> Set[str]:
    return set(norm.split())


def score(norm_a: str, norm_b: str) -> float:
    a, b = _tokens(norm_a), _tokens(norm_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Index IO (mtime-based reload + merge-on-save for cross-process safety)
# ---------------------------------------------------------------------------

def _empty_index() -> Dict[str, Any]:
    return {"version": 1, "entries": {}, "by_query": {}}


def _read_disk() -> Optional[Dict[str, Any]]:
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            data.setdefault("by_query", {})
            return data
    except Exception:
        return None
    return None


def _merge_into(ours: Dict[str, Any], theirs: Dict[str, Any]) -> None:
    """Union two indexes; our entries win on key collisions (ours are newer)."""
    ours["entries"] = {**theirs.get("entries", {}), **ours.get("entries", {})}
    merged_query: Dict[str, List[str]] = {}
    for source in (theirs.get("by_query", {}), ours.get("by_query", {})):
        for q_key, keys in source.items():
            bucket = merged_query.setdefault(q_key, [])
            for entry_key in keys:
                if entry_key not in bucket:
                    bucket.append(entry_key)
    ours["by_query"] = merged_query


def _ensure_loaded() -> Dict[str, Any]:
    """Load the index; re-read it whenever another process rewrote the file."""
    global _index, _index_mtime
    with _lock:
        try:
            mtime = os.path.getmtime(INDEX_PATH)
        except OSError:
            mtime = -1

        if _index is None:
            disk = _read_disk() if mtime != -1 else None
            _index = disk if disk is not None else _empty_index()
            _index_mtime = mtime
        elif mtime != _index_mtime:
            disk = _read_disk()
            if disk is not None:
                _merge_into(_index, disk)
            _index_mtime = mtime
    return _index


def _save() -> None:
    """Absorb concurrent writes, then atomically replace the index file."""
    global _index, _index_mtime
    with _lock:
        if _index is None:
            return
        try:
            disk_mtime = os.path.getmtime(INDEX_PATH)
        except OSError:
            disk_mtime = -1
        if disk_mtime != _index_mtime and disk_mtime != -1:
            disk = _read_disk()
            if disk is not None:
                _merge_into(_index, disk)

        try:
            os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
            # Unique tmp per process avoids two processes fighting over one
            # temp file; retry absorbs the destination being momentarily
            # locked by a reader in another process (WinError 5).
            tmp_path = f"{INDEX_PATH}.{os.getpid()}.tmp"
            last_error: Optional[Exception] = None
            for attempt in range(4):
                try:
                    with open(tmp_path, "w", encoding="utf-8") as fh:
                        json.dump(_index, fh, ensure_ascii=False, indent=0, sort_keys=True)
                    os.replace(tmp_path, INDEX_PATH)
                    last_error = None
                    break
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.12 * (attempt + 1))
            if last_error is not None:
                raise last_error
            _index_mtime = os.path.getmtime(INDEX_PATH)
        except Exception as exc:
            print(f"[IMAGE STORE] index save failed: {exc}")


def _url_for(entry: Dict[str, Any]) -> str:
    return f"/static/img/{entry.get('file', '')}"


# ---------------------------------------------------------------------------
# Download + store
# ---------------------------------------------------------------------------

def _download(url: str, referer: str = "") -> Optional[bytes]:
    headers = {
        "User-Agent": USER_AGENT,
        # NOTE: do NOT advertise avif - cdn-cgi would serve AVIF and this
        # Pillow build cannot decode it (Blinkit ingest silently hit 0 that way).
        "Accept": "image/png,image/jpeg,image/webp,image/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return None
        content_type = str(resp.headers.get("content-type", "")).lower()
        if content_type and not (content_type.startswith("image") or "octet-stream" in content_type):
            return None
        data = resp.content
    except Exception:
        return None
    if len(data) < MIN_IMAGE_BYTES:
        return None
    return data


_MAGIC_EXTS = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
)


def _raw_ext(data: bytes) -> str:
    """Extension by magic bytes when Pillow can't decode (codec gaps, AVIF...)."""
    for magic, ext in _MAGIC_EXTS:
        if data.startswith(magic):
            return ext
    if data[:4] == b"GIF8":
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) >= 12 and data[4:12].startswith(b"ftypav"):
        return ".avif"
    return ""


def _normalise_bytes(data: bytes) -> Optional[bytes]:
    """Resize/convert a downloaded photo so static/img stays small and uniform."""
    if Image is None:
        return data
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    try:
        if min(img.size) < MIN_EDGE:
            return None
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if img.width > MAX_EDGE or img.height > MAX_EDGE:
            img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        out = io.BytesIO()
        if has_alpha:
            img.convert("RGBA").save(out, format="PNG", optimize=True)
            return out.getvalue()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()
    except Exception:
        return None


def _looks_like_product_url(url: str) -> bool:
    lowered = str(url or "").lower()
    if not lowered.startswith("http"):
        return False
    return not any(part in lowered for part in _JUNK_URL_PARTS)


def add_from_url(
    store: Any,
    name: str,
    url: str,
    query: str = "",
    referer: str = "",
    candidate_urls: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """
    Download a product photo and index it under store + normalised name.
    Returns the local /static/img URL, or None when nothing could be stored.
    Tries `candidate_urls` (e.g. a larger Amazon variant first) in order.
    """
    skey = store_key(store)
    norm = normalize(name)
    if not norm or not skey:
        return None

    index = _ensure_loaded()
    key = f"{skey}::{norm}"
    with _lock:
        existing = index["entries"].get(key)
    if existing and _file_ok(existing):
        return _url_for(existing)

    referer = referer or REFERERS.get(skey, "")
    urls = [u for u in ([url] + list(candidate_urls or [])) if u]
    data = None
    used_url = ""
    for candidate in urls:
        if not _looks_like_product_url(candidate):
            continue
        data = _download(candidate, referer=referer)
        used_url = candidate
        if data:
            break
    if not data:
        return None

    # Preferred: resize/convert through Pillow. Fallback: keep the original
    # bytes when the format is recognisable but this Pillow build lacks a
    # decoder for it (browsers still render those fine).
    normalised_bytes = _normalise_bytes(data)
    if normalised_bytes:
        ext = ".png" if normalised_bytes[:8].startswith(b"\x89PNG") else ".jpg"
    else:
        fallback_ext = _raw_ext(data)
        if not fallback_ext:
            return None
        normalised_bytes = data
        ext = fallback_ext

    digest = hashlib.sha1(used_url.encode("utf-8")).hexdigest()[:18]
    filename = digest + ext
    try:
        with _lock:  # serialise writes: identical URLs map to identical files
            os.makedirs(IMG_DIR, exist_ok=True)
            with open(os.path.join(IMG_DIR, filename), "wb") as fh:
                fh.write(normalised_bytes)
    except Exception as exc:
        print(f"[IMAGE STORE] write failed for {name!r}: {exc}")
        return None

    entry = {
        "store": skey,
        "name": str(name),
        "norm": norm,
        "file": filename,
        "source": used_url,
        "query": str(query or ""),
        "ts": int(time.time()),
    }
    with _lock:
        index["entries"][key] = entry
        if query:
            bucket = index["by_query"].setdefault(normalize(query), [])
            if key not in bucket:
                bucket.append(key)
    _save()
    return _url_for(entry)


def _ingest_one(cand: Dict[str, Any], store: Any, query: str, referer: str) -> bool:
    name = str(cand.get("name") or "").strip()
    if not name or len(name) < 5:
        return False
    primary = str(cand.get("image_url") or "").strip()
    alternates = [str(u) for u in (cand.get("image_urls") or []) if u]
    try:
        local_url = add_from_url(
            store, name, primary,
            query=query, referer=referer, candidate_urls=alternates,
        )
    except Exception as exc:
        print(f"[IMAGE STORE] ingest error for {name!r}: {exc}")
        return False
    return bool(local_url)


def ingest_candidates(
    store: Any,
    candidates: List[Dict[str, Any]],
    query: str = "",
    referer: str = "",
    cap: int = 24,
) -> int:
    """Store up to `cap` {name, image_url(, image_urls)} candidates for one store."""
    work = [
        c for c in candidates[:cap]
        if str(c.get("name") or "").strip() and len(str(c.get("name")).strip()) >= 5
    ]
    if not work:
        return 0
    stored = 0
    with ThreadPoolExecutor(max_workers=min(6, len(work))) as pool:
        futures = [pool.submit(_ingest_one, c, store, query, referer) for c in work]
        for future in as_completed(futures):
            try:
                if future.result():
                    stored += 1
            except Exception:
                pass
    return stored


# ---------------------------------------------------------------------------
# Lookup (used on every compare request - must stay fast)
# ---------------------------------------------------------------------------

def _file_ok(entry: Dict[str, Any]) -> bool:
    filename = entry.get("file") or ""
    return bool(filename) and os.path.exists(os.path.join(IMG_DIR, filename))


def _best_match(
    entries: Iterable[Dict[str, Any]],
    name: str,
    min_score: float,
) -> str:
    target_norm = normalize(name)
    if not target_norm:
        return ""
    target_tokens = _tokens(target_norm)
    best_entry: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for entry in entries:
        entry_norm = entry.get("norm") or normalize(entry.get("name", ""))
        entry_tokens = _tokens(entry_norm)
        if not entry_tokens:
            continue
        union = len(target_tokens | entry_tokens)
        s = len(target_tokens & entry_tokens) / union if union else 0.0
        if s <= best_score:
            continue
        if has_conflicting_variants(str(name), str(entry.get("name", ""))):
            continue
        best_score = s
        best_entry = entry
    if best_entry and best_score >= min_score and _file_ok(best_entry):
        return _url_for(best_entry)
    return ""


def lookup(store: Any, name: str) -> str:
    """Real photo for this exact store + product, if we scraped one."""
    index = _ensure_loaded()
    skey = store_key(store)
    norm = normalize(name)
    if not skey or not norm:
        return ""
    with _lock:
        entry = index["entries"].get(f"{skey}::{norm}")
        entries_snapshot = list(index["entries"].values())
    if entry and _file_ok(entry):
        return _url_for(entry)
    scoped = [e for e in entries_snapshot if e.get("store") == skey]
    return _best_match(scoped, name, SAME_STORE_MIN_SCORE)


def lookup_any(name: str) -> str:
    """Same physical product photo from ANY store (photos are store-agnostic)."""
    index = _ensure_loaded()
    with _lock:
        entries_snapshot = list(index["entries"].values())
    return _best_match(entries_snapshot, name, ANY_STORE_MIN_SCORE)


def lookup_query(query: str, name: str) -> str:
    """Anything we scraped while searching for this query (last-resort pool)."""
    index = _ensure_loaded()
    q_norm = normalize(query)
    if not q_norm:
        return ""
    with _lock:
        keys = list(index["by_query"].get(q_norm, []))
        entries = index["entries"]
        pool = [entries[k] for k in keys if k in entries]
    return _best_match(pool, name, QUERY_POOL_MIN_SCORE)


def stats() -> Dict[str, Any]:
    index = _ensure_loaded()
    with _lock:
        photos = len(index.get("entries", {}))
        queries = len(index.get("by_query", {}))
    try:
        files = len([f for f in os.listdir(IMG_DIR) if f.endswith((".jpg", ".png"))])
    except Exception:
        files = 0
    return {"photos": photos, "files": files, "queries": queries}
