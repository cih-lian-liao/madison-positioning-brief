"""AI record classifier (A4 step 1), scored from the chosen company's point of view.

For Databricks the prompt is word for word the A4 prompt; for the other companies only
the company name and its core areas change. Bad or missing answers never stop a run:
the record is marked "needs_review" with the reason, as in A4.
"""
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .config import BRANDS, CLASSIFIER_BATCH, CLASSIFIER_MODEL, CORE_AREAS, SENTIMENTS, THEMES
from .data import slug
from .errors import FriendlyError


def threat_key(focus):
    return f"threat_to_{slug(focus)}"


def system_prompt(focus):
    others = ", ".join(b for b in BRANDS if b != focus)
    key = threat_key(focus)
    return f"""You are a competitive-intelligence analyst supporting the {focus} product marketing team.
You read short evidence records (news headlines, official blog posts, Hacker News posts) about {focus} and its competitors ({others}) and classify each one.

For EVERY record return:
- record_id: copy it exactly as given.
- sentiment: tone toward the record's own brand: "positive", "neutral" or "negative".
- theme: exactly one of: {", ".join(THEMES)}.
  ai_agents = AI, LLMs, agents, GenAI features; data_platform = lakehouse/warehouse, storage, open table formats; analytics_bi = SQL, BI, dashboards, spreadsheets; data_engineering = pipelines, ETL, streaming; governance_security = catalog, governance, security, compliance; performance_cost = benchmarks, speed, pricing, cost; partnerships_ecosystem = partners, integrations, acquisitions; funding_business = funding, valuation, IPO, revenue, leadership, legal; developer_experience = tools, tutorials, open source, community; other = none of these.
- positioning_signal: at most 15 words. What is this brand claiming or pushing, according to this record?
- {key}: integer 1-5.
  For competitor records: 5 = direct attack on a {focus} core area ({CORE_AREAS[focus]}) with strong proof such as a major launch or big customer win; 4 = significant move in an overlapping area; 3 = relevant but incremental; 2 = minor or tangential; 1 = no competitive relevance.
  For {focus} records: score the risk to {focus} itself (negative press, legal trouble, customer churn = higher; good news = 1).
- insight: one sentence. What should a {focus} product manager take away?

Rules:
- Use ONLY the text in the records. Do not invent facts, numbers or customers.
- If a record is too thin to judge, use theme "other", sentiment "neutral", threat 1, and say so in the insight.
- Return valid json only, in this shape: {{"classifications": [ {{"record_id": "...", "sentiment": "...", "theme": "...", "positioning_signal": "...", "{key}": 3, "insight": "..."}} ]}}
- Exactly one entry per record. No extra records."""


def _record_text(r):
    text = (f"[{r['record_id']}] brand={r['brand']} | type={r['source_type']} | publisher={r['publisher']} | "
            f"date={r['published_date']}\nTitle: {r['title']}\n")
    if r.get("summary"):
        text += f"Summary: {r['summary'][:400]}\n"
    return text


def _validate(batch, parsed, batch_issue, key):
    """Check every answer against the allowed labels (A4 'Validate AI Output')."""
    answers = parsed.get("classifications") if isinstance(parsed, dict) else None
    answers = answers if isinstance(answers, list) else []
    if not batch_issue and not answers:
        batch_issue = "AI returned no classifications"
    by_id = {str(a.get("record_id", "")).strip(): a for a in answers if isinstance(a, dict)}
    out = {}
    for r in batch:
        a = by_id.get(r["record_id"])
        problems, threat = [], None
        if not a:
            problems.append(batch_issue or "record missing from AI response")
        else:
            if a.get("sentiment") not in SENTIMENTS:
                problems.append(f'invalid sentiment "{a.get("sentiment")}"')
            if a.get("theme") not in THEMES:
                problems.append(f'invalid theme "{a.get("theme")}"')
            try:
                threat = round(float(a.get(key)))
            except (TypeError, ValueError):
                threat = None
            if threat is None or not 1 <= threat <= 5:
                problems.append(f'invalid threat "{a.get(key)}"')
                threat = None
            if not a.get("insight"):
                problems.append("empty insight")
        a = a or {}
        out[r["record_id"]] = {
            "record_id": r["record_id"],
            "sentiment": a.get("sentiment", "") if a.get("sentiment") in SENTIMENTS else "",
            "theme": a.get("theme", "") if a.get("theme") in THEMES else "",
            "threat": threat,
            "positioning_signal": str(a.get("positioning_signal", ""))[:200],
            "insight": str(a.get("insight", ""))[:300],
            "ai_status": "needs_review" if problems else "ok",
            "ai_issue": "; ".join(problems),
        }
    return out


def classify(records, focus, workers=6, on_batch=None):
    """Label records in batches of 10. Returns ({record_id: label}, (prompt_tokens, completion_tokens))."""
    key = threat_key(focus)
    system = system_prompt(focus)
    batches = [records[i:i + CLASSIFIER_BATCH] for i in range(0, len(records), CLASSIFIER_BATCH)]
    usage = [0, 0]
    errors = []

    def run(batch):
        user = f"Classify these {len(batch)} records and answer in json.\n\n" + "\n".join(_record_text(r) for r in batch)
        try:
            parsed, _, used = llm.chat_json(CLASSIFIER_MODEL, system, user, temperature=0)
            return _validate(batch, parsed, "" if parsed else "malformed JSON from AI", key), used
        except FriendlyError as e:
            errors.append(e)
            return _validate(batch, None, f"AI call failed: {e.title}", key), (0, 0)

    labels = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, (result, used) in enumerate(pool.map(run, batches), start=1):
            labels.update(result)
            usage[0] += used[0]
            usage[1] += used[1]
            if on_batch:
                on_batch(done, len(batches))
    if errors and len(errors) == len(batches):
        raise errors[0]  # nothing was labelled at all: surface the real reason
    return labels, tuple(usage)
