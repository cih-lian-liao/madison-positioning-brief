"""Madison Positioning Brief: the web app.

Turn competitor news into a fully sourced brief, so a product marketer can answer
"How do we win?" with proof, not opinion. Run locally with `streamlit run streamlit_app.py`.
"""
import json
import os
import tempfile
import time
import traceback
from pathlib import Path

import streamlit as st

from madison import render
from madison.config import BRANDS, SAMPLES_DIR, SNAPSHOT_DATE, SOURCES, THEMES
from madison.data import load_snapshot, parse_upload
from madison.errors import FriendlyError
from madison.limits import reserver, visitor_id
from madison.pipeline import Settings, fmt_day, run

st.set_page_config(page_title="Briefproof", page_icon="🧭", layout="wide",
                   initial_sidebar_state="expanded")

# On Streamlit Community Cloud the key is a secret; the pipeline reads it from the environment.
if not os.getenv("OPENAI_API_KEY"):
    try:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass  # no key: the example still works, and building a brief explains what's missing

TEMPLATE = SAMPLES_DIR / "evidence_template.csv"
EXAMPLE = SAMPLES_DIR / "example_run.json"
DEFAULT_COMPANY = "Databricks"
SOURCE_LABELS = {
    "news": "Press coverage: news articles from the last 90 days",
    "official_blog": "Company blogs: what each company says about itself",
    "developer_forum": "Developer forums: Hacker News threads from the last 12 months",
}
TOPICS = ["all"] + [k for k in THEMES if k != "other"]

HEADER = f"""<div class="mpb mpb-header">
<div class="mpb-label">Briefproof · Proof, not opinion</div>
<h1 class="mpb-hero">Turn competitor news into a fully sourced brief</h1>
<p class="mpb-lede">Built for product marketers at data platform companies, so you can answer
<b>“How do we win?”</b> with proof, not opinion. Every claim links to its public source, and a brief is
marked <b>Verified</b> only when every citation passes an automatic check.</p>
<p class="mpb-small mpb-muted"><b>This version covers four companies: Databricks, Snowflake, Google BigQuery and
Microsoft Fabric.</b> Its evidence is 217 checked public records (press coverage, company blogs and Hacker News
threads), collected {fmt_day(SNAPSHOT_DATE)}.</p>
</div>"""

FOOTER = """<div class="mpb mpb-footer">Made by Cih-Lian Liao for INFO7375 at Northeastern University. Not affiliated
with any company named here. Briefs are written by AI from public sources and checked by rules: read the sources
before you rely on a claim.</div>"""

APP_CSS = """
.block-container{padding-top:4.4rem;max-width:1180px}
.mpb-header{padding:0 2px 6px}
.mpb-header h1.mpb-hero{font-size:30px;line-height:1.2;margin:2px 0 8px;font-weight:800;color:var(--mpb-ink);padding:0}
.mpb-header .mpb-lede{font-size:16px;max-width:860px;color:var(--mpb-ink2);margin-bottom:6px}
.mpb-footer{font-size:12.5px;color:var(--mpb-muted);padding:18px 2px 0}
.mpb-side-label{font-weight:700;font-size:15px;color:#15171b;margin:14px 0 2px}
.mpb-side-hint{font-size:12.5px;color:#5f6672;margin:0 0 6px;line-height:1.4}
"""


def log(event, **fields):
    """One JSON line per event in the server log (no IP addresses, no uploaded content)."""
    print(json.dumps({"event": event, "at": time.strftime("%Y-%m-%d %H:%M:%S"), **fields}, ensure_ascii=False), flush=True)


def label(text, hint_text=""):
    """A visible label and hint above an input (the widget's own label stays for screen readers)."""
    hint_html = f'<div class="mpb-side-hint">{hint_text}</div>' if hint_text else ""
    st.markdown(f'<div class="mpb-side-label">{text}</div>{hint_html}', unsafe_allow_html=True)


