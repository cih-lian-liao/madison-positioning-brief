"""AI record classifier (A4 step 1), scored from the chosen company's point of view.

For Databricks the prompt is word for word the A4 prompt; for the other companies only
the company name and its core areas change. Bad or missing answers never stop a run:
the record is marked "needs_review" with the reason, as in A4.
"""
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .config import BRANDS, CLASSIFIER_BATCH, CLASSIFIER_MODEL, CORE_AREAS, PROOF_MODEL, PROOF_TYPES, SENTIMENTS, THEMES
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


# ---------------------------------------------------------------------------
# Proof type (added after user testing, 19 Oct 2026): what kind of proof a record is if a
# product marketer cites it. It does not depend on which company is "yours", so it is labelled once.
# ---------------------------------------------------------------------------
PROOF_SYSTEM = """You label evidence records for a product marketer. For EVERY record decide what kind of proof it would be if the marketer cited it in a positioning deck.

proof_type, exactly one of:
- customer_story: a named customer's use, results or case study
- launch: a post that announces or introduces a named product, feature, model, integration or pricing change
- partnership: a partnership or alliance, an investment, or an acquisition of or by another company
- business_news: funding, valuation, revenue, earnings, leadership, legal matters, events, sponsorships or general market coverage
- how_to: a tutorial, tips or best-practices list, migration or architecture guide, blueprint, maturity model, or a "how I built it" write-up
- discussion: a forum thread or opinion piece that asks, argues, compares or complains, without a concrete announcement

Decide in this order:
1. A named customer's story -> customer_story.
2. The title names a specific product or feature (a proper name such as "CoCo", "Genie One MCP", "Data Agent Kit", "Unity Catalog Pages") and is not worded as a guide ("How to", "Top 5", "best practices", "How I built", "Designing", "Using X to") -> launch. "Now available", "GA", "preview", "Introducing" and "Announcing" are always launch.
3. Otherwise use the definitions above.

Rules:
- Judge only from the title and summary.
- Official company blog posts are never discussion: an opinion or framework post on a company blog is how_to.
- A Hacker News thread that simply shares a launch, a customer story or an acquisition keeps that type. Threads that ask, argue or complain are discussion.
- Return valid json only: {"proof": [{"record_id": "...", "proof_type": "..."}]}
- Exactly one entry per record."""


def classify_proof(records, workers=6, batch_size=20):
    """Returns ({record_id: proof_type or ""}, (prompt_tokens, completion_tokens))."""
    batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)]
    usage = [0, 0]
    errors = []

    def run(batch):
        user = f"Label these {len(batch)} records and answer in json.\n\n" + "\n".join(_record_text(r) for r in batch)
        try:
            parsed, _, used = llm.chat_json(PROOF_MODEL, PROOF_SYSTEM, user, temperature=0)
        except FriendlyError as e:
            errors.append(e)
            return {r["record_id"]: "" for r in batch}, (0, 0)
        answers = parsed.get("proof") if isinstance(parsed, dict) else None
        by_id = {str(a.get("record_id", "")).strip(): a.get("proof_type") for a in answers or [] if isinstance(a, dict)}
        out = {}
        for r in batch:
            kind = by_id.get(r["record_id"]) if by_id.get(r["record_id"]) in PROOF_TYPES else ""
            if kind == "discussion" and r["source_type"] == "official_blog":
                kind = "how_to"  # a company's own blog is never a forum discussion
            out[r["record_id"]] = kind
        return out, used

    out = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result, used in pool.map(run, batches):
            out.update(result)
            usage[0] += used[0]
            usage[1] += used[1]
    if errors and len(errors) == len(batches):
        raise errors[0]
    return out, tuple(usage)
