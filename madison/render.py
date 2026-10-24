"""Turn a run into things a product marketer can read: the brief, battlecards, the check, the sources.

The same HTML is shown in the app and saved as a stand-alone file that prints cleanly to PDF.
Every record ID is a link to its public source (Conductor Brief Part 4, step 4).
"""
import csv
import html
import io
import re
from datetime import datetime

from .config import PROOF_TYPES, SNAPSHOT_DATE, SOURCES, THEMES
from .data import slug
from .pipeline import fmt_day

SOURCE_LABEL = {"news": "Press", "official_blog": "Company blog", "developer_forum": "Hacker News"}

CSS = """
.mpb{--mpb-ink:#15171b;--mpb-ink2:#474d57;--mpb-muted:#6f7682;--mpb-line:#e1e4e9;--mpb-panel:#f4f6f9;
--mpb-card:#ffffff;--mpb-accent:#2457c5;--mpb-accent-ink:#1c4396;--mpb-accent-soft:#e8eefb;--mpb-good:#0b7a3e;
--mpb-good-soft:#e3f4ea;--mpb-warn:#8a5300;--mpb-warn-soft:#fff3db;--mpb-bad:#b42318;--mpb-bad-soft:#fdeceb;
color:var(--mpb-ink);font-size:15px;line-height:1.55;text-align:left}
.dark .mpb{--mpb-ink:#eceef2;--mpb-ink2:#c0c5ce;--mpb-muted:#959ca8;--mpb-line:#343941;--mpb-panel:#1c2027;
--mpb-card:#15181e;--mpb-accent:#7ea6ff;--mpb-accent-ink:#a8c3ff;--mpb-accent-soft:#1d2a47;--mpb-good:#5fd49b;
--mpb-good-soft:#11301f;--mpb-warn:#f3b65c;--mpb-warn-soft:#382811;--mpb-bad:#ff8d84;--mpb-bad-soft:#3c1513}
.mpb *{box-sizing:border-box}
.mpb p{margin:0 0 8px}
.mpb a{color:var(--mpb-accent-ink)}
.mpb .mpb-label{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;font-weight:700;color:var(--mpb-muted);margin:0 0 6px}
.mpb h2.mpb-h{font-size:17px;line-height:1.3;margin:28px 0 10px;padding:0 0 6px;border-bottom:1px solid var(--mpb-line);color:var(--mpb-ink);font-weight:700}
.mpb h3.mpb-h3{font-size:15.5px;line-height:1.35;margin:0 0 4px;color:var(--mpb-ink);font-weight:700}
.mpb .mpb-muted{color:var(--mpb-muted)}
.mpb .mpb-small{font-size:13px}
.mpb-banner{display:flex;gap:14px;align-items:flex-start;border-radius:10px;padding:14px 16px;margin:0 0 12px}
.mpb-banner.ok{background:var(--mpb-good-soft);color:var(--mpb-good)}
.mpb-banner.bad{background:var(--mpb-bad-soft);color:var(--mpb-bad)}
.mpb-banner .mpb-icon{font-size:22px;line-height:1;font-weight:700;margin-top:1px}
.mpb-banner .mpb-title{font-weight:700;font-size:16px;line-height:1.35}
.mpb-banner .mpb-meta{color:var(--mpb-ink2);font-size:13px;margin-top:3px}
.mpb-flag{background:var(--mpb-warn-soft);color:var(--mpb-warn);border-radius:8px;padding:10px 14px;margin:0 0 12px;font-size:14px}
.mpb-flag b{font-weight:700}
.mpb-ribbon{background:var(--mpb-accent-soft);color:var(--mpb-accent-ink);border-radius:8px;padding:10px 14px;margin:0 0 12px;font-size:14px}
.mpb-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:4px 0 6px}
.mpb-kpi{background:var(--mpb-panel);border-radius:8px;padding:10px 12px}
.mpb-kpi b{display:block;font-size:20px;line-height:1.25;color:var(--mpb-ink)}
.mpb-kpi span{font-size:12.5px;color:var(--mpb-ink2)}
.mpb-callout{border-left:4px solid var(--mpb-accent);background:var(--mpb-panel);padding:12px 16px;border-radius:0 8px 8px 0;font-size:15.5px}
.mpb-question{border:1px solid var(--mpb-accent);border-radius:10px;padding:12px 16px;margin:14px 0 4px;background:var(--mpb-card)}
.mpb-question q{font-style:italic;color:var(--mpb-ink2)}
.mpb-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.mpb-card{border:1px solid var(--mpb-line);border-radius:10px;padding:12px 14px;background:var(--mpb-card)}
.mpb-card .mpb-num{display:inline-block;width:22px;height:22px;border-radius:50%;background:var(--mpb-accent-soft);color:var(--mpb-accent-ink);font-weight:700;font-size:12.5px;text-align:center;line-height:22px;margin-right:6px}
.mpb-comp{border:1px solid var(--mpb-line);border-radius:10px;padding:12px 14px;margin:0 0 10px;background:var(--mpb-card)}
.mpb-comp-head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;align-items:center;margin-bottom:6px}
.mpb-two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px}
.mpb-ref{display:inline-block;font:12px/1.75 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--mpb-accent-soft);color:var(--mpb-accent-ink)!important;border-radius:5px;padding:0 7px;margin:5px 5px 0 0;text-decoration:none!important;white-space:nowrap}
.mpb-ref:hover{outline:1px solid var(--mpb-accent)}
.mpb-ref.bad{background:var(--mpb-bad-soft);color:var(--mpb-bad)!important;text-decoration:line-through!important}
.mpb-ref.s-strong{background:var(--mpb-good-soft);color:var(--mpb-good)!important}
.mpb-ref.s-weak{background:var(--mpb-warn-soft);color:var(--mpb-warn)!important}
.mpb-ref .mpb-pt{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-size:11.5px;margin-left:6px;padding-left:6px;border-left:1px solid currentColor}
.mpb-weak{margin-top:8px;background:var(--mpb-warn-soft);color:var(--mpb-warn);border-radius:6px;padding:6px 9px;font-size:13px}
.mpb-legend{font-size:12.5px;color:var(--mpb-muted);margin:8px 0 0}
.mpb-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin:0 4px 0 10px;vertical-align:-1px}
.mpb-upload{border-radius:8px;padding:8px 10px;font-size:13px;line-height:1.45;margin:6px 0}
.mpb-upload.ok{background:var(--mpb-good-soft);color:var(--mpb-ink)}
.mpb-upload.bad{background:var(--mpb-bad-soft);color:var(--mpb-ink)}
.mpb-upload b{color:var(--mpb-ink)}
.mpb-ok{color:var(--mpb-good);font-weight:700}
.mpb-no{color:var(--mpb-bad);font-weight:700}
.mpb-meter{display:inline-flex;gap:3px;vertical-align:middle;margin-right:6px}
.mpb-meter i{width:15px;height:8px;border-radius:2px;background:var(--mpb-line)}
.mpb-meter i.on{background:var(--mpb-accent)}
.mpb-tag{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 9px;background:var(--mpb-panel);color:var(--mpb-ink2)}
.mpb-tag.warn{background:var(--mpb-warn-soft);color:var(--mpb-warn)}
.mpb-tag.bad{background:var(--mpb-bad-soft);color:var(--mpb-bad)}
.mpb-tag.ok{background:var(--mpb-good-soft);color:var(--mpb-good)}
.mpb ul.mpb-list{margin:0;padding-left:20px}
.mpb ul.mpb-list li{margin:0 0 10px}
.mpb ul.mpb-plain{list-style:none;padding-left:0}
.mpb ul.mpb-notes{list-style:none;margin:0;padding:0}
.mpb ul.mpb-notes li{position:relative;padding:6px 0 6px 26px;border-bottom:1px solid var(--mpb-line);font-size:14px;color:var(--mpb-ink2)}
.mpb ul.mpb-notes li:last-child{border-bottom:0}
.mpb ul.mpb-notes li::before{position:absolute;left:2px;top:6px;font-weight:700}
.mpb ul.mpb-notes li.info::before{content:"i";color:var(--mpb-accent);border:1.5px solid var(--mpb-accent);border-radius:50%;width:15px;height:15px;font-size:11px;line-height:13px;text-align:center;top:9px}
.mpb ul.mpb-notes li.warn::before{content:"!";color:var(--mpb-warn);border:1.5px solid var(--mpb-warn);border-radius:50%;width:15px;height:15px;font-size:11px;line-height:13px;text-align:center;top:9px}
.mpb table.mpb-table{width:100%;border-collapse:collapse;font-size:13.5px;margin:4px 0 8px}
.mpb table.mpb-table th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--mpb-muted);border-bottom:1px solid var(--mpb-line);padding:6px 8px;font-weight:700;background:transparent}
.mpb table.mpb-table td{border-bottom:1px solid var(--mpb-line);padding:8px;vertical-align:top;color:var(--mpb-ink);background:transparent}
.mpb .mpb-bars{margin-top:4px}
.mpb .mpb-bar{display:grid;grid-template-columns:minmax(110px,170px) 1fr 70px;gap:8px;align-items:center;margin:5px 0;font-size:13px}
.mpb .mpb-track{height:8px;background:var(--mpb-panel);border-radius:4px;overflow:hidden}
.mpb .mpb-fill{display:block;height:100%;background:var(--mpb-accent)}
.mpb .mpb-bar .v{text-align:right;color:var(--mpb-ink2)}
.mpb details{border:1px solid var(--mpb-line);border-radius:8px;padding:8px 12px;margin:10px 0}
.mpb details summary{cursor:pointer;font-weight:600}
.mpb .mpb-foot{margin-top:22px;padding-top:10px;border-top:1px solid var(--mpb-line);font-size:12.5px;color:var(--mpb-muted)}
.mpb-empty{border:1.5px dashed var(--mpb-line);border-radius:12px;padding:22px 24px}
.mpb-empty ol{margin:8px 0 12px;padding-left:22px}
.mpb-empty ol li{margin:0 0 6px}
.mpb-empty .mpb-preview{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}
.mpb-empty .mpb-preview div{background:var(--mpb-panel);border-radius:8px;padding:8px 10px;font-size:13.5px;color:var(--mpb-ink2)}
.mpb-empty .mpb-preview b{color:var(--mpb-ink)}
.mpb-mobile-only{display:none}
.mpb-error{border-radius:12px;padding:16px 18px;border:1.5px solid var(--mpb-bad);background:var(--mpb-bad-soft)}
.mpb-error.warn{border-color:var(--mpb-warn);background:var(--mpb-warn-soft)}
.mpb-error .mpb-title{font-weight:700;font-size:17px;color:var(--mpb-bad);margin-bottom:6px}
.mpb-error.warn .mpb-title{color:var(--mpb-warn)}
.mpb-error p{color:var(--mpb-ink)}
.mpb-error .mpb-fix{margin-top:8px;padding-top:8px;border-top:1px solid rgba(127,127,127,.25)}
@media (max-width:760px){.mpb-mobile-only{display:block}.mpb-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.mpb-cards,.mpb-two,.mpb-empty .mpb-preview{grid-template-columns:1fr}}
"""