def visitor():
    ip = ""
    try:
        ip = st.context.ip_address or ""
        if not ip:
            ip = (st.context.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    except Exception:
        pass
    return visitor_id(ip)


def settings_for_log(s):
    return {"company": s.company, "competitors": s.competitors, "sources": s.sources, "topic": s.topic,
            "question": s.question[:300], "upload": bool(s.upload_path)}


# ---------------------------------------------------------------------------
# Inputs (left panel)
# ---------------------------------------------------------------------------
st.html(f"<style>{render.CSS}{APP_CSS}</style>")

with st.sidebar:
    st.markdown("### Build your brief")
    label("1. Your company", "The brief is written from this company’s side.")
    company = st.selectbox("Your company", BRANDS, index=BRANDS.index(DEFAULT_COMPANY), label_visibility="collapsed")

    label("2. Competitors to compare against", "Pick one or more. Each gets a “how to win” section and a battlecard.")
    competitors = [b for b in BRANDS if b != company and st.checkbox(b, value=True, key=f"cmp_{company}_{b}")]

    label("3. Evidence to use", "Keep all three for the most balanced brief.")
    sources = [k for k in SOURCES if st.checkbox(SOURCE_LABELS[k], value=True, key=f"src_{k}")]

    label("4. Focus topic (optional)", "Narrow the brief to one area, such as AI & agents.")
    topic = st.selectbox("Focus topic", TOPICS, format_func=lambda k: "All topics" if k == "all" else THEMES[k],
                         label_visibility="collapsed")

    label("5. The question you need to answer (optional)")
    question = st.text_area("The question you need to answer", height=90, label_visibility="collapsed",
                            placeholder="e.g. Sales says Snowflake is easier to start with. How do we respond?")

    with st.expander("6. Add your own evidence (optional, CSV file)"):
        st.markdown("Found more articles about **Databricks, Snowflake, Google BigQuery or Microsoft Fabric**? "
                    "Add up to 100 rows. Articles about other companies can’t be used yet, because every claim has "
                    "to stand on checked evidence about these four. Each row needs **brand**, **source_type** "
                    "(news, blog or forum), **title**, **url** and **published_date** (YYYY-MM-DD).")
        upload = st.file_uploader("Your CSV file")
        if upload is not None:  # check the file straight away, before anything is built
            check_path = Path(tempfile.mkdtemp(prefix="madison-check-")) / Path(upload.name).name
            check_path.write_bytes(upload.getvalue())
            try:
                rows_ok, rows_skipped = parse_upload(str(check_path), [company] + competitors,
                                                     {r["url"] for r in load_snapshot()})
                st.html(render.upload_check_view(rows_ok, rows_skipped))
            except FriendlyError as err:
                st.html(render.upload_error_view(err))
            except Exception:  # never show a stack trace; the build step checks the file again anyway
                traceback.print_exc()
                st.warning("We couldn't check that file just now. Add it again, or build the brief without it.")
        st.download_button("Download the CSV template", data=TEMPLATE.read_bytes(),
                           file_name="briefproof_evidence_template.csv", mime="text/csv", on_click="ignore")

    build = st.button("Build my brief", type="primary", width="stretch")
    example = st.button("See an example brief (opens instantly)", width="stretch")

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
st.html(HEADER)
progress_area = st.empty()

if build:
    upload_path = None
    if upload is not None:
        upload_path = Path(tempfile.mkdtemp(prefix="madison-upload-")) / Path(upload.name).name
        upload_path.write_bytes(upload.getvalue())
    s = Settings(company=company, competitors=competitors, sources=sources,
                 topic=None if topic == "all" else topic, question=question or "",
                 upload_path=str(upload_path) if upload_path else None,
                 upload_name=upload.name if upload is not None else None)
    with progress_area.container():
        bar = st.progress(0.0, text="Checking your choices")
    try:
        result = run(s, progress=lambda f, msg: bar.progress(min(max(f, 0.0), 1.0), text=msg),
                     reserve=reserver(visitor()))
        st.session_state.update(result=result, example=False, error=None)
        qa = result["qa"]
        log("build_done", status=result["status"], claims=f"{qa['claims_verified']}/{qa['claims_total']}",
            attempts=qa["attempt"], seconds=result["seconds"],
            flags=[c["brand"] for c in result["threat_checks"] if not c["ok"]], settings=settings_for_log(s))
    except FriendlyError as err:
        st.session_state.update(result=None, error=err)
        log("build_stopped", reason=err.title, settings=settings_for_log(s))
    except Exception:
        traceback.print_exc()
        st.session_state.update(result=None, error=FriendlyError(
            "Something went wrong on our side",
            "The brief couldn't be finished, and nothing was published.",
            "Press “Build my brief” again. If it happens twice, try fewer competitors or come back in a few minutes."))
        log("build_crashed", settings=settings_for_log(s))
    progress_area.empty()
elif example:
    try:
        st.session_state.update(result=json.loads(EXAMPLE.read_text(encoding="utf-8")), example=True, error=None)
        log("example_opened")
    except (OSError, ValueError):
        st.session_state.update(result=None, error=FriendlyError(
            "The example isn't available", "The saved example brief couldn't be opened.",
            "Press “Build my brief” to make a new one instead."))

# ---------------------------------------------------------------------------
# Output (right side)
# ---------------------------------------------------------------------------
def show_output():
    error = st.session_state.get("error")
    result = st.session_state.get("result")
    if error:
        st.html(render.error_view(error))
    elif result:
        show_result(result)
    else:
        st.html(render.empty_view())


def show_result(result):
    is_example = st.session_state.get("example", False)
    (html_name, html_bytes), (csv_name, csv_bytes) = render.downloads(result)
    tab_brief, tab_cards, tab_checks, tab_sources, tab_download = st.tabs(
        ["Brief", "Battlecards", "How it was checked", "Sources", "Download"])
    with tab_brief:
        st.html(render.brief_view(result, is_example))
    with tab_cards:
        st.html(render.battlecards_view(result))
    with tab_checks:
        st.html(render.checks_view(result))
    with tab_sources:
        st.html(render.sources_view(result))
    with tab_download:
        st.markdown("Take the brief with you. The HTML file opens in any browser and prints to PDF "
                    "(File → Print → Save as PDF). The CSV has every record with its AI labels.")
        st.download_button("Download the full brief (HTML, prints to PDF)", data=html_bytes, file_name=html_name,
                           mime="text/html", type="primary", on_click="ignore")
        st.download_button("Download the scored evidence (CSV for Excel or Sheets)", data=csv_bytes,
                           file_name=csv_name, mime="text/csv", on_click="ignore")
        st.markdown("**Plain-text version** to paste into an email, doc or Slack (copy button at the top right of the box):")
        st.code(render.plain_text(result), language=None, wrap_lines=True)


try:
    show_output()
except Exception:  # never show a stack trace to a visitor
    traceback.print_exc()
    st.session_state.update(result=None, error=None)
    st.error("Something went wrong while showing this page. Press “See an example brief” or “Build my brief” again.")

st.html(FOOTER)
