# Briefproof

*Formerly "Madison Positioning Brief" (the working name in INFO7375 A6A). The web address keeps the old name.*

**Proof, not opinion.** Briefproof helps product marketers at data platform companies turn
competitor news into a fully sourced brief, so they can answer "How do we win?" with proof, not opinion.

## How to use it

1. Choose your company and the competitors you are up against (Databricks vs. Snowflake, Google BigQuery and
   Microsoft Fabric is set up by default).
2. Optional: pick a focus topic, type the question you need to answer, or add your own evidence as a CSV.
3. Press **Build my brief**. In under 30 seconds you get a positioning statement, three reasons you win, how to
   win against each competitor, risks to watch, a battlecard per competitor, and the public source behind every
   claim.

A brief is marked **Verified** only when every claim cites a real record from this run's evidence about the right
company. A claim that fails goes back to the AI once with the exact problem; if anything still fails, the brief is
labelled **Not verified** and the failing claims are marked ✗.

## How it works

| Step | What happens |
|---|---|
| Evidence | 217 checked public records (Google News, official company blogs, Hacker News), collected 28 Sep 2026 |
| Labels | Each record is labelled by gpt-4.1-mini: topic, sentiment, a 1-5 threat score from your company's side |
| Patterns | Rules group the records per company: average threat, high-threat moves, topic mix, near-duplicate stories counted once |
| Brief | gpt-4.1 writes the brief; every claim must cite record IDs |
| Check | Rules confirm every cited ID exists and belongs to the right company; threat ratings are compared with the evidence average |

Built by Cih-Lian Liao for INFO7375 (Northeastern University). Not affiliated with any company named here.
Briefs are written by AI from public sources and checked by rules; read the sources before you rely on a claim.

## Run it locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...   # needed to build new briefs; the example works without it
streamlit run streamlit_app.py
```