PAGE_CSS = """
body{margin:0;background:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
main.mpb{max-width:920px;margin:0 auto;padding:36px 28px}
.mpb-doc-title{font-size:26px;font-weight:800;line-height:1.2;margin:4px 0 4px}
.mpb-part{break-before:page;margin-top:36px}
@media print{main.mpb{padding:0;max-width:none}.mpb-card,.mpb-comp,.mpb-kpi,tr{break-inside:avoid}h2.mpb-h{break-after:avoid}@page{margin:14mm}}
"""


def e(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def _safe_url(url):
    return url if re.match(r"^https?://", url or "") else "#"


def built_at(result):
    if result.get("built_label"):
        return result["built_label"]
    try:
        dt = datetime.fromisoformat(result["generated_at"])
        return f"{dt.day} {dt.strftime('%b %Y')}, {dt.strftime('%I:%M %p').lstrip('0')} {dt.tzname() or ''}".strip()
    except (KeyError, ValueError):
        return result.get("generated_at", "")


def window_text(result, short=False):
    w = result.get("window", {})
    parts = []
    for k in SOURCES:
        rng = w.get("by_source", {}).get(k)
        if rng:
            parts.append(f"{SOURCE_LABEL[k].lower() if short else SOURCE_LABEL[k]} {fmt_day(rng[0])} – {fmt_day(rng[1])}")
    return "; ".join(parts)


def _vs_line(result):
    st = result["settings"]
    comps = st["competitors"]
    joined = comps[0] if len(comps) == 1 else ", ".join(comps[:-1]) + " and " + comps[-1]
    return f"{st['company']} vs {joined}"


class _Ctx:
    def __init__(self, result):
        self.r = result
        self.by_id = {x["record_id"]: x for x in result["records"]}
        self.focus = result["settings"]["company"]
        self.brief = result.get("brief") or {}
        self.stats = {b["brand"]: b for b in result["brands"]}

    def chip(self, rid):
        rec = self.by_id.get(rid)
        if not rec or rec.get("ai_status") != "ok" or rec.get("duplicate_of"):
            return f'<span class="mpb-ref bad" title="This ID is not in the evidence">{e(rid)}</span>'
        label, strength = PROOF_TYPES.get(rec.get("proof_type") or "", ("", "unknown"))
        tip = f"{rec['title']} · {rec['publisher']} · {fmt_day(rec['published_date'])}"
        if label:
            tip += f" · AI label: {label}"
        tag = f'<span class="mpb-pt">{e(label)}</span>' if label else ""
        return (f'<a class="mpb-ref s-{strength}" href="{e(_safe_url(rec["url"]))}" target="_blank" '
                f'rel="noopener noreferrer" title="{e(tip)}">{e(rid)}{tag}</a>')

    def chips(self, refs):
        return "".join(self.chip(str(x).strip()) for x in (refs or []))


def tick(ok):
    if ok is False:
        return '<span class="mpb-no" title="Failed the citation check">✗</span>'
    return '<span class="mpb-ok" title="Citations checked">✓</span>'


def meter(t):
    t = t or 0
    bars = "".join(f'<i class="{"on" if i <= t else ""}"></i>' for i in range(1, 6))
    return f'<span class="mpb-meter" role="img" aria-label="threat {t} of 5">{bars}</span>'


def _status_line(result):
    qa = result["qa"]
    n, v = qa["claims_total"], qa["claims_verified"]
    if result["status"] == "verified":
        after = " after one rewrite" if qa.get("attempt", 1) > 1 else ""
        return "ok", "✓", f"Verified: all {n} claims cite real sources about the right company{after}"
    return "bad", "!", (f"Not verified: {v} of {n} claims passed the citation check. Claims marked ✗ need a person "
                        "to check them before this brief is shared.")


def banner(result):
    cls, icon, title = _status_line(result)
    meta = (f"{e(_vs_line(result))} · Built {e(built_at(result))} in {result['seconds']:.0f} s · "
            f"Evidence collected {e(fmt_day(SNAPSHOT_DATE))}")
    return (f'<div class="mpb-banner {cls}" role="status"><div class="mpb-icon">{icon}</div><div>'
            f'<div class="mpb-title">{e(title)}</div><div class="mpb-meta">{meta}</div></div></div>')


def flags(result):
    items = [f"the AI rated {e(c['brand'])} {c['ai']}/5, but its evidence averages {c['evidence_avg']:.1f} "
             "(ratings should stay within 1 point)" for c in result.get("threat_checks", []) if not c["ok"]]
    items += [f"“{e(w['claim'].split(': ', 1)[-1])}” rests only on "
              f"{e(' and '.join(PROOF_TYPES[t][0] for t in w['types'] if t in PROOF_TYPES) or 'weak')} proof"
              for w in result.get("qa", {}).get("weak_proof", [])]
    if not items:
        return ""
    n = len(items)
    return (f'<div class="mpb-flag"><b>{n} thing{"s" if n > 1 else ""} to review before you share:</b> '
            f'{"; ".join(items)}.</div>')


STRENGTH_TAG = {"strong": ("ok", "strong proof"), "medium": ("", "moderate proof"), "weak": ("warn", "weak proof")}


def proof_tag(proof):
    if not proof:
        return ""
    cls, text = STRENGTH_TAG.get(proof.get("strength"), ("", ""))
    return f' <span class="mpb-tag {cls}">{text}</span>' if text else ""


LEGEND = ('<p class="mpb-legend">Source labels are AI judgements from each headline: '
          '<i style="background:var(--mpb-good-soft);border:1px solid var(--mpb-good)"></i>customer story, launch, '
          'partner or acquisition <i style="background:var(--mpb-accent-soft);border:1px solid var(--mpb-accent)"></i>'
          'business news <i style="background:var(--mpb-warn-soft);border:1px solid var(--mpb-warn)"></i>how-to or '
          'discussion</p>')


def kpis(result):
    brief = result.get("brief") or {}
    avg = {b["brand"]: b["avg_threat"] or 0 for b in result["brands"]}
    comps = sorted(brief.get("competitors", []), key=lambda c: (-(c.get("threat_level") or 0), -avg.get(c["brand"], 0)))
    top = comps[0] if comps else {}
    qa, t = result["qa"], result["totals"]
    cells = [
        (t["usable"], "records analyzed"),
        (t["high_threat"], "high-threat moves (4–5 of 5)"),
        (top.get("brand", "–"), f"top threat ({top.get('threat_level', '–')}/5)"),
        (f"{qa['claims_verified']}/{qa['claims_total']}", "claims verified"),
    ]
    return '<div class="mpb-kpis">' + "".join(f'<div class="mpb-kpi"><b>{e(a)}</b><span>{e(b)}</span></div>'
                                              for a, b in cells) + "</div>"


def notes_list(result, levels=("info", "warn")):
    items = [w for w in result.get("warnings", []) if w["level"] in levels]
    if not items:
        return '<p class="mpb-muted">No gaps found in the evidence for this brief.</p>'
    return '<ul class="mpb-notes">' + "".join(f'<li class="{w["level"]}">{e(w["text"])}</li>' for w in items) + "</ul>"


def brief_view(result, example=False):
    c = _Ctx(result)
    b = c.brief
    st = result["settings"]
    out = ['<div class="mpb">']
    if example:
        out.append('<div class="mpb-ribbon"><b>Example brief.</b> Built earlier with the default settings, so it opens '
                   'instantly. Press “Build my brief” to make one from your own choices.</div>')
    out += [banner(result), flags(result), kpis(result)]

    a = b.get("answer_to_question")
    if st.get("question") and isinstance(a, dict):
        out.append(f'<div class="mpb-question"><div class="mpb-label">Your question {tick(a.get("verified"))}</div>'
                   f'<p><q>{e(st["question"])}</q></p><p>{e(a.get("text"))}</p><div>{c.chips(a.get("evidence_refs"))}</div></div>')

    out.append(f'<h2 class="mpb-h">Bottom line</h2><p>{e(b.get("executive_summary"))}</p>')
    ps = b.get("positioning_statement") or {}
    out.append(f'<h2 class="mpb-h">Positioning statement {tick(ps.get("verified"))}</h2>'
               f'<div class="mpb-callout">{e(ps.get("text"))}<div>{c.chips(ps.get("evidence_refs"))}</div></div>')

    def weak_note(d):
        if (d.get("proof") or {}).get("strength") != "weak":
            return ""
        return ('<div class="mpb-weak">Only how-to or discussion posts back this point. Find a customer result or '
                'a launch before you put it in a deck.</div>')

    cards = "".join(
        f'<div class="mpb-card"><h3 class="mpb-h3"><span class="mpb-num">{i}</span>{e(d.get("title"))} {tick(d.get("verified"))}</h3>'
        f'<div style="margin:-2px 0 6px">{proof_tag(d.get("proof"))}</div>'
        f'<p>{e(d.get("claim"))}</p><div>{c.chips(d.get("evidence_refs"))}</div>{weak_note(d)}</div>'
        for i, d in enumerate(b.get("differentiators", []), start=1))
    out.append(f'<h2 class="mpb-h">Why {e(c.focus)} wins</h2><div class="mpb-cards">{cards}</div>{LEGEND}')

    checks = {x["brand"]: x for x in result.get("threat_checks", [])}
    rows = []
    for comp in sorted(b.get("competitors", []), key=lambda x: -(x.get("threat_level") or 0)):
        chk = checks.get(comp["brand"], {})
        avg = chk.get("evidence_avg")
        tag = ""
        if chk and not chk["ok"]:
            tag = ' <span class="mpb-tag warn">rating doesn’t match the evidence: review</span>'
        counter = (f'<div class="mpb-label" style="margin-top:8px">Our proof</div><div>{c.chips(comp.get("counter_refs"))}</div>'
                   if comp.get("counter_refs") else "")
        rows.append(
            f'<div class="mpb-comp"><div class="mpb-comp-head"><h3 class="mpb-h3">{e(comp["brand"])} {tick(comp.get("verified"))}</h3>'
            f'<div>{meter(comp.get("threat_level"))}<b>{e(comp.get("threat_level"))}/5 threat</b>'
            f'<span class="mpb-muted mpb-small"> · evidence average {avg if avg is not None else "–"}</span>{tag}</div></div>'
            f'<div class="mpb-two"><div><div class="mpb-label">What they push</div><p>{e(comp.get("what_they_push"))}</p>'
            f'<div class="mpb-label">Their evidence</div><div>{c.chips(comp.get("evidence_refs"))}</div></div>'
            f'<div><div class="mpb-label">How {e(c.focus)} wins</div><p>{e(comp.get("how_to_win"))}</p>{counter}</div></div></div>')
    out.append(f'<h2 class="mpb-h">How to win against each competitor</h2>{"".join(rows)}'
               '<p class="mpb-muted mpb-small">One-page versions of these are in the Battlecards tab.</p>')

    risks = "".join(f'<li>{tick(r.get("verified"))} {e(r.get("risk"))}<div>{c.chips(r.get("evidence_refs"))}</div></li>'
                    for r in b.get("risks_to_watch", []))
    out.append(f'<h2 class="mpb-h">Risks to watch</h2><ul class="mpb-list mpb-plain">{risks}</ul>')
    out.append(f'<h2 class="mpb-h">About this evidence</h2><p class="mpb-small mpb-muted">{e(window_text(result))}</p>'
               f'{notes_list(result)}')
    out.append('<div class="mpb-foot">Every ID links to its public source. The automatic check confirms that each cited '
               'source exists in this run’s evidence and is about the right company. It does not confirm that the '
               'source says exactly what the claim says, so open two or three before you present.</div></div>')
    return "".join(out)


def _bars(stats):
    mix = stats.get("theme_mix", [])
    rows = mix[:4]
    rest = sum(m["count"] for m in mix[4:])
    total = stats.get("classified_ok") or 1
    items = [(THEMES.get(m["theme"], m["theme"]), m["count"], m["share"]) for m in rows]
    if rest:
        items.append(("All other topics", rest, round(100 * rest / total)))
    return '<div class="mpb-bars">' + "".join(
        f'<div class="mpb-bar"><span>{e(lbl)}</span><span class="mpb-track"><span class="mpb-fill" style="width:{pct}%"></span></span>'
        f'<span class="v">{pct}% <span class="mpb-muted">({n})</span></span></div>' for lbl, n, pct in items) + "</div>"


def battlecards_view(result):
    c = _Ctx(result)
    out = ['<div class="mpb"><p class="mpb-muted mpb-small">One card per competitor, built from the same checked '
           'evidence as the brief. Share a card with sales before a deal.</p>']
    checks = {x["brand"]: x for x in result.get("threat_checks", [])}
    for comp in sorted(c.brief.get("competitors", []), key=lambda x: -(x.get("threat_level") or 0)):
        name = comp["brand"]
        s = c.stats.get(name, {})
        top_theme = (s.get("theme_mix") or [{}])[0]
        moves = sorted((c.by_id[x] for x in s.get("top_evidence", []) if x in c.by_id),
                       key=lambda r: -(r.get("threat") or 0))[:3]
        move_items = "".join(
            f'<li><a href="{e(_safe_url(r["url"]))}" target="_blank" rel="noopener noreferrer">{e(r["title"])}</a>'
            f'<div class="mpb-muted mpb-small">{e(r["positioning_signal"])} · threat {r["threat"]}/5 · '
            f'{e(SOURCE_LABEL.get(r["source_type"], r["source_type"]))}, {e(fmt_day(r["published_date"]))} · '
            f'<code>{e(r["record_id"])}</code></div></li>' for r in moves)
        chk = checks.get(name, {})
        tag = ' <span class="mpb-tag warn">rating doesn’t match the evidence: review</span>' if chk and not chk["ok"] else ""
        sent = s.get("sentiment", {})
        counter = (f'<div class="mpb-label" style="margin-top:8px">Our proof</div><div>{c.chips(comp.get("counter_refs"))}</div>'
                   if comp.get("counter_refs") else "")
        out.append(
            f'<div class="mpb-comp" style="padding:16px 18px;margin-bottom:16px">'
            f'<div class="mpb-label">Battlecard · {e(c.focus)} vs</div>'
            f'<div class="mpb-comp-head"><h2 class="mpb-h" style="margin:0;border:0;font-size:21px">{e(name)} {tick(comp.get("verified"))}</h2>'
            f'<div>{meter(comp.get("threat_level"))}<b>{e(comp.get("threat_level"))}/5 threat to {e(c.focus)}</b>{tag}</div></div>'
            f'<div class="mpb-kpis"><div class="mpb-kpi"><b>{s.get("avg_threat", "–")}</b><span>evidence threat average</span></div>'
            f'<div class="mpb-kpi"><b>{s.get("high_threat", 0)}</b><span>high-threat moves</span></div>'
            f'<div class="mpb-kpi"><b>{e(THEMES.get(top_theme.get("theme"), "–"))}</b><span>#1 topic ({top_theme.get("share", 0)}%)</span></div>'
            f'<div class="mpb-kpi"><b>{s.get("classified_ok", 0)}</b><span>records · {sent.get("positive", 0)} positive / '
            f'{sent.get("negative", 0)} negative</span></div></div>'
            f'<div class="mpb-two" style="margin-top:10px"><div><div class="mpb-label">What they push</div><p>{e(comp.get("what_they_push"))}</p>'
            f'<div>{c.chips(comp.get("evidence_refs"))}</div></div>'
            f'<div><div class="mpb-label">How {e(c.focus)} wins</div><div class="mpb-callout">{e(comp.get("how_to_win"))}</div>{counter}</div></div>'
            f'<div class="mpb-two" style="margin-top:14px"><div><div class="mpb-label">What their coverage is about</div>{_bars(s)}</div>'
            f'<div><div class="mpb-label">Their top 3 moves</div><ul class="mpb-list">{move_items}</ul></div></div></div>')
    out.append("</div>")
    return "".join(out)


def checks_view(result):
    c = _Ctx(result)
    qa = result["qa"]
    hist = result.get("qa_history", [])
    out = ['<div class="mpb">',
           '<h2 class="mpb-h" style="margin-top:4px">How the check works</h2>'
           '<p>Every claim must pass three rules: (1) it cites at least one record ID from this run’s evidence; '
           '(2) each cited record is about the right company; (3) a sentence that names a competitor, such as '
           '“unlike Snowflake”, also cites that competitor’s own records. A claim that fails goes back to the AI '
           'once, with the exact problem. If anything still fails, the brief is labelled <b>Not verified</b> and the '
           'failing claims are marked ✗.</p><p>Each source also carries an AI label for the kind of proof it is. '
           'Customer stories, launches and partnerships count as strong proof; how-to and discussion posts as weak. '
           'A reason-you-win backed only by weak proof is flagged for review.</p>'
           '<p class="mpb-muted mpb-small">What it does not check: whether each source says exactly what the claim '
           'says, and whether an AI proof label is right. Open two or three sources before you present.</p>']
    steps = []
    for h in hist:
        res = '<span class="mpb-ok">passed</span>' if h["pass"] else '<span class="mpb-no">failed</span>'
        issues = "".join(f"<li>{e(i)}</li>" for i in h["issues"])
        note = f'<ul class="mpb-list mpb-small" style="margin-top:6px">{issues}</ul>' if issues else ""
        then = " → sent back to the AI with these problems" if not h["pass"] and h["attempt"] == 1 and len(hist) > 1 else ""
        steps.append(f'<li><b>Attempt {h["attempt"]}:</b> {h["claims_verified"]} of {h["claims_total"]} claims {res}{then}{note}</li>')
    out.append(f'<h2 class="mpb-h">Result</h2><ul class="mpb-list">{"".join(steps)}</ul>')

    rows = "".join(
        f'<tr><td>{tick(cl["verified"])}</td><td>{e(cl["claim"])}</td><td>{c.chips(cl["refs"])}</td>'
        f'<td>{proof_tag(cl.get("proof")) or "–"}</td>'
        f'<td>{e("; ".join(cl["problems"])) or "–"}</td></tr>' for cl in qa.get("claims", []))
    out.append('<h2 class="mpb-h">Claim by claim</h2><table class="mpb-table"><thead><tr><th></th><th>Claim</th>'
               f'<th>Sources cited</th><th>Proof</th><th>Problem</th></tr></thead><tbody>{rows}</tbody></table>')

    trows = "".join(
        f'<tr><td>{e(x["brand"])}</td><td>{x["ai"]}/5</td><td>{x["evidence_avg"]:.2f}</td>'
        f'<td>{"<span class=mpb-ok>yes</span>" if x["ok"] else "<span class=mpb-no>no: review</span>"}</td></tr>'
        for x in result.get("threat_checks", []))
    out.append('<h2 class="mpb-h">Threat ratings vs the evidence</h2><p class="mpb-small mpb-muted">The AI’s rating '
               'should stay within 1 point of the average threat score of that competitor’s records.</p>'
               '<table class="mpb-table"><thead><tr><th>Competitor</th><th>AI rating</th><th>Evidence average</th>'
               f'<th>Within 1 point?</th></tr></thead><tbody>{trows}</tbody></table>')

    srows = "".join(
        f'<tr><td>{e(b["brand"])}{" (you)" if b["role"] == "focus" else ""}</td>'
        + "".join(f'<td>{b["by_source"].get(k, 0)}</td>' for k in SOURCES)
        + f'<td><b>{b["classified_ok"]}</b></td></tr>' for b in result["brands"])
    heads = "".join(f"<th>{e(SOURCES[k][0])}</th>" for k in SOURCES)
    out.append('<h2 class="mpb-h">Evidence used</h2><table class="mpb-table"><thead><tr><th>Company</th>'
               f'{heads}<th>Total</th></tr></thead><tbody>{srows}</tbody></table>'
               f'<p class="mpb-small mpb-muted">{e(window_text(result))}</p>')
    out.append(f'<h2 class="mpb-h">Gaps and notes</h2>{notes_list(result)}')

    review = [r for r in result["records"] if r["ai_status"] != "ok"]
    if review:
        rr = "".join(f'<tr><td><code>{e(r["record_id"])}</code></td><td>{e(r["title"])}</td><td>{e(plain_issue(r["ai_issue"]))}</td></tr>'
                     for r in review)
        out.append(f'<h2 class="mpb-h">Left out for a person to review ({len(review)})</h2><table class="mpb-table">'
                   f'<thead><tr><th>ID</th><th>Headline</th><th>Why</th></tr></thead><tbody>{rr}</tbody></table>')
    out.append("</div>")
    return "".join(out)


def plain_issue(issue):
    """The classifier's technical reasons (A4 wording), in words a marketer can follow."""
    out = []
    for part in (p.strip() for p in (issue or "").split(";") if p.strip()):
        m = re.match(r"AI invented IDs in batch: (.+)", part)
        if part == "record missing from AI response":
            out.append("The AI skipped this record")
        elif m:
            out.append(f"it answered with a garbled ID ({m.group(1)}) instead")
        elif part.startswith("AI call failed"):
            out.append("The AI service didn't answer for this record")
        elif part.startswith("invalid"):
            out.append(f"The AI gave a label that isn't allowed ({part.removeprefix('invalid ')})")
        elif part == "not labelled":
            out.append("No AI label is stored for this record")
        else:
            out.append(part)
    text = ", ".join(out)
    return (text[:1].upper() + text[1:] + ".") if text else ""


def _source_row(c, r):
    return (f'<tr><td>{c.chip(r["record_id"])}</td><td><a href="{e(_safe_url(r["url"]))}" target="_blank" '
            f'rel="noopener noreferrer">{e(r["title"])}</a><div class="mpb-muted mpb-small">{e(r["publisher"])} · '
            f'{e(fmt_day(r["published_date"]))} · {e(SOURCE_LABEL.get(r["source_type"], r["source_type"]))}</div></td>'
            f'<td>{e(PROOF_TYPES.get(r.get("proof_type") or "", ("–",))[0])}</td>'
            f'<td>{e(THEMES.get(r.get("theme"), r.get("theme") or "–"))}</td><td>{r.get("threat") or "–"}</td></tr>')


def sources_view(result):
    c = _Ctx(result)
    head = '<thead><tr><th>ID</th><th>Source</th><th>Proof (AI label)</th><th>Topic</th><th>Threat</th></tr></thead>'
    order = [c.focus] + result["settings"]["competitors"]
    cited = [r for r in result["records"] if r.get("cited")]
    out = ['<div class="mpb">',
           f'<p class="mpb-muted mpb-small">{len(cited)} sources are cited in this brief. Click a headline to open it.</p>']
    for brand in order:
        rs = sorted((r for r in cited if r["brand"] == brand), key=lambda r: r["record_id"])
        if rs:
            out.append(f'<h2 class="mpb-h">{e(brand)} ({len(rs)})</h2><table class="mpb-table">{head}<tbody>'
                       + "".join(_source_row(c, r) for r in rs) + "</tbody></table>")
    rest = sorted((r for r in result["records"] if not r.get("cited")), key=lambda r: (order.index(r["brand"]), r["record_id"]))
    out.append(f'<details><summary>All other records considered ({len(rest)})</summary><table class="mpb-table">{head}<tbody>'
               + "".join(_source_row(c, r) for r in rest) + "</tbody></table></details></div>")
    return "".join(out)


def empty_view():
    return """<div class="mpb"><div class="mpb-empty">
<div class="mpb-label">Your brief will appear here</div>
<ol>
<li><b>Choose your company and its competitors</b> in the panel on the left. Databricks against all three is already set up.<span class="mpb-mobile-only mpb-muted mpb-small">On a phone, tap the » arrow at the top left to open the panel.</span></li>
<li><b>Optional:</b> pick a topic, or type the question you need to answer.</li>
<li>Press <b>Build my brief</b>. It usually takes under 30 seconds.</li>
</ol>
<div class="mpb-label" style="margin-top:14px">What you get</div>
<div class="mpb-preview">
<div><b>A verified badge</b><br>shown only when every claim cites a real source about the right company</div>
<div><b>A positioning statement</b><br>and three reasons you win</div>
<div><b>How to win against each competitor</b><br>with a one-page battlecard for each</div>
<div><b>Risks to watch</b><br>and a link to the public source behind every line</div>
</div>
<p class="mpb-muted mpb-small" style="margin-top:12px">Want to see one first? Press <b>See an example brief</b>; it opens instantly.</p>
</div></div>"""


def upload_check_view(added, skipped):
    """Shown under the upload box as soon as a file is added, before anything is built (v2)."""
    ready = f"<b>✓ {len(added)} row{'s' if len(added) != 1 else ''} ready to use.</b>"
    if not skipped:
        return f'<div class="mpb"><div class="mpb-upload ok">{ready}</div></div>'
    items = "".join(f"<li>Row {line}: {e(why)}</li>" for line, why in skipped[:5])
    more = f"<li>…and {len(skipped) - 5} more</li>" if len(skipped) > 5 else ""
    return (f'<div class="mpb"><div class="mpb-upload ok">{ready} {len(skipped)} '
            f'{"rows" if len(skipped) != 1 else "row"} will be skipped:<ul style="margin:4px 0 0;padding-left:18px">'
            f'{items}{more}</ul></div></div>')


def upload_error_view(err):
    return (f'<div class="mpb"><div class="mpb-upload bad" role="alert"><b>{e(err.title)}</b><br>{e(err.detail)}'
            f'<br><b>What to do:</b> {e(err.fix)}</div></div>')


def error_view(err):
    cls = "warn" if getattr(err, "kind", "error") == "warn" else ""
    return (f'<div class="mpb"><div class="mpb-error {cls}" role="alert"><div class="mpb-title">{e(err.title)}</div>'
            f'<p>{e(err.detail)}</p><p class="mpb-fix"><b>What to do:</b> {e(err.fix)}</p></div></div>')


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
def standalone_html(result):
    title = f"Positioning brief: {_vs_line(result)} ({built_at(result)})"
    body = (f'<div class="mpb-label">Briefproof · Proof, not opinion</div>'
            f'<div class="mpb-doc-title">{e(_vs_line(result))}</div>'
            + brief_view(result).removeprefix('<div class="mpb">').removesuffix("</div>")
            + '<div class="mpb-part"><h2 class="mpb-h">Battlecards</h2></div>'
            + battlecards_view(result).removeprefix('<div class="mpb">').removesuffix("</div>")
            + '<div class="mpb-part"></div>' + checks_view(result).removeprefix('<div class="mpb">').removesuffix("</div>")
            + '<div class="mpb-part"><h2 class="mpb-h">Sources</h2></div>'
            + sources_view(result).removeprefix('<div class="mpb">').removesuffix("</div>"))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{CSS}{PAGE_CSS}</style>'
            f'</head><body><main class="mpb">{body}</main></body></html>')


