"""Evidence: the verified A3 snapshot, its AI labels, and evidence a person uploads."""
import csv
import io
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from .config import (BRAND_PREFIX, BRANDS, LABELS_DIR, SOURCES, UPLOAD_MAX_BYTES, UPLOAD_MAX_ROWS,
                     VERIFIED_DIR)
from .errors import FriendlyError

LABEL_FIELDS = ["record_id", "sentiment", "theme", "threat", "positioning_signal", "insight", "ai_status", "ai_issue"]


def slug(brand):
    return re.sub(r"[^a-z0-9]+", "_", brand.lower()).strip("_")


def domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/?#:]+)", url or "")
    return m.group(1).lower() if m else ""


@lru_cache(maxsize=1)
def load_snapshot():
    """All 217 verified records (Conductor Brief Part 3), as read-only tuples of dicts."""
    rows = []
    for source_type, (_, folder) in SOURCES.items():
        with (VERIFIED_DIR / folder / f"{folder}_records.csv").open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows.append({
                    "record_id": r["record_id"],
                    "brand": r["brand"],
                    "source_type": r["source_type"],
                    "publisher": r["author_or_publisher"],
                    "title": r["title"],
                    "summary": re.sub(r"\s+", " ", r.get("summary") or "").strip(),
                    "url": r["url"],
                    "published_date": r["published_date"],
                    "points": r.get("engagement_points") or "",
                    "comments": r.get("engagement_comments") or "",
                    "origin": "snapshot",
                })
    return tuple(rows)


@lru_cache(maxsize=8)
def load_labels(focus):
    """AI labels for every snapshot record, scored from `focus`'s point of view (built by tools/build_labels.py)."""
    path = LABELS_DIR / f"focus_{slug(focus)}.csv"
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            t = (r.get("threat") or "").strip()
            r["threat"] = int(t) if t.isdigit() else None
            out[r["record_id"]] = r
    return out


@lru_cache(maxsize=1)
def load_proof_types():
    """{record_id: proof_type} for every snapshot record (built by tools/build_proof_types.py)."""
    path = LABELS_DIR / "proof_types.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {r["record_id"]: r["proof_type"] for r in csv.DictReader(f)}


