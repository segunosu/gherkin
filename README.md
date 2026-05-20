# INVEST → Gherkin Pipeline

A lightweight tool that turns raw business requirements into INVEST-passed, Gherkin-ready, audit-traceable user stories.

Built for AI-accelerated software delivery in regulated environments (pensions, insurance, financial services). Single-file Streamlit app, hosted on Replit, calls OpenAI GPT-5.5 with strict JSON schemas.

---

## What it does

A 4-stage pipeline:

1. **Paste** a raw business requirement (the messy kind that lands from an SME).
2. **INVEST critique** — strict quality gate. Each of the six criteria gets a PASS / PARTIAL / FAIL verdict with a specific reason. Domain ambiguities are flagged. The tool generates clarifying questions for the SME and recommends story splits where bundling is detected.
3. **Clarify** — the PO captures SME answers inline.
4. **Generate** the implementation-ready artifact set: refined user story, acceptance criteria with thresholds, assumptions, out-of-scope items, a full Gherkin Feature block (happy path + edges + negatives + a should-fail + a boundary table), and a traceability stub (regulation, guidance, reference-data version, linked stories).

Output is one click away from being pasted into Jira / Azure DevOps / Confluence / Notion.

---

## Why this exists

The Senior PO role this was built for explicitly calls for using AI to accelerate analysis, refinement, documentation, and scenario generation — and for critically reviewing AI-generated outputs to ensure depth, accuracy, and domain quality. This tool puts the critique first (INVEST as the quality gate) so generation never runs over rubbish inputs. Traceability is built into every artifact for audit-friendly delivery.

---

## Deploy to Replit (≈ 5 minutes)

1. Create a new Replit from a Python template (or import this folder directly).
2. Drop these files into the Repl root:
   - `app.py`
   - `requirements.txt`
   - `.replit`
   - `.streamlit/config.toml`
3. Open **Tools → Secrets** and add:
   - Key: `OPENAI_API_KEY`
   - Value: your OpenAI key (needs access to `gpt-5.5` or `gpt-5.4-mini`)
4. Press **Run**. Replit installs the deps and starts Streamlit on port 8080.
5. Click the webview URL to open the tool. To share publicly, click **Deploy** in Replit and copy the autoscale URL.

If `OPENAI_API_KEY` isn't set as a Secret, you can paste it into the sidebar at runtime instead — useful for a demo where someone else uses their own key.

---

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

---

## Demo script (for the interview)

3 minutes, runs straight through. The default pensions example is deliberately bad so the tool gets to show its judgment.

1. **Open with the messy requirement on screen.** Read it aloud — it sounds plausible until you start picking at it.
2. **Click "Run INVEST critique".** Watch the criteria light up. Show the FAIL on Estimable + Testable.
3. **Read out one or two domain-ambiguity flags.** This is the key moment: the tool isn't just reformatting text, it's surfacing the regulatory terms the PO needs to nail down (eligible jobholder vs entitled worker, earnings trigger vs qualifying earnings band).
4. **Show the clarifying questions.** Note that this is the same conversation a senior PO would have with an SME — but pre-structured.
5. **Type quick answers to a couple of questions** (or leave blank — the tool will assume + flag).
6. **Click Generate.** Walk through the four tabs: Story, AC (point out the boundary inclusivity language — `>=` vs `>`), Gherkin (highlight the should-fail and the boundary table), Traceability.
7. **Open the Export tab.** "This goes straight into Jira."

Closing line: *"This is a sketch of how I'd plug into your AI-assisted delivery workflow on day one. The critique stage is what stops AI generation amplifying bad inputs — it's the part most teams skip."*

---

## What's deliberately out of scope (v1)

- Multi-story refinement at once
- Persistence (each session is in-memory only — fine for a demo, not for production)
- Auth / multi-user
- Tracker integration (the export is paste-ready, not API-pushed)
- Domain-specific rule libraries (currently the model brings its own pensions knowledge — for a production tool you'd want a curated reference-data layer)

All of these are natural v2 conversations to have with the hiring team.

---

## File structure

```
.
├── app.py                     # Single-file Streamlit app
├── requirements.txt           # streamlit, openai
├── .replit                    # Replit run config
├── .streamlit/config.toml     # Streamlit server + theme
└── README.md                  # This file
```

---

## Model notes

- Default model: `gpt-5.5` (released April 2026, supports native structured outputs against JSON schemas).
- Cheaper alternative: `gpt-5.4-mini` — useful for iteration without burning credit.
- Both calls use OpenAI's strict JSON schema mode, so the UI never has to defensively parse free-form text.