def plain_text(result):
    b = result.get("brief") or {}
    c = _Ctx(result)
    qa = result["qa"]
    status = ("VERIFIED" if result["status"] == "verified" else "NOT VERIFIED") + \
        f": {qa['claims_verified']}/{qa['claims_total']} claims cite real sources about the right company"
    lines = [f"POSITIONING BRIEF: {_vs_line(result).upper()}", status,
             f"Built {built_at(result)} · evidence collected {fmt_day(SNAPSHOT_DATE)}", ""]
    a = b.get("answer_to_question")
    if result["settings"].get("question") and isinstance(a, dict):
        lines += [f"YOUR QUESTION: {result['settings']['question']}", f"{a.get('text', '')} {_ids(a)}", ""]
    ps = b.get("positioning_statement") or {}
    lines += ["BOTTOM LINE", b.get("executive_summary", ""), "", "POSITIONING STATEMENT", f"{ps.get('text', '')} {_ids(ps)}",
              "", f"WHY {c.focus.upper()} WINS"]
    lines += [f"{i}. {d.get('title', '')}: {d.get('claim', '')} {_ids(d)}" for i, d in enumerate(b.get("differentiators", []), 1)]
    lines += ["", "HOW TO WIN AGAINST EACH COMPETITOR"]
    for comp in b.get("competitors", []):
        lines.append(f"- {comp['brand']} (threat {comp.get('threat_level')}/5). They push: {comp.get('what_they_push', '')} "
                     f"{_ids(comp)} We win: {comp.get('how_to_win', '')}")
    lines += ["", "RISKS TO WATCH"] + [f"- {r.get('risk', '')} {_ids(r)}" for r in b.get("risks_to_watch", [])]
    lines += ["", "SOURCES"]
    for r in sorted((x for x in result["records"] if x.get("cited")), key=lambda x: x["record_id"]):
        kind = PROOF_TYPES.get(r.get("proof_type") or "", ("",))[0]
        lines.append(f"[{r['record_id']}{' · ' + kind if kind else ''}] {r['title']} ({r['publisher']}, "
                     f"{fmt_day(r['published_date'])}) {r['url']}")
    return "\n".join(lines)


def _ids(part):
    refs = list(part.get("evidence_refs") or []) + list(part.get("counter_refs") or [])
    return "[" + ", ".join(refs) + "]" if refs else ""


CSV_COLUMNS = ["record_id", "brand", "source_type", "publisher", "published_date", "title", "url", "sentiment", "theme",
               "threat", "proof_type", "positioning_signal", "insight", "cited_in_brief", "ai_status", "ai_issue",
               "duplicate_of", "origin"]


def downloads(result):
    """The stand-alone brief (HTML, prints to PDF) and the scored evidence (CSV), as (file name, bytes) pairs."""
    stem = f"Briefproof_brief_{slug(result['settings']['company'])}_{result['run_id']}"
    threat_col = f"threat_to_{slug(result['settings']['company'])}"

    def cell(r, k):
        if k == "cited_in_brief":
            return "yes" if r.get("cited") else "no"
        return r.get(k, "")

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([threat_col if k == "threat" else k for k in CSV_COLUMNS])
    for r in result["records"]:
        w.writerow([cell(r, k) for k in CSV_COLUMNS])
    return ((f"{stem}.html", standalone_html(result).encode("utf-8")),
            (f"{stem}_evidence.csv", buf.getvalue().encode("utf-8-sig")))