def save_proof_types(proofs):
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    with (LABELS_DIR / "proof_types.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "proof_type"])
        for rid in sorted(proofs):
            w.writerow([rid, proofs[rid]])


def save_labels(focus, labels):
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    with (LABELS_DIR / f"focus_{slug(focus)}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        w.writeheader()
        for rid in sorted(labels):
            w.writerow({k: labels[rid].get(k, "") for k in LABEL_FIELDS})


# ---------------------------------------------------------------------------
# Uploaded evidence. Same required fields as the data contract: brand, source,
# title, link and publish date. IDs are assigned here, so every claim stays traceable.
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = ["brand", "source_type", "title", "url", "published_date"]
COLUMN_ALIASES = {
    "brand": "brand", "company": "brand", "competitor": "brand",
    "source_type": "source_type", "source": "source_type", "type": "source_type",
    "title": "title", "headline": "title",
    "url": "url", "link": "url",
    "published_date": "published_date", "date": "published_date", "published": "published_date",
    "summary": "summary", "description": "summary", "notes": "summary",
    "publisher": "publisher", "author_or_publisher": "publisher", "author": "publisher",
}
BRAND_ALIASES = {
    "databricks": "Databricks", "snowflake": "Snowflake",
    "google bigquery": "Google BigQuery", "bigquery": "Google BigQuery", "big query": "Google BigQuery",
    "microsoft fabric": "Microsoft Fabric", "fabric": "Microsoft Fabric",
}
SOURCE_ALIASES = {
    "news": "news", "press": "news", "press coverage": "news", "article": "news",
    "official_blog": "official_blog", "blog": "official_blog", "company blog": "official_blog",
    "company blogs": "official_blog",
    "developer_forum": "developer_forum", "forum": "developer_forum", "developer forums": "developer_forum",
    "hacker news": "developer_forum", "hn": "developer_forum", "reddit": "developer_forum",
}
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y", "%B %d, %Y"]
TEMPLATE_DOMAINS = ("example.com", "example.org")


def parse_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def parse_upload(path, allowed_brands, known_urls=()):
    """Read a CSV of extra evidence. Returns (records, skipped_rows); raises FriendlyError if nothing is usable."""
    p = Path(path)
    name, ext = p.name, p.suffix.lower()
    template_fix = ("Under step 6 on the left, press “Download the CSV template”, paste your rows into it, "
                    "and add the file again.")
    if ext in (".xlsx", ".xls", ".numbers"):
        kind = "a Numbers file" if ext == ".numbers" else "an Excel workbook"
        raise FriendlyError(
            "That file is a spreadsheet, not a CSV",
            f"“{name}” is {kind}. This tool reads CSV files only.",
            "In Excel, Numbers or Google Sheets, choose File → Save As / Download → CSV, then add that file. " + template_fix)
    if ext != ".csv":
        raise FriendlyError("That file isn't a CSV", f"“{name}” isn't a .csv file.", template_fix)
    size = p.stat().st_size
    if size == 0:
        raise FriendlyError("That file is empty", f"“{name}” has nothing in it.", template_fix)
    if size > UPLOAD_MAX_BYTES:
        raise FriendlyError("That file is too large",
                            f"“{name}” is {size / 1_000_000:.1f} MB; the limit is {UPLOAD_MAX_BYTES // 1_000_000} MB.",
                            f"Keep the {UPLOAD_MAX_ROWS} rows that matter most and try again.")

    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise FriendlyError("We couldn't read the text in that file",
                            f"“{name}” isn't saved as plain text.", "Save it as “CSV UTF-8” and add it again.")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h for h in (reader.fieldnames or []) if h and h.strip()]
    mapping = {}
    for h in headers:
        key = COLUMN_ALIASES.get(re.sub(r"[\s\-]+", "_", h.strip().lower()))
        if key and key not in mapping.values():
            mapping[h] = key
    missing = [c for c in REQUIRED_COLUMNS if c not in mapping.values()]
    if missing:
        found = ", ".join(f"“{h.strip()}”" for h in headers) or "none"
        raise FriendlyError(
            f"Your file is missing {_plural(len(missing), 'required column')}",
            f"Missing: {', '.join(missing)}. Columns found: {found}. Every row needs a company, a source type, "
            "a headline, a link and a publish date, so each claim in the brief can be traced to a dated public source.",
            template_fix)

    rows = [r for r in reader if any((v or "").strip() for v in r.values() if isinstance(v, str))]
    if not rows:
        raise FriendlyError("Your file has no rows", f"“{name}” has column names but no evidence under them.", template_fix)
    if len(rows) > UPLOAD_MAX_ROWS:
        raise FriendlyError(f"Your file has {len(rows)} rows; the limit is {UPLOAD_MAX_ROWS}",
                            "Each uploaded row is read by the AI, so this free demo caps uploads.",
                            f"Keep the {UPLOAD_MAX_ROWS} most important rows and add the file again.")

    records, skipped, counters = [], [], {}
    seen = set(known_urls)
    today = date.today()
    for line, r in enumerate(rows, start=2):  # line 1 is the header
        v = {key: (r.get(h) or "").strip() for h, key in mapping.items()}
        empty = [c for c in REQUIRED_COLUMNS if not v.get(c)]
        if empty:
            skipped.append((line, f"missing {', '.join(empty)}"))
            continue
        brand = BRAND_ALIASES.get(v["brand"].lower())
        if not brand:
            skipped.append((line, f"“{v['brand']}” isn't one of the four companies this tool covers ({', '.join(BRANDS)})"))
            continue
        if brand not in allowed_brands:
            skipped.append((line, f"{brand} isn't part of this comparison"))
            continue
        source_type = SOURCE_ALIASES.get(v["source_type"].lower())
        if not source_type:
            skipped.append((line, f"source type “{v['source_type']}” should be news, blog or forum"))
            continue
        published = parse_date(v["published_date"])
        if not published:
            skipped.append((line, f"“{v['published_date']}” isn't a date we can read (use YYYY-MM-DD, e.g. 2026-10-05)"))
            continue
        if published > today:
            skipped.append((line, f"the date {published.isoformat()} is in the future"))
            continue
        url = v["url"]
        if not re.match(r"^https?://[^\s/]+\.[^\s/]+", url):
            skipped.append((line, "the link should start with http:// or https://"))
            continue
        if domain(url).endswith(TEMPLATE_DOMAINS):
            skipped.append((line, "this is the template's example row; replace it with a real article"))
            continue
        if url in seen:
            skipped.append((line, "this link is already in the evidence"))
            continue
        if len(v["title"].split()) < 3:
            skipped.append((line, "the headline is shorter than 3 words"))
            continue
        seen.add(url)
        n = counters[brand] = counters.get(brand, 0) + 1
        records.append({
            "record_id": f"YOU-{BRAND_PREFIX[brand]}-{n:03d}",
            "brand": brand,
            "source_type": source_type,
            "publisher": v.get("publisher") or domain(url),
            "title": v["title"],
            "summary": re.sub(r"\s+", " ", v.get("summary", ""))[:400],
            "url": url,
            "published_date": published.isoformat(),
            "points": "",
            "comments": "",
            "origin": "upload",
            "upload_line": line,
        })

    if not records:
        reasons = "; ".join(f"row {line}: {why}" for line, why in skipped[:3])
        more = f" (and {len(skipped) - 3} more)" if len(skipped) > 3 else ""
        raise FriendlyError("None of the rows in your file could be used", f"{reasons}{more}.",
                            "Fix those rows and add the file again. The template shows one correctly filled row.")
    return records, skipped
