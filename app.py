"""
INVEST -> Gherkin Pipeline (Teamsmiths AI)

A Streamlit tool that ingests raw business requirements, critiques them against
the INVEST criteria, captures SME clarifications, and emits implementation-ready
user stories + acceptance criteria + Gherkin scenarios + traceability stubs.

Built for AI-accelerated software delivery in regulated environments
(pensions, insurance, financial services). Brand-matched to Teamsmiths Deputee.ai.
"""

import base64
import json
import os
import re
import uuid

import requests
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# Single knob for the OpenAI model used across the app. gpt-5.4-mini ($0.75/$4.50
# per 1M tokens) is ~6-7x cheaper and faster than gpt-5.5 ($5/$30) while still
# handling INVEST critique, clarifications, Gherkin generation and test plans.
# Tune here: "gpt-5.5" for max quality, "gpt-5.4-nano" ($0.20/$1.25) for cheapest.
OPENAI_MODEL = "gpt-5.4-mini"


st.set_page_config(
    page_title="INVEST -> Gherkin - Teamsmiths AI",
    page_icon="\U0001F952",
    layout="wide",
    initial_sidebar_state="collapsed",
)


TEAMSMITHS_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 120" fill="none" preserveAspectRatio="xMinYMid meet" style="height:100%;width:auto;display:block;">
  <text x="10" y="55" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="48" fill="#4A90D9" letter-spacing="2">TEAM</text>
  <text x="10" y="105" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="48" fill="#4A90D9" letter-spacing="2">SMITHS</text>
  <rect x="270" y="12" width="90" height="90" rx="6" fill="#4A90D9"/>
  <text x="283" y="55" font-family="Arial Black, Arial, sans-serif" font-weight="900" font-size="36" fill="#0a0a0a">AI</text>
  <line x1="283" y1="68" x2="347" y2="68" stroke="#0a0a0a" stroke-width="4" stroke-linecap="round"/>
  <line x1="283" y1="80" x2="347" y2="80" stroke="#0a0a0a" stroke-width="4" stroke-linecap="round"/>
  <line x1="283" y1="92" x2="335" y2="92" stroke="#0a0a0a" stroke-width="4" stroke-linecap="round"/>
</svg>"""


DEFAULT_EXAMPLE = (
    "When a new employee joins, we need to check if they qualify for "
    "auto-enrolment and enrol them into the pension scheme. They should be "
    "enrolled if they are 22 or over, earn enough, and aren't already in a "
    "scheme. We also need to handle people who opt out."
)


def init_state():
    defaults = {
        "page": "intro",
        "theme": "dark",
        "raw_requirement": DEFAULT_EXAMPLE,
        "invest_result": None,
        "final_artifacts": None,
        "clarification_answers": {},
        "model": OPENAI_MODEL,
        "project_context": None,
        "saved_projects": [],
        "test_plan": None,
        "test_engine": "Claude (via prompt)",
        "current_user": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_state()


DARK_PALETTE = """
    --bg: #0b0d14;
    --bg-2: #0f121b;
    --fg: #e1e7ef;
    --fg-strong: #ffffff;
    --fg-muted: #94a3b8;
    --primary: #0080ff;
    --primary-hover: #1a8cff;
    --primary-soft: rgba(0, 128, 255, 0.12);
    --primary-fg: #ffffff;
    --card: #11141d;
    --card-2: #161a25;
    --border: #1f2330;
    --label: #6b7280;
    --success-bg: #052e16;  --success-fg: #4ade80;
    --warn-bg:    #422006;  --warn-fg:    #fbbf24;
    --danger-bg:  #450a0a;  --danger-fg:  #f87171;
"""

LIGHT_PALETTE = """
    --bg: #f8fafc;
    --bg-2: #ffffff;
    --fg: #0f172a;
    --fg-strong: #0b0d14;
    --fg-muted: #64748b;
    --primary: #0080ff;
    --primary-hover: #006fe0;
    --primary-soft: rgba(0, 128, 255, 0.10);
    --primary-fg: #ffffff;
    --card: #ffffff;
    --card-2: #f1f5f9;
    --border: #e2e8f0;
    --label: #475569;
    --success-bg: #dcfce7;  --success-fg: #166534;
    --warn-bg:    #fef3c7;  --warn-fg:    #92400e;
    --danger-bg:  #fee2e2;  --danger-fg:  #991b1b;
"""


CSS_RULES_TEMPLATE = """
#MainMenu, footer, .stDeployButton { display:none !important; }
header[data-testid="stHeader"] { display: none !important; height: 0 !important; min-height: 0 !important; }
section[data-testid="stSidebar"] { display:none !important; }

html, body, [data-testid="stAppViewContainer"], .main, .block-container, .stApp {
    background: var(--bg) !important;
    color: var(--fg) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
.block-container { padding: 24px 32px 48px 32px !important; max-width: 1200px !important; }
h1, h2, h3, h4, h5, h6 { color: var(--fg-strong) !important; font-family: inherit !important; letter-spacing: -0.01em; }
p, label, span, div { color: var(--fg); }

.ts-topbar { display:flex; align-items:center; justify-content:space-between; padding: 4px 0 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 32px; gap: 24px; }
.ts-topbar-left { display:flex; align-items:center; gap: 20px; min-width:0; }
svg.ts-logo-sm { display:block; height: 32px !important; width: 107px !important; opacity: 0.85; flex-shrink:0; overflow:visible; }
svg.ts-logo-lg { display:block; height: 72px !important; width: 240px !important; flex-shrink:0; overflow:visible; }
.ts-meta { display:flex; flex-direction:column; min-width:0; }
.ts-category { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: var(--primary); text-transform: uppercase; margin: 0; }
.ts-page-title { font-size: 15px; font-weight: 600; color: var(--fg-strong); margin: 2px 0 0 0; }

.ts-hero { padding: 32px 0 16px 0; max-width: 760px; }
.ts-hero-label { font-size: 12px; font-weight: 700; letter-spacing: 2px; color: var(--primary); text-transform: uppercase; margin: 24px 0 16px 0; }
.ts-hero-h1 { font-size: 56px; font-weight: 800; line-height: 1.05; color: var(--fg-strong) !important; margin: 0; }
.ts-hero-h1-accent { color: var(--primary) !important; }
.ts-hero-body { font-size: 18px; line-height: 1.6; color: var(--fg-muted) !important; margin: 24px 0 28px 0; max-width: 640px; }

.ts-section-h2 { font-size: 22px; font-weight: 700; color: var(--fg-strong) !important; margin: 56px 0 8px 0; }
.ts-section-sub { font-size: 14px; color: var(--fg-muted) !important; margin: 0 0 24px 0; max-width: 720px; line-height: 1.5; }

.ts-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; height: 100%; }
.ts-card-icon { width: 40px; height: 40px; background: var(--primary-soft); color: var(--primary); display:flex; align-items:center; justify-content:center; border-radius: var(--radius); margin-bottom: 16px; font-size: 18px; font-weight: 800; }
.ts-card-title { font-size: 16px; font-weight: 700; color: var(--fg-strong); margin: 0 0 8px 0; }
.ts-card-body { font-size: 13px; color: var(--fg-muted); line-height: 1.55; }

.stButton > button {
    background: var(--primary) !important;
    color: var(--primary-fg) !important;
    border: 1px solid var(--primary) !important;
    border-radius: var(--radius) !important;
    padding: 9px 18px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    box-shadow: none !important;
}
.stButton > button:hover { background: var(--primary-hover) !important; border-color: var(--primary-hover) !important; }
.stButton > button[kind="secondary"] {
    background: var(--card) !important;
    color: var(--fg) !important;
    border: 1px solid var(--border) !important;
}
.stButton > button[kind="secondary"]:hover { background: var(--card-2) !important; }

.ts-stage { display:flex; align-items:center; gap: 12px; margin: 36px 0 16px 0; }
.ts-stage-num { background: var(--primary); color: var(--primary-fg); width: 30px; height: 30px; border-radius: 50%; display:flex; align-items:center; justify-content:center; font-weight: 700; font-size: 13px; }
.ts-stage-title { font-size: 19px; font-weight: 700; color: var(--fg-strong); }

.v-pill { display:inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }
.v-pass    { background: var(--success-bg); color: var(--success-fg); }
.v-partial { background: var(--warn-bg);    color: var(--warn-fg); }
.v-fail    { background: var(--danger-bg);  color: var(--danger-fg); }

.criterion-grid { display:grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin: 12px 0 8px 0; }
.criterion { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; text-align: center; }
.criterion-name { font-size: 11px; font-weight: 600; color: var(--fg-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }

.verdict-banner { padding: 14px 18px; border-radius: var(--radius-lg); margin: 8px 0 16px 0; display:flex; align-items:center; gap:12px; border: 1px solid var(--border); }
.verdict-ready   { background: var(--success-bg); color: var(--success-fg); }
.verdict-clarify { background: var(--warn-bg);    color: var(--warn-fg); }
.verdict-reject  { background: var(--danger-bg);  color: var(--danger-fg); }

textarea, input[type="text"], input[type="password"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    color: var(--fg) !important;
    border-radius: var(--radius) !important;
    font-family: 'Inter', sans-serif !important;
}
textarea:focus, input:focus { border-color: var(--primary) !important; box-shadow: 0 0 0 2px var(--primary-soft) !important; }
.stSelectbox > div > div { background: var(--card) !important; border: 1px solid var(--border) !important; color: var(--fg) !important; }

.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); background: transparent; }
.stTabs [data-baseweb="tab"] {
    background: transparent !important; color: var(--fg-muted) !important;
    border-radius: var(--radius) var(--radius) 0 0;
    padding: 8px 16px; border: none !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] { color: var(--fg-strong) !important; border-bottom: 2px solid var(--primary) !important; }

[data-testid="stExpander"] { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
[data-testid="stExpander"] details { background: var(--card) !important; }
[data-testid="stExpander"] details > summary,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] { background: var(--card) !important; color: var(--fg-strong) !important; }
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div { color: var(--fg-strong) !important; }
[data-testid="stExpander"] > div { background: var(--card) !important; }
[data-testid="stExpanderDetails"] { background: var(--card) !important; }
[data-testid="stExpanderToggleIcon"] svg { fill: var(--fg-strong) !important; color: var(--fg-strong) !important; }

.stCodeBlock, pre { background: var(--card-2) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
.stCodeBlock code, pre code { color: var(--fg) !important; }

[data-testid="stCaptionContainer"], .stCaption { color: var(--fg-muted) !important; }
hr { border-color: var(--border) !important; }

@media (max-width: 720px) {
    .block-container { padding: 16px 16px 32px 16px !important; }
    .ts-topbar { flex-direction: column; align-items: flex-start !important; gap: 12px; padding: 12px 0; }
    .ts-topbar-left { flex-wrap: wrap; gap: 12px; }
    .ts-hero-h1 { font-size: 36px !important; }
    .ts-hero-body { font-size: 16px !important; }
    .ts-card { padding: 16px !important; }
    .criterion-grid { grid-template-columns: repeat(3, 1fr) !important; }
}
"""


def render_theme():
    if st.session_state.get("_injected_theme") == st.session_state.theme:
        return
    st.session_state["_injected_theme"] = st.session_state.theme
    palette = DARK_PALETTE if st.session_state.theme == "dark" else LIGHT_PALETTE
    css_body = ":root {\n" + palette + "\n    --radius: 6px;\n    --radius-lg: 10px;\n}\n" + CSS_RULES_TEMPLATE
    import json as _json
    css_json = _json.dumps(css_body)
    components.html(
        '<script>(function(){'
        'const css = ' + css_json + ';'
        'const p = window.parent.document;'
        'let s = p.getElementById("ts-injected-styles"); if (s) s.remove();'
        's = p.createElement("style"); s.id = "ts-injected-styles"; s.innerHTML = css; p.head.appendChild(s);'
        'if (!p.getElementById("ts-injected-fonts")) {'
        'const l = p.createElement("link"); l.id = "ts-injected-fonts"; l.rel = "stylesheet";'
        'l.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap";'
        'p.head.appendChild(l);'
        '}'
        '})();</script>',
        height=0,
        width=0,
    )


render_theme()


def render_topbar(scope: str):
    is_intro = scope == "intro"
    logo_class = "ts-logo-lg" if is_intro else "ts-logo-sm"
    if is_intro:
        meta_html = '<div class="ts-meta"><span class="ts-category">BDD for regulated delivery</span></div>'
    else:
        meta_html = '<div class="ts-meta"><span class="ts-category">INVEST &rarr; GHERKIN</span><span class="ts-page-title">Workbench</span></div>'

    sized_svg = TEAMSMITHS_LOGO_SVG.replace('<svg ', f'<svg class="{logo_class}" ', 1)
    nav_cols = st.columns([6, 1.6, 1])
    with nav_cols[0]:
        st.markdown(
            f'<div class="ts-topbar"><div class="ts-topbar-left">'
            f'{sized_svg}{meta_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with nav_cols[1]:
        if is_intro:
            if st.button("Open Workbench  →", key="nav_to_wb", use_container_width=True, type="primary"):
                st.session_state.page = "workbench"
                st.rerun()
        else:
            if st.button("← Back to intro", key="nav_to_intro", use_container_width=True):
                st.session_state.page = "intro"
                st.rerun()
    with nav_cols[2]:
        is_dark = st.session_state.theme == "dark"
        label = "☀ Light" if is_dark else "☽ Dark"
        if st.button(label, key="theme_btn", use_container_width=True):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()


INVEST_SYSTEM_PROMPT = """You are a senior Product Owner critiquing a business requirement for an AI-enabled software delivery team operating in a regulated environment (most likely pensions, insurance, or financial services).

Apply the INVEST criteria rigorously:
- Independent: Can the story stand alone, or does it bundle multiple workflows that should be separated?
- Negotiable: Is intent clear without being over-specified into a fixed solution?
- Valuable: Is the value owner identifiable, and is the business outcome clear?
- Estimable: Are there ambiguities (terminology, thresholds, timing) that would block engineering from sizing the work?
- Small: Could this be delivered in a single sprint, or does scope force a split?
- Testable: Could a tester write unambiguous pass/fail criteria from this requirement today?

For each criterion, return PASS, PARTIAL, or FAIL with a specific reason. Quote the ambiguous phrase where relevant.

Then surface domain ambiguities: undefined terminology, missing thresholds, regulatory references that should be cited, timing/boundary cases that aren't handled, or reference data not specified.

Then generate clarifying questions the PO should put to the SME. Be specific - vague questions get vague answers. For EACH clarifying question, also produce:
  - why_it_matters: one short line describing which downstream artifact (AC, Gherkin scenarios, traceability) is steered by the answer
  - candidate_answers: 3 to 5 ranked candidate answers, ordered most-likely-correct first. Each candidate must include:
      * answer: the candidate answer itself, written as the PO would write it
      * rationale: 1-2 sentences on why this is a reasonable answer in the relevant domain
      * tradeoff: what this answer makes harder or constrains later
      * assumption: what this answer takes for granted about the domain or data
      * downstream_impact: which specific AC field, Gherkin scenario, or traceability item this answer will set
      * industry_norm: "standard" (TPR/equivalent-regulator default), "common" (frequent variant), or "non_standard" (deliberate departure)

IMPORTANT: clarifying_questions MUST be an array of objects (each with question/why_it_matters/candidate_answers), NEVER an array of strings.

CROSS-QUESTION CONSISTENCY: rank candidates so that the ordinally-first candidate of each question is mutually consistent across questions. If Q1's top candidate scopes the story narrowly (e.g. "eligible jobholders only"), then Q2's top candidate must NOT contradict it (e.g. would prefer "no postponement, defer to a separate story" over "use postponement window"). Flag any candidate that is inconsistent with the most-likely answers to earlier questions with its industry_norm set to "non_standard".

If the story bundles multiple concerns, propose a split (separate stories named with crisp titles).

Overall verdict:
- READY if no FAILs and no critical ambiguities
- NEEDS_CLARIFICATION if PARTIALs / minor ambiguities the PO can resolve
- REJECT if FAILs require structural change (split, rewrite, missing inputs)

Be terse and concrete. No filler."""

INVEST_SCHEMA = {
    "name": "invest_critique",
    "schema": {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": ["Independent", "Negotiable", "Valuable", "Estimable", "Small", "Testable"]},
                        "verdict": {"type": "string", "enum": ["PASS", "PARTIAL", "FAIL"]},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["name", "verdict", "reasoning"],
                    "additionalProperties": False,
                },
            },
            "domain_ambiguities": {"type": "array", "items": {"type": "string"}},
            "clarifying_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "candidate_answers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "answer": {"type": "string"},
                                    "rationale": {"type": "string"},
                                    "tradeoff": {"type": "string"},
                                    "assumption": {"type": "string"},
                                    "downstream_impact": {"type": "string"},
                                    "industry_norm": {"type": "string", "enum": ["standard", "common", "non_standard"]},
                                },
                                "required": ["answer", "rationale", "tradeoff", "assumption", "downstream_impact", "industry_norm"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["question", "why_it_matters", "candidate_answers"],
                    "additionalProperties": False,
                },
            },
            "split_recommendation": {"type": "string"},
            "overall_verdict": {"type": "string", "enum": ["READY", "NEEDS_CLARIFICATION", "REJECT"]},
        },
        "required": ["criteria", "domain_ambiguities", "clarifying_questions", "split_recommendation", "overall_verdict"],
        "additionalProperties": False,
    },
    "strict": True,
}

GENERATE_SYSTEM_PROMPT = """You are a senior Product Owner finalising a user story for an AI-enabled engineering team in a regulated domain (likely pensions, insurance, or financial services).

Produce an implementation-ready artifact set:

1. Crisp story title in active voice.
2. User story in As/I need to/So that form.
3. Acceptance criteria as a list of rule-based, unambiguous, audit-friendly statements. Cite specific thresholds, formulas, reference data sources. Be explicit about boundary inclusivity (>= vs >).
4. Assumptions you've made because the SME didn't fully resolve.
5. Out-of-scope items that have been split off.
6. A complete Gherkin Feature block:
   - Feature header with intent
   - Background with shared thresholds/setup
   - 1 happy-path Scenario
   - 2-3 edge Scenarios (boundary, time/age, variable inputs)
   - 1 negative Scenario
   - 1 should-fail Scenario (data quality / error handling)
   - 1 Scenario Outline boundary table where a numeric threshold exists
   Annotate non-obvious scenarios with brief # comments.
7. Traceability stub: originating regulation, regulator guidance, reference-data version, linked downstream stories.

Treat SME clarifications as authoritative. If a clarification leaves residual ambiguity, surface under Assumptions - never invent regulations. Use [SQUARE BRACKETS] for placeholders the PO must fill. Be precise with thresholds, dates, currencies, and boundary inclusivity."""

GENERATE_SCHEMA = {
    "name": "story_artifacts",
    "schema": {
        "type": "object",
        "properties": {
            "story_title": {"type": "string"},
            "user_story": {
                "type": "object",
                "properties": {
                    "as_a": {"type": "string"},
                    "i_need_to": {"type": "string"},
                    "so_that": {"type": "string"},
                },
                "required": ["as_a", "i_need_to", "so_that"],
                "additionalProperties": False,
            },
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "out_of_scope": {"type": "array", "items": {"type": "string"}},
            "gherkin_feature": {"type": "string"},
            "traceability": {
                "type": "object",
                "properties": {
                    "originating_regulation": {"type": "string"},
                    "regulator_guidance": {"type": "string"},
                    "reference_data_version": {"type": "string"},
                    "linked_stories": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["originating_regulation", "regulator_guidance", "reference_data_version", "linked_stories"],
                "additionalProperties": False,
            },
        },
        "required": ["story_title", "user_story", "acceptance_criteria", "assumptions", "out_of_scope", "gherkin_feature", "traceability"],
        "additionalProperties": False,
    },
    "strict": True,
}


def get_client():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OpenAI API key not configured. Set the OPENAI_API_KEY environment variable to your actual sk-... key.")
        st.stop()
    if not api_key.startswith("sk-"):
        st.error("The OPENAI_API_KEY value doesn't look like an API key. It must start with 'sk-'.")
        st.stop()
    return OpenAI(api_key=api_key)


def call_openai_structured(client, system_prompt, user_message, schema, *, model=None, status_placeholder=None):
    model_name = model or st.session_state.get("model", OPENAI_MODEL)
    stream = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_schema", "json_schema": schema},
        stream=True,
    )
    chunks = []
    cc = 0
    finish_reason = None
    for event in stream:
        if not event.choices:
            continue
        choice = event.choices[0]
        if getattr(choice, "finish_reason", None):
            finish_reason = choice.finish_reason
        d = choice.delta.content or ""
        if not d: continue
        chunks.append(d); cc += len(d)
        if status_placeholder is not None and cc % 120 < len(d):
            status_placeholder.caption(f"⏳ {model_name} • {cc:,} chars received…")
    if status_placeholder is not None: status_placeholder.empty()
    raw = "".join(chunks).strip()
    if not raw:
        raise ValueError(f"The model returned no content (finish_reason={finish_reason}). Please try again.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        hint = " The response appears truncated - please try again." if finish_reason == "length" else ""
        raise ValueError(
            f"Could not parse the model response (finish_reason={finish_reason}, {cc:,} chars received).{hint} [{e}]"
        ) from e


def verdict_pill(verdict: str) -> str:
    cls = {"PASS": "v-pass", "PARTIAL": "v-partial", "FAIL": "v-fail"}[verdict]
    return f"<span class='v-pill {cls}'>{verdict}</span>"



def _render_user_strip():
    cu = st.session_state.get("current_user")
    cols = st.columns([4, 1, 1, 1])
    with cols[0]:
        if cu:
            badge = "Admin" if _is_admin(cu) else ("Approved" if _is_approved(cu) else "Pending")
            st.markdown(
                f'<div style="font-size:12px;color:var(--fg-muted);margin:-12px 0 18px 0;">'
                f'Signed in as <strong style="color:var(--fg);">{cu}</strong> '
                f'<span class="v-pill v-pass" style="margin-left:6px;font-size:10px;">{badge}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:12px;color:var(--fg-muted);margin:-12px 0 18px 0;">'
                'Not signed in. Token-consuming actions require admin-approved access.'
                '</div>',
                unsafe_allow_html=True,
            )
    with cols[1]:
        if cu:
            if st.button("Sign out", key="sign_out", use_container_width=True):
                st.session_state.current_user = None
                st.rerun()
        else:
            if st.button("Sign in", key="sign_in", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
    with cols[2]:
        if not cu:
            if st.button("Register", key="sign_register", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()
        elif _is_admin(cu):
            if st.button("Admin", key="admin_link", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()


def page_intro():
    render_topbar("intro")
    _render_user_strip()
    st.markdown(
        '<div class="ts-hero">'
        '<div class="ts-hero-label">INVEST &rarr; Gherkin Pipeline</div>'
        '<h1 class="ts-hero-h1">Stop generating bad stories.<br/>'
        '<span class="ts-hero-h1-accent">Start shipping testable ones.</span></h1>'
        '<p class="ts-hero-body">The requirements engine that critiques business intent against INVEST, '
        'surfaces domain ambiguities, captures SME clarifications, and emits Gherkin-ready, '
        'audit-traceable user stories - built for AI-accelerated delivery in regulated environments.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Primary CTA + pensions example
    cta_cols = st.columns([1.4, 1.6, 5])
    with cta_cols[0]:
        if st.button("Propose a raw requirement  →", type="primary", use_container_width=True, key="hero_cta_1"):
            st.session_state.page = "workbench"
            st.rerun()
    with cta_cols[1]:
        if st.button("+ Try pensions example", use_container_width=True, key="hero_cta_2"):
            st.session_state.raw_requirement = DEFAULT_EXAMPLE
            st.session_state.invest_result = None
            st.session_state.final_artifacts = None
            st.session_state.page = "workbench"
            st.rerun()

    # Workspace link
    nav_extra = st.columns([1.4, 1.6, 5])
    with nav_extra[0]:
        ws_count = len(st.session_state.get("saved_projects", []))
        ws_label = f"View workspace ({ws_count})" if ws_count else "View workspace"
        if st.button(ws_label, key="intro_workspace_btn", use_container_width=True):
            st.session_state.page = "workspace"
            st.rerun()
    with nav_extra[1]:
        if st.button("Product backlog board", key="intro_board_btn", use_container_width=True):
            st.session_state.page = "board"
            st.rerun()

    # Three project-mode options below the hero
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    st.markdown('<h2 class="ts-section-h2">Or pick a project mode</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-section-sub">PROPOSE is the public demo path. START and ADD are private utilities '
        '(orchestrating GitHub repos + Lovable/Replit scaffolds) for getting projects off the ground.</p>',
        unsafe_allow_html=True,
    )

    mode_cols = st.columns(3)
    mode_cards = [
        (
            "PROPOSE",
            "Raw business requirement",
            "Paste a messy requirement. Get INVEST critique with ranked candidate answers, then Gherkin + traceability. This is the live demo path.",
            "Open  →",
            "live",
        ),
        (
            "START",
            "New project",
            "Capture domain, glossary, regulatory references, success metrics. Tool creates the GitHub repo and offers one-click handoff to Lovable or Replit. Project context primes every subsequent refinement.",
            "Coming soon",
            "stub",
        ),
        (
            "ADD",
            "Feature to existing project",
            "Pull project context from GitHub (README, glossary, prior .feature files). The PROPOSE flow then runs with that context injected, so candidate answers and Gherkin stay consistent with the codebase.",
            "Coming soon",
            "stub",
        ),
    ]
    for i, (tag, title, body, btn_label, status) in enumerate(mode_cards):
        with mode_cols[i]:
            st.markdown(
                f'<div class="ts-card" style="display:flex;flex-direction:column;min-height:240px;">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
                f'<span class="v-pill v-pass" style="font-size:10px;">{tag}</span>'
                f'</div>'
                f'<div class="ts-card-title">{title}</div>'
                f'<div class="ts-card-body" style="flex:1;">{body}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if tag == "PROPOSE":
                if st.button("Open  ->", key=f"mode_btn_{i}", type="primary", use_container_width=True):
                    st.session_state.page = "workbench"
                    st.rerun()
            elif tag == "START":
                if st.button("Start a project  ->", key=f"mode_btn_{i}", type="primary", use_container_width=True):
                    st.session_state.page = "start"
                    st.rerun()
            elif tag == "ADD":
                if st.button("Load a project  ->", key=f"mode_btn_{i}", type="primary", use_container_width=True):
                    st.session_state.page = "add"
                    st.rerun()

    st.markdown('<h2 class="ts-section-h2">Why INVEST &rarr; Gherkin?</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-section-sub">Most requirements tools either auto-generate stories from raw text, or just structure typing. '
        'This one critiques first - because AI generation over rubbish inputs scales bad decisions faster than any human team can.</p>',
        unsafe_allow_html=True,
    )
    cards = [
        ("⚡", "Critique before generate", "INVEST is a quality gate, not a checklist. Stories that fail Estimable or Testable get flagged with specific reasons before any Gherkin is written."),
        ("⚑", "Domain ambiguity flags", "Undefined terms, missing thresholds, and unstated regulatory references are surfaced for the SME - the difference between AI-assisted and AI-substituted PO work."),
        ("⎙", "Audit-traceable output", "Every artifact carries provenance: originating regulation, regulator guidance, reference-data version, and links to downstream split stories."),
    ]
    cols = st.columns(3)
    for i, (icon, title, body) in enumerate(cards):
        with cols[i]:
            st.markdown(
                f'<div class="ts-card"><div class="ts-card-icon">{icon}</div>'
                f'<div class="ts-card-title">{title}</div>'
                f'<div class="ts-card-body">{body}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<h2 class="ts-section-h2">The pipeline</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-section-sub">Four stages from raw business intent to Jira-ready artifact. Each stage shows its working so a senior PO can challenge it.</p>',
        unsafe_allow_html=True,
    )
    pipeline = [
        ("01", "Paste raw requirement", "The messy version, as it arrives from the SME."),
        ("02", "INVEST critique", "Six criteria, PASS / PARTIAL / FAIL with reasons. Splits recommended."),
        ("03", "SME clarifications", "Domain ambiguities turned into targeted questions."),
        ("04", "Generate artifacts", "Story, AC, Gherkin (happy + edges + negatives + boundary table), traceability."),
    ]
    cols = st.columns(4)
    for i, (n, t, b) in enumerate(pipeline):
        with cols[i]:
            st.markdown(
                f'<div class="ts-card"><div class="ts-card-icon" style="font-weight:800;font-size:14px;">{n}</div>'
                f'<div class="ts-card-title">{t}</div>'
                f'<div class="ts-card-body">{b}</div></div>',
                unsafe_allow_html=True,
            )


def stage_header(num: str, title: str):
    st.markdown(
        f'<div class="ts-stage"><div class="ts-stage-num">{num}</div>'
        f'<div class="ts-stage-title">{title}</div></div>',
        unsafe_allow_html=True,
    )


def _with_project_context(user_msg):
    """If project_context is set, prepend a domain primer so the model is anchored."""
    ctx = st.session_state.get("project_context")
    if not ctx:
        return user_msg
    lines = ["[Project context]"]
    for k, label in [
        ("name", "Project"),
        ("domain", "Domain"),
        ("regulatory_references", "Regulatory references"),
        ("glossary", "Glossary"),
        ("stakeholders", "Stakeholders"),
        ("success_metric", "Success metric"),
    ]:
        v = ctx.get(k)
        if v:
            lines.append(f"{label}: {v}")
    lines.append("Use this context to sharpen INVEST candidate answers and Gherkin terminology.")
    lines.append("")
    return "\n".join(lines) + "\n" + user_msg


def page_workbench():
    render_topbar("workbench")

    # Voice input via Web Speech API (browser-native, no API cost)
    components.html(
        """
<div style='margin-bottom:6px;'>
  <button id='mic-btn' style='background:#0080ff;color:#fff;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;'>🎤 Speak the requirement</button>
  <span id='mic-status' style='margin-left:12px;color:#94a3b8;font-size:12px;'></span>
  <div id='mic-out' style='margin-top:6px;padding:8px 10px;background:#11141d;border:1px solid #1f2330;border-radius:6px;color:#e1e7ef;min-height:36px;display:none;font-size:13px;'></div>
  <button id='mic-copy' style='margin-top:6px;display:none;background:transparent;color:#0080ff;border:1px solid #1f2330;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px;'>Copy to clipboard</button>
</div>
<script>
const btn=document.getElementById('mic-btn'),st=document.getElementById('mic-status'),
out=document.getElementById('mic-out'),cp=document.getElementById('mic-copy');
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(!SR){btn.disabled=true;st.textContent='(browser does not support Web Speech)';}
else{let recog=null,recording=false,full='';
btn.addEventListener('click',()=>{if(!recording){recog=new SR();recog.continuous=true;recog.interimResults=true;recog.lang='en-GB';
full='';out.style.display='block';out.textContent='';cp.style.display='none';
recog.onresult=e=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const t=e.results[i][0].transcript;if(e.results[i].isFinal)full+=t+' ';else interim+=t;}out.textContent=full+interim;};
recog.onerror=e=>{st.textContent='Error: '+e.error;};
recog.onend=()=>{recording=false;btn.textContent='🎤 Speak the requirement';st.textContent='Done — copy then paste into the box below.';cp.style.display='inline-block';};
recog.start();recording=true;btn.textContent='⏹ Stop';st.textContent='Listening…';}else{recog.stop();}});
cp.addEventListener('click',()=>{navigator.clipboard.writeText(out.textContent.trim()).then(()=>{cp.textContent='✓ Copied';setTimeout(()=>cp.textContent='Copy to clipboard',1800);});});}
</script>
""",
        height=170,
    )

    stage_header("01", "Paste a raw business requirement")
    col_input, col_actions = st.columns([3, 1])
    with col_input:
        raw = st.text_area(
            "Requirement text",
            value=st.session_state.raw_requirement,
            height=140,
            label_visibility="collapsed",
        )
        st.session_state.raw_requirement = raw
    with col_actions:
        if st.button("↺ Pensions example", use_container_width=True):
            st.session_state.raw_requirement = DEFAULT_EXAMPLE
            st.session_state.invest_result = None
            st.session_state.final_artifacts = None
            st.session_state.clarification_answers = {}
            st.rerun()
        run_invest = st.button("▶ Run INVEST critique", type="primary", use_container_width=True)

    if run_invest:
        require_approved("invest")
        client = get_client()
        progress = st.empty(); progress.caption("⏳ Critiquing against INVEST… (uses OpenAI tokens)")
        try:
            st.session_state.invest_result = call_openai_structured(
                client, INVEST_SYSTEM_PROMPT,
                _with_project_context(f"Critique this requirement:\n\n{st.session_state.raw_requirement}"),
                INVEST_SCHEMA, model=OPENAI_MODEL, status_placeholder=progress,
            )
            st.session_state.final_artifacts = None
            st.session_state.clarification_answers = {}
        except Exception as e:
            progress.empty(); st.error(f"OpenAI call failed: {e}")

    if st.session_state.invest_result:
        result = st.session_state.invest_result
        stage_header("02", "INVEST critique")

        verdict = result["overall_verdict"]
        v_class = {"READY": "verdict-ready", "NEEDS_CLARIFICATION": "verdict-clarify", "REJECT": "verdict-reject"}[verdict]
        v_icon = {"READY": "●", "NEEDS_CLARIFICATION": "●", "REJECT": "●"}[verdict]
        v_label = {"READY": "Ready for development", "NEEDS_CLARIFICATION": "Needs clarification", "REJECT": "Reject - structural issue"}[verdict]
        st.markdown(
            f'<div class="verdict-banner {v_class}"><span style="font-size:20px;">{v_icon}</span>'
            f'<div><div style="font-weight:700;font-size:13px;letter-spacing:0.6px;text-transform:uppercase;">Overall verdict</div>'
            f'<div style="font-size:16px;font-weight:600;">{v_label}</div></div></div>',
            unsafe_allow_html=True,
        )

        grid_html = '<div class="criterion-grid">'
        for crit in result["criteria"]:
            grid_html += (
                f'<div class="criterion">'
                f'<div class="criterion-name">{crit["name"]}</div>'
                f'{verdict_pill(crit["verdict"])}'
                f'</div>'
            )
        grid_html += "</div>"
        st.markdown(grid_html, unsafe_allow_html=True)

        with st.expander("Reasoning per criterion", expanded=True):
            for crit in result["criteria"]:
                st.markdown(
                    f"**{crit['name']}** &nbsp; {verdict_pill(crit['verdict'])}",
                    unsafe_allow_html=True,
                )
                st.markdown(f"_{crit['reasoning']}_")
                st.markdown("")

        if result["domain_ambiguities"]:
            with st.expander("⚑ Domain ambiguity flags", expanded=True):
                for amb in result["domain_ambiguities"]:
                    st.markdown(f"- {amb}")

        if result["split_recommendation"]:
            with st.expander("✂ Splitting recommendation"):
                st.markdown(result["split_recommendation"])

        stage_header("03", "SME clarifications")
        st.caption("Each question carries 3-5 ranked candidate answers with reasoning. Pick one or type your own.")

        CUSTOM_LABEL = "✎ Type your own…"
        NORM_BADGES = {
            "standard": ("TPR-standard", "v-pass"),
            "common": ("common variant", "v-partial"),
            "non_standard": ("non-standard", "v-fail"),
        }

        answers = {}
        # Defensive: stale invest_result from before schema change may be list of strings.
        if result["clarifying_questions"] and isinstance(result["clarifying_questions"][0], str):
            st.warning("Old-schema data detected. Click ▶ Run INVEST critique above to refresh with candidate answers.")
            answers = {}
            for i, q_str in enumerate(result["clarifying_questions"]):
                prior = st.session_state.clarification_answers.get(q_str, "")
                if isinstance(prior, dict):
                    prior = prior.get("answer", "")
                answers[q_str] = st.text_area(f"**Q{i + 1}.** {q_str}", value=prior, key=f"clar_legacy_{i}", height=70)
            st.session_state.clarification_answers = answers
            return  # Skip the new-format loop entirely

        for i, q_obj in enumerate(result["clarifying_questions"]):
            q_text = q_obj["question"]
            candidates = q_obj["candidate_answers"]

            st.markdown(f"**Q{i + 1}.** {q_text}")
            if q_obj.get("why_it_matters"):
                st.markdown(
                    f"<div style='color:var(--fg-muted);font-size:12px;margin:-4px 0 8px 0;'>"
                    f"<em>Why this matters:</em> {q_obj['why_it_matters']}</div>",
                    unsafe_allow_html=True,
                )

            # Radio: numbered options for candidates + custom
            opt_labels = [f"{j + 1}. {c['answer']}" for j, c in enumerate(candidates)]
            opt_labels.append(CUSTOM_LABEL)

            prior = st.session_state.clarification_answers.get(q_text, {})
            prior_idx = prior.get("source_idx", 0) if isinstance(prior, dict) else 0
            if prior_idx >= len(opt_labels):
                prior_idx = 0

            choice = st.radio(
                f"answer_{i}",
                opt_labels,
                index=prior_idx,
                key=f"clar_radio_{i}",
                label_visibility="collapsed",
            )
            chosen_idx = opt_labels.index(choice)

            # Show the supporting card for the selected candidate
            if chosen_idx < len(candidates):
                c = candidates[chosen_idx]
                norm_label, norm_cls = NORM_BADGES.get(c.get("industry_norm", "common"), ("common variant", "v-partial"))
                st.markdown(
                    f"""<div style='background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px 18px;margin:4px 0 12px 0;'>
<div style='margin-bottom:8px;'><span class='v-pill {norm_cls}'>{norm_label}</span></div>
<div style='font-size:13px;color:var(--fg);line-height:1.55;'>
  <div style='margin-bottom:6px;'><strong style='color:var(--fg-muted);'>Why:</strong> {c['rationale']}</div>
  <div style='margin-bottom:6px;'><strong style='color:var(--fg-muted);'>Tradeoff:</strong> {c['tradeoff']}</div>
  <div style='margin-bottom:6px;'><strong style='color:var(--fg-muted);'>Assumption:</strong> {c['assumption']}</div>
  <div><strong style='color:var(--fg-muted);'>Downstream impact:</strong> {c['downstream_impact']}</div>
</div>
</div>""",
                    unsafe_allow_html=True,
                )
                answers[q_text] = {
                    "answer": c["answer"],
                    "source": "ai_candidate",
                    "source_idx": chosen_idx,
                    "candidate_meta": c,
                }
            else:
                # Custom override
                prior_custom = prior.get("answer", "") if isinstance(prior, dict) and prior.get("source") == "custom" else ""
                custom = st.text_area(
                    f"Type your answer for Q{i + 1}",
                    value=prior_custom,
                    key=f"clar_custom_{i}",
                    height=70,
                    label_visibility="collapsed",
                    placeholder="Type your own answer here…",
                )
                answers[q_text] = {
                    "answer": custom,
                    "source": "custom",
                    "source_idx": chosen_idx,
                    "candidate_meta": None,
                }

            st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

        st.session_state.clarification_answers = answers

        if st.button("Generate story + AC + Gherkin →", type="primary", use_container_width=True):
            require_approved("generate")
            client = get_client()
            def _fmt_answer(q, rec):
                if not isinstance(rec, dict):
                    return f"Q: {q}\nA: {rec or '(no answer - assume and surface under Assumptions)'}"
                ans = rec.get("answer") or "(no answer - assume and surface under Assumptions)"
                src_kind = rec.get("source", "custom")
                meta = rec.get("candidate_meta") or {}
                norm = meta.get("industry_norm", "")
                if src_kind == "ai_candidate":
                    return (
                        f"Q: {q}\nA: {ans}\n"
                        f"Source: AI-suggested candidate (industry_norm={norm})\n"
                        f"Rationale: {meta.get('rationale','')}\n"
                        f"Tradeoff locked in: {meta.get('tradeoff','')}\n"
                        f"Assumption: {meta.get('assumption','')}"
                    )
                return f"Q: {q}\nA: {ans}\nSource: PO free-text override"

            block = "\n\n".join(_fmt_answer(q, a) for q, a in answers.items())
            user_message = _with_project_context(
                f"Original requirement:\n{st.session_state.raw_requirement}\n\n"
                f"INVEST critique noted:\n"
                f"- Domain ambiguities: {'; '.join(result['domain_ambiguities']) or 'none'}\n"
                f"- Split recommendation: {result['split_recommendation'] or 'none'}\n\n"
                f"SME clarifications:\n{block}\n\n"
                f"Now produce the implementation-ready artifact set."
            )
            progress = st.empty(); progress.caption("⏳ Generating story, AC and Gherkin… gpt-5.5 reasons for ~15-20s before output streams, then writes the full feature (usually 45-60s total). A live character count appears below once it starts.")
            st.session_state["generate_error"] = None
            _artifacts = None
            _last_err = None
            for _attempt in range(2):  # one automatic retry on a transient stream/parse failure
                try:
                    _artifacts = call_openai_structured(
                        client, GENERATE_SYSTEM_PROMPT, user_message, GENERATE_SCHEMA,
                        model=OPENAI_MODEL, status_placeholder=progress,
                    )
                    break
                except Exception as e:
                    _last_err = e
                    if _attempt == 0:
                        progress.caption("⏳ First attempt did not return clean output - retrying once…")
            progress.empty()
            if _artifacts is not None:
                st.session_state.final_artifacts = _artifacts
                st.session_state["scroll_to_artifacts"] = True
            else:
                st.session_state["generate_error"] = f"Generation did not complete: {_last_err}"

    if st.session_state.get("generate_error"):
        st.error(st.session_state["generate_error"])
        st.caption("Tip: click Generate again - large requirements with many clarifications occasionally need a second pass.")

    if st.session_state.final_artifacts:
        a = st.session_state.final_artifacts
        stage_header("04", "Implementation-ready artifacts")

        # Auto-scroll to the freshly generated artifacts (once, not on later tab clicks)
        if st.session_state.get("scroll_to_artifacts"):
            st.session_state["scroll_to_artifacts"] = False
            components.html(
                '<script>(function(){'
                'const p = window.parent.document; let n = 0;'
                'const iv = setInterval(function(){'
                'const ts = p.querySelectorAll(".ts-stage-title");'
                'for (const t of ts){ if (t.textContent.trim() === "Implementation-ready artifacts"){'
                't.scrollIntoView({behavior:"smooth", block:"start"}); clearInterval(iv); return; } }'
                'if (++n > 20) clearInterval(iv);'
                '}, 100);'
                '})();</script>',
                height=0, width=0,
            )

        tab_story, tab_ac, tab_gherkin, tab_trace, tab_test, tab_export = st.tabs(
            ["User Story", "Acceptance Criteria", "Gherkin", "Traceability", "Test Plan", "Export"]
        )
        with tab_story:
            st.markdown(f"#### {a['story_title']}")
            st.markdown(f"**As** {a['user_story']['as_a']}")
            st.markdown(f"**I need to** {a['user_story']['i_need_to']}")
            st.markdown(f"**So that** {a['user_story']['so_that']}")
        with tab_ac:
            st.markdown("#### Acceptance criteria")
            for c in a["acceptance_criteria"]:
                st.markdown(f"- {c}")
            if a["assumptions"]:
                st.markdown("**Assumptions**")
                for x in a["assumptions"]:
                    st.markdown(f"- {x}")
            if a["out_of_scope"]:
                st.markdown("**Out of scope (split into separate stories)**")
                for x in a["out_of_scope"]:
                    st.markdown(f"- {x}")
        with tab_gherkin:
            st.code(a["gherkin_feature"], language="gherkin")
        with tab_trace:
            t = a["traceability"]
            st.markdown(f"**Originating regulation:** {t['originating_regulation']}")
            st.markdown(f"**Regulator guidance:** {t['regulator_guidance']}")
            st.markdown(f"**Reference data version:** {t['reference_data_version']}")
            st.markdown("**Linked downstream stories:**")
            for s in t["linked_stories"]:
                st.markdown(f"- {s}")
        with tab_test:
            st.markdown("#### Test Plan")
            st.caption(
                "Generate a structured test plan from the Gherkin scenarios. Choose where the tests should run — "
                "the plan adapts (assertions, fixtures, oracle choices) to the chosen engine."
            )
            engine = st.radio(
                "Execution engine",
                ["Claude (via prompt)", "OpenAI (via prompt)", "Manual (PO walks the team through)", "Replit + Cucumber", "Lovable preview"],
                horizontal=False,
                key="test_engine_radio",
                index=0,
            )
            st.session_state["test_engine"] = engine

            if st.button("Generate test plan", type="primary", key="gen_test_plan"):
                require_approved("testplan")
                client = get_client()
                tp_progress = st.empty()
                tp_progress.caption("⏳ Drafting test plan…")
                tp_prompt = (
                    "You are writing a test plan for an engineering team in a regulated domain. "
                    "Given the Gherkin feature below and the chosen execution engine, produce a concise test plan in markdown with: "
                    "(1) Coverage matrix (which scenario tests which rule), "
                    "(2) Engine-specific notes (fixtures, oracle, data needs) for the chosen engine, "
                    "(3) Risks & gaps the scenarios don\'t cover, "
                    "(4) Suggested next test additions ranked by risk. Be terse, structured, audit-friendly."
                )
                tp_user = (
                    f"Engine: {engine}\n\nGherkin feature:\n{a['gherkin_feature']}\n\n"
                    f"Acceptance criteria (for context):\n" + "\n".join(f"- {c}" for c in a["acceptance_criteria"])
                )
                try:
                    r = client.chat.completions.create(
                        model=OPENAI_MODEL,
                        messages=[{"role": "system", "content": tp_prompt}, {"role": "user", "content": _with_project_context(tp_user)}],
                        stream=True,
                    )
                    chunks = []
                    cc = 0
                    for ev in r:
                        d = (ev.choices[0].delta.content or "") if ev.choices else ""
                        if d:
                            chunks.append(d); cc += len(d)
                            if cc % 120 < len(d):
                                tp_progress.caption(f"⏳ gpt-5.4-mini • {cc:,} chars received…")
                    tp_progress.empty()
                    st.session_state["test_plan"] = "".join(chunks)
                except Exception as e:  # noqa: BLE001
                    tp_progress.empty()
                    st.error(f"Test plan generation failed: {e}")

            if st.session_state.get("test_plan"):
                st.markdown("---")
                st.markdown(st.session_state.get("test_plan", ""))

        with tab_export:
            ac_md = "\n".join([f"- {c}" for c in a["acceptance_criteria"]])
            assumptions_md = "\n".join([f"- {x}" for x in a["assumptions"]]) or "_None_"
            oos_md = "\n".join([f"- {x}" for x in a["out_of_scope"]]) or "_None_"
            linked_md = "\n".join([f"  - {s}" for s in a["traceability"]["linked_stories"]]) or "  - _None_"
            export_md = (
                f"# {a['story_title']}\n\n"
                f"**As** {a['user_story']['as_a']}\n"
                f"**I need to** {a['user_story']['i_need_to']}\n"
                f"**So that** {a['user_story']['so_that']}\n\n"
                f"## Acceptance criteria\n{ac_md}\n\n"
                f"## Assumptions\n{assumptions_md}\n\n"
                f"## Out of scope (split into separate stories)\n{oos_md}\n\n"
                f"## Gherkin\n```gherkin\n{a['gherkin_feature']}\n```\n\n"
                f"## Traceability\n"
                f"- Originating regulation: {a['traceability']['originating_regulation']}\n"
                f"- Regulator guidance: {a['traceability']['regulator_guidance']}\n"
                f"- Reference data version: {a['traceability']['reference_data_version']}\n"
                f"- Linked downstream stories:\n{linked_md}\n"
            )
            st.code(export_md, language="markdown")
            st.caption("Copy-paste ready for Jira / Azure DevOps / Confluence / Notion.")

            st.markdown("---")
            _splits = _split_titles(a)
            _pc = st.session_state.get("project_context") or {}
            _repo_url = _pc.get("url")
            _author = st.session_state.get("current_user") or "demo"
            if _splits:
                st.caption(
                    f"INVEST split detected: this story + {len(_splits)} split-off "
                    f"stor{'y' if len(_splits) == 1 else 'ies'}. Add them all so the whole "
                    "decomposition is tracked, not just this subset."
                )
            ab1, ab2, ab3 = st.columns([1.8, 2.4, 1.6])
            with ab1:
                if st.button("+ Add story only", type="primary", key="add_to_board"):
                    card = card_from_artifacts(a, created_by=_author, repo_url=_repo_url)
                    _board_save(card)
                    st.session_state["_board_msgs"] = [f"Added {card['title']} to the board."]
                    st.success("Added to the product backlog board.")
            with ab2:
                if _splits and st.button(f"+ Add story + {len(_splits)} split-offs", key="add_with_splits"):
                    card = card_from_artifacts(a, created_by=_author, repo_url=_repo_url)
                    _board_save(card)
                    made = 0
                    for _t in _splits:
                        _board_save(child_card_from_title(_t, parent=card, created_by=_author, repo_url=_repo_url))
                        made += 1
                    st.session_state["_board_msgs"] = [
                        f"Added {card['title']} + {made} split-off stories (each needs a PROPOSE pass) to the board."
                    ]
                    st.success(f"Added the story and {made} split-off stories to the board.")
            with ab3:
                if st.button("Open board", key="export_open_board"):
                    st.session_state.page = "board"
                    st.rerun()


# ============================================================
# GitHub helpers (used by START / ADD)
# ============================================================
GH_API = "https://api.github.com"


def _github_token():
    return os.environ.get("GITHUB_TOKEN", "").strip()


def _gh_headers():
    tok = _github_token()
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def github_create_repo(name, description, private=False):
    r = requests.post(
        f"{GH_API}/user/repos",
        headers=_gh_headers(),
        json={"name": name, "description": description, "private": private, "auto_init": False},
        timeout=20,
    )
    if r.status_code in (200, 201):
        return r.json()
    raise RuntimeError(f"Create repo failed ({r.status_code}): {r.text[:300]}")


def github_put_file(owner, repo, path, content, message):
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    r = requests.put(
        f"{GH_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_gh_headers(),
        json={"message": message, "content": encoded},
        timeout=20,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Put {path} failed ({r.status_code}): {r.text[:300]}")


def github_get_file(owner, repo, path):
    h = _gh_headers()
    h["Accept"] = "application/vnd.github.raw"
    r = requests.get(f"{GH_API}/repos/{owner}/{repo}/contents/{path}", headers=h, timeout=15)
    return r.text if r.status_code == 200 else None


def _parse_repo_url(url):
    m = re.search(r"github\.com[/:]([^/]+)/([^/\s]+?)(?:\.git)?(?:/|$)", url.strip())
    return (m.group(1), m.group(2)) if m else None


# ============================================================
# Page: START
# ============================================================
def page_start():
    render_topbar("workbench")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">START — new project</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-hero-body">Capture project context, create a GitHub repo with templated structure, optionally hand off to Lovable or Replit. Context primes every refinement that follows.</p>',
        unsafe_allow_html=True,
    )

    if not _github_token():
        st.error("GITHUB_TOKEN not configured. Add it to Replit Secrets to enable repo creation.")

    with st.form("start_form", clear_on_submit=False):
        name = st.text_input("Project name (becomes the GitHub repo name)", placeholder="acme-pensions-modernisation")
        c1, c2 = st.columns(2)
        with c1:
            domain = st.text_area("Domain / industry context", height=110, placeholder="UK pensions under TPR; auto-enrolment, drawdown…")
        with c2:
            regulatory = st.text_area("Regulatory references (one per line)", height=110, placeholder="Pensions Act 2008\nTPR Detailed Guidance No. 3\nFCA COBS 19")
        glossary = st.text_area(
            "Glossary terms (one per line, format: term — definition)",
            height=110,
            placeholder="Eligible jobholder — age ≥22 and <SPA, qualifying earnings ≥ trigger\nQualifying earnings — band £6,240–£50,270 (24/25)",
        )
        c3, c4 = st.columns(2)
        with c3:
            stakeholders = st.text_input("Stakeholders / SMEs", placeholder="Pensions PM (Jane Doe), Payroll lead, Compliance…")
        with c4:
            success_metric = st.text_input("Success metric", placeholder="Zero TPR enforcement actions in 12 months post-launch")
        c5, c6 = st.columns([2, 1])
        with c5:
            runtime = st.radio("Runtime handoff", ["None (just create the repo)", "Replit", "Lovable"], horizontal=True)
        with c6:
            private = st.checkbox("Make repo private", value=False)
        submitted = st.form_submit_button("Create GitHub repo  →", type="primary", use_container_width=True)

    if submitted:
        require_approved("start")
        if not _github_token():
            st.stop()
        nm = name.strip()
        if not nm:
            st.error("Project name required.")
            st.stop()
        progress = st.empty()
        try:
            progress.caption("⏳ Creating GitHub repo… (uses OpenAI tokens for arch advisory)")
            repo = github_create_repo(nm, description=f"Project: {nm}", private=private)
            owner = repo["owner"]["login"]
            url = repo["html_url"]

            project = {
                "name": nm,
                "domain": domain.strip(),
                "regulatory_references": regulatory.strip(),
                "glossary": glossary.strip(),
                "stakeholders": stakeholders.strip(),
                "success_metric": success_metric.strip(),
                "runtime": runtime,
            }

            progress.caption("⏳ Pushing /context/project.json…")
            github_put_file(owner, nm, "context/project.json", json.dumps(project, indent=2), "chore: project context")

            progress.caption("⏳ Pushing README + glossary…")
            readme = (
                f"# {nm}\n\n"
                f"**Domain:** {domain.strip()}\n\n"
                f"## Regulatory references\n{regulatory.strip()}\n\n"
                f"## Stakeholders\n{stakeholders.strip()}\n\n"
                f"## Success metric\n{success_metric.strip()}\n"
            )
            github_put_file(owner, nm, "README.md", readme, "chore: README")

            lines = ["# Glossary", ""]
            for line in glossary.splitlines():
                if "—" in line:
                    term, _, defn = line.partition("—")
                    lines.append(f"- **{term.strip()}** — {defn.strip()}")
            glossary_md = "\n".join(lines) if len(lines) > 2 else "# Glossary\n\n(None yet.)"
            github_put_file(owner, nm, "docs/glossary.md", glossary_md, "chore: glossary")

            github_put_file(owner, nm, "features/.gitkeep", "", "chore: features placeholder")

            # Auto-generate an advisory architecture-suggestion.md for the engineering team.
            # Non-fatal — failure here does not block repo creation.
            try:
                progress.caption("⏳ Drafting architecture-suggestion.md (advisory)…")
                arch_client = get_client()
                arch_system = (
                    "You are writing an ADVISORY architecture suggestion for the engineering team that will "
                    "pick up this newly-created project. The reader is an engineer, not a PO. Write a concise "
                    "markdown document (~400 words) covering: (1) data-model sketch (key entities and "
                    "relationships derived from the domain and glossary), (2) API shape suggestion (REST/RPC, "
                    "key endpoints), (3) hosting + DB defaults that fit the chosen runtime, (4) regulatory-"
                    "driven constraints inferred from the regulatory references (auditability, data residency, "
                    "retention, immutability where relevant), (5) integration touchpoints, (6) one explicit "
                    "domain-relevant risk callout. End with a 'Caveats' line explicitly stating this is an "
                    "AI-generated starting point the engineering team should challenge."
                )
                arch_user = (
                    f"Project: {nm}\n"
                    f"Domain: {domain.strip()}\n"
                    f"Regulatory references:\n{regulatory.strip()}\n"
                    f"Glossary terms:\n{glossary.strip()}\n"
                    f"Stakeholders: {stakeholders.strip()}\n"
                    f"Success metric: {success_metric.strip()}\n"
                    f"Chosen runtime: {runtime}\n"
                )
                arch_resp = arch_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": arch_system},
                        {"role": "user", "content": arch_user},
                    ],
                )
                arch_md = arch_resp.choices[0].message.content or ""
                if arch_md.strip():
                    github_put_file(
                        owner, nm,
                        "docs/architecture-suggestion.md",
                        arch_md,
                        "chore: AI advisory architecture suggestion",
                    )
            except Exception:  # noqa: BLE001
                pass

            st.session_state.project_context = {"owner": owner, "name": nm, "url": url, **project}
            # Track in backlog
            entry = {"owner": owner, "name": nm, "url": url, "domain": project.get("domain", "")}
            sp = st.session_state.saved_projects
            sp = [e for e in sp if e.get("url") != url]
            sp.insert(0, entry)
            st.session_state.saved_projects = sp[:20]
            progress.empty()
            st.success(f"✓ Repo created: {url}")
        except Exception as e:  # noqa: BLE001
            progress.empty()
            st.error(f"Failed: {e}")

    if st.session_state.get('project_context'):
        ctx = st.session_state.get('project_context') or {}
        st.markdown(
            f'<div class="ts-card" style="margin:16px 0;">'
            f'<div class="ts-card-title">Project context loaded</div>'
            f'<div class="ts-card-body">'
            f"<strong>{ctx.get('name')}</strong>"
            f" · <a href=\"{ctx.get('url', '#')}\" target=\"_blank\" style=\"color:var(--primary);\">{ctx.get('url', '')}</a><br>"
            f"<em>Domain:</em> {ctx.get('domain', '(none)')}"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        cols = st.columns([1.5, 1.5, 1, 5])
        with cols[0]:
            if st.button("Continue to workbench →", type="primary", key="start_to_wb"):
                st.session_state.page = "workbench"
                st.rerun()
        with cols[1]:
            rt = ctx.get("runtime", "")
            o, n = ctx.get("owner"), ctx.get("name")
            if rt == "Replit" and o and n:
                st.link_button("Import to Replit ↗", f"https://replit.com/github/{o}/{n}")
            elif rt == "Lovable" and o and n:
                st.link_button("Import to Lovable ↗", f"https://lovable.dev/?import={o}/{n}")
        with cols[2]:
            if st.button("← Back", key="start_back"):
                st.session_state.page = "intro"
                st.rerun()


# ============================================================
# Page: ADD
# ============================================================
def page_add():
    render_topbar("workbench")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">ADD — feature to existing project</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-hero-body">Pulls <code>context/project.json</code> from the GitHub repo. Loaded context primes INVEST critique and Gherkin generation thereafter.</p>',
        unsafe_allow_html=True,
    )

    if not _github_token():
        st.caption("Public repos work without a token. Private repos require GITHUB_TOKEN in Secrets.")

    repo_url = st.text_input("GitHub repo URL", placeholder="https://github.com/segunosu/acme-pensions-modernisation", key="add_url")
    c1, c2 = st.columns([1, 5])
    with c1:
        load = st.button("Load context →", type="primary", use_container_width=True)
    with c2:
        if st.button("← Back to intro", key="add_back"):
            st.session_state.page = "intro"
            st.rerun()

    if load:
        parsed = _parse_repo_url(repo_url or "")
        if not parsed:
            st.error("Couldn't parse owner/name from URL.")
            st.stop()
        owner, name = parsed
        progress = st.empty()
        progress.caption(f"⏳ Fetching {owner}/{name}/context/project.json…")
        try:
            content = github_get_file(owner, name, "context/project.json")
            progress.empty()
            if not content:
                st.error(f"No context/project.json in {owner}/{name}. Was the project created via START? Private repos need GITHUB_TOKEN.")
                st.stop()
            project = json.loads(content)
            st.session_state.project_context = {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}", **project}
            entry = {"owner": owner, "name": name, "url": f"https://github.com/{owner}/{name}", "domain": project.get("domain", "")}
            sp = st.session_state.saved_projects
            sp = [e for e in sp if e.get("url") != entry["url"]]
            sp.insert(0, entry)
            st.session_state.saved_projects = sp[:20]
            st.success(f"✓ Loaded: {project.get('name', name)}")
        except Exception as e:  # noqa: BLE001
            progress.empty()
            st.error(f"Failed: {e}")

    if st.session_state.get('project_context'):
        ctx = st.session_state.get('project_context') or {}
        st.markdown(
            f'<div class="ts-card" style="margin:16px 0;">'
            f'<div class="ts-card-title">Project context loaded</div>'
            f'<div class="ts-card-body"><strong>{ctx.get("name")}</strong><br><em>Domain:</em> {ctx.get("domain", "(none)")}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button("Continue to workbench →", type="primary", key="add_to_wb"):
            st.session_state.page = "workbench"
            st.rerun()




# ============================================================
# Page: WORKSPACE — backlog of loaded projects
# ============================================================
def page_workspace():
    render_topbar("workbench")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">Workspace</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-hero-body">Recently loaded projects. Click any to swap context and jump to the workbench.</p>',
        unsafe_allow_html=True,
    )

    projects = st.session_state.get("saved_projects", [])
    if not projects:
        st.info("No projects yet. Use START to create one, or ADD to load an existing GitHub repo.")
        c1, c2, c3 = st.columns([1, 1, 5])
        with c1:
            if st.button("+ Start a project", type="primary", use_container_width=True):
                st.session_state.page = "start"
                st.rerun()
        with c2:
            if st.button("Load via URL", use_container_width=True):
                st.session_state.page = "add"
                st.rerun()
        with c3:
            if st.button("← Back to intro", key="ws_back_empty"):
                st.session_state.page = "intro"
                st.rerun()
        return

    cols = st.columns(2)
    for i, p in enumerate(projects):
        col = cols[i % 2]
        with col:
            st.markdown(
                f'<div class="ts-card" style="margin-bottom:12px;">'
                f'<div class="ts-card-title">{p.get("name", "(unnamed)")}</div>'
                f'<div class="ts-card-body" style="margin-bottom:8px;">'
                f'<em>Domain:</em> {p.get("domain") or "(none)"}<br>'
                f'<a href="{p.get("url", "#")}" target="_blank" style="color:var(--primary);font-size:12px;">{p.get("url", "")}</a>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Load \u2192", key=f"ws_load_{i}", use_container_width=True):
                # Re-load from GitHub to ensure freshness
                owner, name = p.get("owner"), p.get("name")
                content = github_get_file(owner, name, "context/project.json")
                if content:
                    proj = json.loads(content)
                    st.session_state.project_context = {"owner": owner, "name": name, "url": p.get("url"), **proj}
                    st.session_state.page = "workbench"
                    st.rerun()
                else:
                    st.error(f"Couldn't reload context/project.json for {owner}/{name}.")

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
    cb1, cb2 = st.columns([1, 5])
    with cb1:
        if st.button("← Back to intro", key="ws_back"):
            st.session_state.page = "intro"
            st.rerun()


# ============================================================
# Access gate (MVP) — email + admin-approval, persisted in Replit DB
# ============================================================
from datetime import datetime as _dt

ADMIN_EMAIL = "segun.osu@teamsmiths.com"

# Replit DB if available, else in-memory fallback (for local dev)
try:
    from replit import db as _user_db  # type: ignore
    _USE_REPLIT_DB = True
except Exception:  # noqa: BLE001
    _user_db = {}
    _USE_REPLIT_DB = False


def _user_key(email):
    return f"user:{(email or '').lower().strip()}"


def _get_user(email):
    if not email:
        return None
    k = _user_key(email)
    raw = _user_db.get(k)
    if not raw:
        return None
    if isinstance(raw, (str, bytes)):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None
    return dict(raw)


def _set_user(email, data):
    k = _user_key(email)
    payload = json.dumps(data) if _USE_REPLIT_DB else data
    _user_db[k] = payload


def _list_users():
    items = []
    if _USE_REPLIT_DB:
        for k in list(_user_db.keys()):
            if k.startswith("user:"):
                u = _get_user(k.split(":", 1)[1])
                if u:
                    items.append(u)
    else:
        for k, v in _user_db.items():
            if k.startswith("user:") and isinstance(v, dict):
                items.append(v)
    items.sort(key=lambda u: u.get("registered_at", ""), reverse=True)
    return items


def _is_admin(email):
    return bool(email) and email.lower().strip() == ADMIN_EMAIL.lower()


def _is_approved(email):
    u = _get_user(email)
    return bool(u and u.get("status") == "approved") or _is_admin(email)


def require_approved(scope_key):
    """Gate a token-consuming action. Call inline before the OpenAI call."""
    cu = st.session_state.get("current_user")
    if _is_approved(cu):
        return True
    st.warning(
        "🔒 This action calls OpenAI and consumes tokens (typically a few cents). "
        "Sign in with an approved account before continuing."
    )
    c1, c2, c3 = st.columns([1, 1, 5])
    with c1:
        if st.button("Sign in", key=f"signin_{scope_key}"):
            st.session_state.page = "login"
            st.rerun()
    with c2:
        if st.button("Register", key=f"register_{scope_key}"):
            st.session_state.page = "register"
            st.rerun()
    st.stop()


def page_register():
    render_topbar("workbench")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">Request access</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-hero-body">Access lets you run INVEST critiques, generate Gherkin artifacts, and create projects. '
        'Each action calls OpenAI and costs a few cents per request. The admin reviews requests before approving.</p>',
        unsafe_allow_html=True,
    )

    with st.form("register_form", clear_on_submit=False):
        email = st.text_input("Email")
        name = st.text_input("Your name")
        reason = st.text_area("What will you use it for?", height=80, placeholder="Short note on intended use.")
        submitted = st.form_submit_button("Submit request →", type="primary", use_container_width=True)

    if submitted:
        if not email or "@" not in email:
            st.error("Provide a valid email address.")
            st.stop()
        existing = _get_user(email)
        auto = _is_admin(email)
        record = {
            "email": email.lower().strip(),
            "name": name.strip(),
            "reason": reason.strip(),
            "status": "approved" if auto else (existing.get("status") if existing else "pending"),
            "registered_at": (existing.get("registered_at") if existing else _dt.utcnow().isoformat()),
            "last_seen": _dt.utcnow().isoformat(),
        }
        _set_user(email, record)
        if auto:
            st.session_state.current_user = email.lower().strip()
            st.success("Admin account — auto-approved. You can use the workbench now.")
        else:
            st.success("Request submitted. You'll be able to sign in once the admin approves it.")

    if st.button("← Back to intro", key="reg_back"):
        st.session_state.page = "intro"
        st.rerun()


def page_login():
    render_topbar("workbench")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">Sign in</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="ts-hero-body">Enter your approved email. (Lightweight MVP gate — '
        'real auth with magic-links is a follow-up.)</p>',
        unsafe_allow_html=True,
    )
    with st.form("login_form"):
        email = st.text_input("Email")
        submitted = st.form_submit_button("Sign in →", type="primary", use_container_width=True)
    if submitted:
        e = (email or "").strip().lower()
        if _is_admin(e):
            # Auto-create + approve admin if not already
            existing = _get_user(e) or {}
            existing.update({"email": e, "status": "approved", "name": existing.get("name") or "Admin",
                             "registered_at": existing.get("registered_at") or _dt.utcnow().isoformat(),
                             "last_seen": _dt.utcnow().isoformat()})
            _set_user(e, existing)
            st.session_state.current_user = e
            st.success("Signed in as admin.")
            st.session_state.page = "intro"
            st.rerun()
        u = _get_user(e)
        if not u:
            st.error("No account for that email. Please register.")
            st.stop()
        if u.get("status") != "approved":
            st.warning(f"Account is **{u.get('status', 'unknown')}**. Awaiting admin approval.")
            st.stop()
        u["last_seen"] = _dt.utcnow().isoformat()
        _set_user(e, u)
        st.session_state.current_user = e
        st.success(f"Signed in as {e}.")
        st.session_state.page = "intro"
        st.rerun()
    if st.button("← Back to intro", key="login_back"):
        st.session_state.page = "intro"
        st.rerun()


def page_admin():
    render_topbar("workbench")
    cu = st.session_state.get("current_user")
    if not _is_admin(cu):
        st.error("Admin only.")
        if st.button("← Back", key="admin_back_no"):
            st.session_state.page = "intro"
            st.rerun()
        return
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">Admin — users</h1>', unsafe_allow_html=True)
    users = _list_users()
    pending = [u for u in users if u.get("status") == "pending"]
    if pending:
        st.markdown(f"#### Pending ({len(pending)})")
        for u in pending:
            with st.container():
                st.markdown(f'<div class="ts-card" style="margin-bottom:8px;">'
                            f'<strong>{u["email"]}</strong> — {u.get("name", "")}<br>'
                            f'<span style="color:var(--fg-muted);font-size:13px;">{u.get("reason", "(no reason)")}</span><br>'
                            f'<span style="color:var(--fg-muted);font-size:11px;">requested {u.get("registered_at", "")[:19]}</span>'
                            f'</div>', unsafe_allow_html=True)
                c1, c2, _ = st.columns([1, 1, 4])
                with c1:
                    if st.button("Approve", key=f"appr_{u['email']}", type="primary"):
                        u["status"] = "approved"
                        _set_user(u["email"], u)
                        st.rerun()
                with c2:
                    if st.button("Deny", key=f"deny_{u['email']}"):
                        u["status"] = "denied"
                        _set_user(u["email"], u)
                        st.rerun()

    st.markdown(f"#### All users ({len(users)})")
    for u in users:
        badge = {"approved": "v-pass", "pending": "v-partial", "denied": "v-fail"}.get(u.get("status", ""), "v-partial")
        st.markdown(f'<div style="margin:8px 0;font-size:13px;">'
                    f'<span class="v-pill {badge}">{u.get("status", "?")}</span> '
                    f'<strong>{u["email"]}</strong> · {u.get("name", "")} · '
                    f'last seen {u.get("last_seen", "—")[:19]}</div>', unsafe_allow_html=True)

    if st.button("← Back to intro", key="admin_back"):
        st.session_state.page = "intro"
        st.rerun()


# ============================================================
# Product backlog board — persistent Kanban + GitHub status sync
# Tenancy-lite: every card is scoped to a project so separate hobby
# projects keep separate boards. GitHub is the queue + audit trail.
# ============================================================
BOARD_COLUMNS = [
    ("backlog", "Backlog"),
    ("ready", "Ready"),
    ("doing", "Doing"),
    ("done", "Done"),
]
_BOARD_PREFIX = "board:card:"
READY_LABEL = "gherkin:ready"


def _project_scope():
    """Which board are we looking at? A loaded GitHub project, else a personal board."""
    pc = st.session_state.get("project_context") or {}
    if pc.get("owner") and pc.get("name"):
        return f"{pc['owner']}/{pc['name']}"
    cu = st.session_state.get("current_user") or "demo"
    return f"user:{cu}"


def _board_card_key(cid):
    return f"{_BOARD_PREFIX}{cid}"


def _board_save(card):
    card["updated_at"] = _dt.utcnow().isoformat()
    _user_db[_board_card_key(card["id"])] = json.dumps(card) if _USE_REPLIT_DB else card


def _board_get(cid):
    raw = _user_db.get(_board_card_key(cid))
    if not raw:
        return None
    if isinstance(raw, (str, bytes)):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None
    return dict(raw)


def _board_cards(scope=None):
    scope = scope or _project_scope()
    cards = []
    for k in list(_user_db.keys()):
        ks = str(k)
        if ks.startswith(_BOARD_PREFIX):
            c = _board_get(ks[len(_BOARD_PREFIX):])
            if c and c.get("scope") == scope and c.get("status") != "archived":
                cards.append(c)
    cards.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return cards


def _board_group_members(card):
    """All cards in the same split-story group: the in-scope parent + its split-off children.

    A standalone card returns just itself. Lets one repo (or status action) apply to the
    whole decomposition instead of forcing the same input on every child.
    """
    root_id = card.get("parent_id") or card.get("id")
    members, seen = [], set()
    for c in _board_cards(card.get("scope")):
        cid = c.get("id")
        if (cid == root_id or c.get("parent_id") == root_id) and cid not in seen:
            seen.add(cid)
            members.append(c)
    if card.get("id") not in seen:  # safety: always include the card itself
        members.append(card)
    return members


def _slugify(text, maxlen=48):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (s[:maxlen].strip("-")) or "feature"


def _artifacts_to_spec_md(a):
    ac_md = "\n".join(f"- {c}" for c in a.get("acceptance_criteria", []))
    assumptions_md = "\n".join(f"- {x}" for x in a.get("assumptions", [])) or "_None_"
    oos_md = "\n".join(f"- {x}" for x in a.get("out_of_scope", [])) or "_None_"
    t = a.get("traceability", {}) or {}
    linked_md = "\n".join(f"  - {s}" for s in t.get("linked_stories", [])) or "  - _None_"
    us = a.get("user_story", {}) or {}
    return (
        f"# {a.get('story_title', 'Untitled story')}\n\n"
        f"**As** {us.get('as_a', '')}\n"
        f"**I need to** {us.get('i_need_to', '')}\n"
        f"**So that** {us.get('so_that', '')}\n\n"
        f"## Acceptance criteria\n{ac_md}\n\n"
        f"## Assumptions\n{assumptions_md}\n\n"
        f"## Out of scope (split into separate stories)\n{oos_md}\n\n"
        f"## Gherkin\n```gherkin\n{a.get('gherkin_feature', '')}\n```\n\n"
        f"## Traceability\n"
        f"- Originating regulation: {t.get('originating_regulation', '')}\n"
        f"- Regulator guidance: {t.get('regulator_guidance', '')}\n"
        f"- Reference data version: {t.get('reference_data_version', '')}\n"
        f"- Linked downstream stories:\n{linked_md}\n"
    )


def card_from_artifacts(a, *, created_by, scope=None, repo_url=None):
    cid = uuid.uuid4().hex[:10]
    parsed = _parse_repo_url(repo_url) if repo_url else None
    now = _dt.utcnow().isoformat()
    return {
        "id": cid,
        "scope": scope or _project_scope(),
        "title": a.get("story_title", "Untitled story"),
        "status": "backlog",
        "spec_md": _artifacts_to_spec_md(a),
        "gherkin_feature": a.get("gherkin_feature", ""),
        "acceptance_criteria": a.get("acceptance_criteria", []),
        "repo_url": repo_url,
        "owner": parsed[0] if parsed else None,
        "repo": parsed[1] if parsed else None,
        "feature_path": None,
        "commit_sha": None,
        "issue_number": None,
        "issue_url": None,
        "status_check": None,
        "synced_at": None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


def _split_titles(a):
    """Unique, ordered list of split-off story titles from a critique/artifact."""
    t = (a.get("traceability", {}) or {})
    raw = list(a.get("out_of_scope", []) or []) + list(t.get("linked_stories", []) or [])
    seen, out = set(), []
    for x in raw:
        title = (x or "").strip()
        title = re.sub(r"^\s*\[?\s*story\s*\]?\s*[:\-\u2013\u2014]?\s*", "", title, flags=re.I)
        # strip a leading list-number marker like "001]", "1.", "2)", "3 -", "01:" (a bare
        # number with no terminator is left alone so titles like "2024 review" survive)
        title = re.sub(r"^\s*#?\d{1,3}\s*[\]\.\):\-\u2013\u2014]\s*", "", title).strip()
        key = title.lower()
        if title and key not in seen:
            seen.add(key)
            out.append(title)
    return out


def child_card_from_title(title, *, parent, created_by, scope=None, repo_url=None):
    """A backlog stub card for a split-off story, linked to its parent.

    Stubs carry no Gherkin yet (they need their own PROPOSE pass), so they are
    tracked on the board but cannot be marked Ready until refined.
    """
    cid = uuid.uuid4().hex[:10]
    parsed = _parse_repo_url(repo_url) if repo_url else None
    now = _dt.utcnow().isoformat()
    title = (title or "").strip()[:140]
    return {
        "id": cid,
        "scope": scope or _project_scope(),
        "title": title,
        "status": "backlog",
        "spec_md": (f"# {title}\n\n_Split off from **{parent.get('title', '')}** by the INVEST critique. "
                    "Open this card in PROPOSE to produce acceptance criteria + Gherkin before marking it Ready._\n"),
        "gherkin_feature": "",
        "acceptance_criteria": [],
        "repo_url": repo_url,
        "owner": parsed[0] if parsed else None,
        "repo": parsed[1] if parsed else None,
        "feature_path": None,
        "commit_sha": None,
        "issue_number": None,
        "issue_url": None,
        "status_check": None,
        "synced_at": None,
        "parent_id": parent.get("id"),
        "parent_title": parent.get("title"),
        "needs_refinement": True,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


# ---- GitHub queue helpers (issue = work item, .feature = spec, commit status = gate) ----
def _gh_get_sha(owner, repo, path):
    r = requests.get(f"{GH_API}/repos/{owner}/{repo}/contents/{path}", headers=_gh_headers(), timeout=15)
    if r.status_code == 200:
        try:
            return r.json().get("sha")
        except Exception:  # noqa: BLE001
            return None
    return None


def _gh_upsert_file(owner, repo, path, content, message):
    payload = {"message": message, "content": base64.b64encode((content or "").encode("utf-8")).decode("ascii")}
    sha = _gh_get_sha(owner, repo, path)
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{GH_API}/repos/{owner}/{repo}/contents/{path}", headers=_gh_headers(), json=payload, timeout=25)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Commit {path} failed ({r.status_code}): {r.text[:200]}")
    return (r.json().get("commit", {}) or {}).get("sha")


def _gh_ensure_label(owner, repo, name):
    """Create the label if it does not exist yet (so it can attach to an issue)."""
    try:
        requests.post(f"{GH_API}/repos/{owner}/{repo}/labels", headers=_gh_headers(),
                      json={"name": name, "color": "0e8a16",
                            "description": "Queued for the Gherkin delivery loop"}, timeout=20)
    except Exception:  # noqa: BLE001 — already-exists / transient is fine
        pass


def _gh_create_issue(owner, repo, title, body, labels):
    for _lb in labels:
        _gh_ensure_label(owner, repo, _lb)
    r = requests.post(f"{GH_API}/repos/{owner}/{repo}/issues", headers=_gh_headers(),
                      json={"title": title, "body": body, "labels": labels}, timeout=25)
    if r.status_code in (200, 201):
        d = r.json()
        num = d.get("number")
        # Belt-and-braces: ensure the labels actually attached (GitHub can drop
        # an inline label that did not exist at create time).
        if num and labels and not d.get("labels"):
            try:
                requests.post(f"{GH_API}/repos/{owner}/{repo}/issues/{num}/labels",
                              headers=_gh_headers(), json={"labels": labels}, timeout=20)
            except Exception:  # noqa: BLE001
                pass
        return num, d.get("html_url")
    raise RuntimeError(f"Create issue failed ({r.status_code}): {r.text[:200]}")


def _gh_set_issue_state(owner, repo, number, state):
    r = requests.patch(f"{GH_API}/repos/{owner}/{repo}/issues/{number}", headers=_gh_headers(),
                       json={"state": state}, timeout=20)
    return r.status_code == 200


def _gh_commit_state(owner, repo, ref):
    r = requests.get(f"{GH_API}/repos/{owner}/{repo}/commits/{ref}/status", headers=_gh_headers(), timeout=15)
    if r.status_code == 200:
        d = r.json()
        return d.get("state"), d.get("total_count", 0)
    return None, 0


def _board_publish(card):
    """Publish a card to the GitHub queue: commit the .feature + spec, open a ready-labelled issue."""
    if not _github_token():
        return ["No GITHUB_TOKEN — card moved locally; GitHub publish/sync disabled."]
    if not (card.get("owner") and card.get("repo")):
        return ["No repo attached — moved locally. Attach a GitHub repo on the card to publish to the queue."]
    owner, repo = card["owner"], card["repo"]
    slug = _slugify(card["title"])
    feat_path = f"features/{slug}-{card['id']}.feature"
    spec_path = f"features/{slug}-{card['id']}.md"
    notes = []
    try:
        sha = _gh_upsert_file(owner, repo, feat_path, card.get("gherkin_feature", ""),
                              f"gherkin: scenarios for {card['title']}")
        _gh_upsert_file(owner, repo, spec_path, card.get("spec_md", ""),
                        f"gherkin: spec for {card['title']}")
        card["feature_path"] = feat_path
        card["commit_sha"] = sha
        notes.append(f"Committed {feat_path}")
    except Exception as e:  # noqa: BLE001
        return [f"Commit failed: {e}"]
    if card.get("issue_number"):
        _gh_set_issue_state(owner, repo, card["issue_number"], "open")
        notes.append(f"Re-opened issue #{card['issue_number']}")
    else:
        ac = "\n".join(f"- [ ] {c}" for c in card.get("acceptance_criteria", [])) or "- [ ] (none specified)"
        body = (f"Auto-published from the Gherkin board.\n\n"
                f"**Scenarios:** `{feat_path}`  \n**Spec:** `{spec_path}`\n\n"
                f"### Acceptance criteria\n{ac}\n\n"
                f"---\n_When the scenarios pass, this issue closes and the board card moves to Done._")
        try:
            num, url = _gh_create_issue(owner, repo, f"[gherkin] {card['title']}", body, [READY_LABEL])
            card["issue_number"], card["issue_url"] = num, url
            notes.append(f"Opened issue #{num} ({READY_LABEL})")
        except Exception as e:  # noqa: BLE001
            notes.append(f"Issue create failed: {e}")
    card["status_check"] = "pending"
    card["synced_at"] = _dt.utcnow().isoformat()
    return notes


def _gh_find_loop_pr(owner, repo, issue_number):
    """Find the delivery-loop PR for an issue (head branch gherkin-loop/issue-N).

    Returns (pr_number, pr_url, head_sha) or (None, None, None). Uses the pulls
    API (PR read) so it works with the standard delivery-loop token scope.
    """
    branch = f"gherkin-loop/issue-{issue_number}"
    try:
        r = requests.get(f"{GH_API}/repos/{owner}/{repo}/pulls",
                         headers=_gh_headers(),
                         params={"state": "all", "head": f"{owner}:{branch}", "per_page": 5},
                         timeout=15)
        prs = r.json() if r.status_code == 200 else []
        if not isinstance(prs, list) or not prs:
            # Fallback: scan recent PRs for the head branch.
            r = requests.get(f"{GH_API}/repos/{owner}/{repo}/pulls",
                             headers=_gh_headers(), params={"state": "all", "per_page": 50}, timeout=15)
            prs = [p for p in (r.json() if r.status_code == 200 else [])
                   if isinstance(p, dict) and (p.get("head") or {}).get("ref") == branch]
        if prs:
            p = prs[0]
            return p.get("number"), p.get("html_url"), (p.get("head") or {}).get("sha")
    except Exception:  # noqa: BLE001
        pass
    return None, None, None


def _gh_latest_run_conclusion(owner, repo, sha):
    """Return (status, conclusion) of the latest GitHub Actions run for a commit.

    Uses the Actions API (actions:read), so no Checks/Statuses scope is needed.
    """
    try:
        r = requests.get(f"{GH_API}/repos/{owner}/{repo}/actions/runs",
                         headers=_gh_headers(), params={"head_sha": sha, "per_page": 1}, timeout=15)
        if r.status_code != 200:
            return None, None
        runs = (r.json() or {}).get("workflow_runs", [])
        if not runs:
            return None, None
        return runs[0].get("status"), runs[0].get("conclusion")
    except Exception:  # noqa: BLE001
        return None, None


def _board_poll(card):
    """Reflect the implementation PR's CI state onto the card (via the Actions API).

    Looks up the delivery-loop PR for the card's issue, reads the latest workflow
    run on the PR head, and maps it to the card's status badge. Does NOT auto-move
    to Done on green: merging a draft PR is a human step (attended).
    """
    if not (_github_token() and card.get("owner") and card.get("repo") and card.get("issue_number")):
        return None
    owner, repo, n = card["owner"], card["repo"], card["issue_number"]
    pr_num, pr_url, head_sha = _gh_find_loop_pr(owner, repo, n)
    if pr_num:
        card["pr_number"], card["pr_url"] = pr_num, pr_url
        if card.get("status") == "ready":
            card["status"] = "doing"  # a PR exists -> work is in progress
    if not head_sha:
        card["status_check"] = "none"
        return f"No implementation PR yet for issue #{n} (awaiting the delivery-loop routine)."
    status, conclusion = _gh_latest_run_conclusion(owner, repo, head_sha)
    if status is None:
        card["status_check"] = "none"
        return f"PR #{pr_num} open; no CI run found yet."
    if status != "completed":
        card["status_check"] = "pending"
        return f"PR #{pr_num}: tests {status}."
    if conclusion == "success":
        card["status_check"] = "success"
        return f"PR #{pr_num}: tests passing."
    card["status_check"] = "failure"
    return f"PR #{pr_num}: tests {conclusion}."


def _board_apply_status(card, new_status):
    old = card.get("status")
    have_gh = bool(card.get("owner") and card.get("repo") and _github_token())
    # Guard: a split-off stub with no Gherkin yet cannot be published to the queue.
    if new_status == "ready" and old != "ready" and not (card.get("gherkin_feature") or "").strip():
        return ["No Gherkin yet - open this split-off story in PROPOSE to produce AC + scenarios before marking it Ready."]
    card["status"] = new_status
    notes = []
    if new_status == "ready" and old != "ready":
        notes += _board_publish(card)
    elif new_status == "done" and have_gh and card.get("issue_number"):
        _gh_set_issue_state(card["owner"], card["repo"], card["issue_number"], "closed")
        notes.append(f"Closed issue #{card['issue_number']}")
    elif old == "done" and new_status != "done" and have_gh and card.get("issue_number"):
        _gh_set_issue_state(card["owner"], card["repo"], card["issue_number"], "open")
        notes.append(f"Re-opened issue #{card['issue_number']}")
    _board_save(card)
    return notes


def _status_badge(c):
    sc = c.get("status_check")
    if not sc:
        return ""
    m = {"success": ("v-pass", "tests ok"), "failure": ("v-fail", "tests x"),
         "pending": ("v-partial", "tests ..."), "none": ("v-partial", "no CI")}
    cls, txt = m.get(sc, ("v-partial", str(sc)))
    return f'<span class="v-pill {cls}" style="font-size:9px;">{txt}</span>'


def _render_board_card(c, order, can_edit):
    badge = _status_badge(c)
    links = ""
    if c.get("issue_url"):
        links += (f' &middot; <a href="{c["issue_url"]}" target="_blank" '
                  f'style="color:var(--primary);font-size:11px;">#{c.get("issue_number")}</a>')
    if c.get("pr_url"):
        links += (f' &middot; <a href="{c["pr_url"]}" target="_blank" '
                  f'style="color:var(--primary);font-size:11px;">PR #{c.get("pr_number")}</a>')
    refine = ""
    if c.get("needs_refinement") or not (c.get("gherkin_feature") or "").strip():
        refine = '<span class="v-pill v-partial" style="font-size:9px;">needs refinement</span> '
    parent = ""
    if c.get("parent_title"):
        parent = (f'<div style="margin-top:5px;font-size:10px;color:var(--fg-muted);">'
                  f'↳ split from: {c["parent_title"]}</div>')
    st.markdown(
        f'<div class="ts-card" style="padding:12px;margin-bottom:8px;">'
        f'<div style="font-size:13px;font-weight:600;color:var(--fg-strong);line-height:1.35;">{c["title"]}</div>'
        f'<div style="margin-top:6px;">{refine}{badge}{links}</div>'
        f'{parent}'
        f'</div>',
        unsafe_allow_html=True,
    )
    with st.expander("details"):
        st.markdown(f"**Repo:** {c.get('repo_url') or '_none attached_'}")
        if can_edit:
            _repo_now = c.get("repo_url") or ""
            # Key includes the current URL so the field always reflects the card's real
            # repo (Streamlit otherwise keeps a stale widget value after propagation).
            new_url = st.text_input("GitHub repo URL", value=_repo_now,
                                    key=f"repo_{c['id']}_{_repo_now or 'none'}",
                                    placeholder="https://github.com/you/project")
            _group = _board_group_members(c)
            if len(_group) > 1:
                st.caption(f"One repo for the whole story - entering a URL applies it to this card + its {len(_group) - 1} split-off(s).")
            if st.button("Save repo", key=f"saverepo_{c['id']}"):
                _url = (new_url or "").strip()
                parsed = _parse_repo_url(_url) if _url else None
                if _url and not parsed:
                    st.session_state["_board_msgs"] = ["Couldn't parse owner/name from that URL - nothing changed."]
                elif not _url:
                    # Empty save detaches THIS card only - never silently wipes the whole story.
                    c["repo_url"] = None; c["owner"] = None; c["repo"] = None
                    _board_save(c)
                    st.session_state["_board_msgs"] = ["Repo detached from this card (siblings untouched)."]
                else:
                    for _m in _group:
                        _m["repo_url"] = _url; _m["owner"] = parsed[0]; _m["repo"] = parsed[1]
                        _board_save(_m)
                    st.session_state["_board_msgs"] = (
                        [f"Repo applied to this story + {len(_group) - 1} split-off card(s)."]
                        if len(_group) > 1 else ["Repo saved."]
                    )
                st.rerun()
        if c.get("acceptance_criteria"):
            st.markdown("**Acceptance criteria**")
            for ac in c.get("acceptance_criteria", []):
                st.markdown(f"- {ac}")
        if c.get("gherkin_feature"):
            st.code(c["gherkin_feature"], language="gherkin")
        if c.get("feature_path"):
            st.caption(f"queued at {c['feature_path']}")
        if can_edit:
            idx = order.index(c["status"]) if c.get("status") in order else 0
            labels = dict(BOARD_COLUMNS)
            if idx > 0 and st.button("Move to " + labels[order[idx - 1]], key=f"left_{c['id']}"):
                st.session_state["_board_msgs"] = _board_apply_status(c, order[idx - 1])
                st.rerun()
            if idx < len(order) - 1 and st.button("Move to " + labels[order[idx + 1]], key=f"right_{c['id']}"):
                st.session_state["_board_msgs"] = _board_apply_status(c, order[idx + 1])
                st.rerun()
            if st.button("Archive", key=f"arch_{c['id']}"):
                c["status"] = "archived"
                _board_save(c)
                st.rerun()
        else:
            st.caption("Sign in (approved) to move or publish cards.")


def page_board():
    render_topbar("workbench")
    scope = _project_scope()
    pretty = scope.replace("user:", "personal - ")
    st.markdown('<h1 class="ts-hero-h1" style="font-size:36px;">Product backlog board</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="ts-hero-body">Persistent board for <strong>{pretty}</strong>. '
        'Cards flow Backlog -> Ready -> Doing -> Done. Marking a card <em>Ready</em> publishes its '
        'scenarios + a <code>gherkin:ready</code> issue to GitHub - the queue a scheduled routine picks up.</p>',
        unsafe_allow_html=True,
    )

    cu = st.session_state.get("current_user")
    can_edit = _is_approved(cu)

    ctrl = st.columns([1.1, 1.6, 1.4, 4])
    with ctrl[0]:
        if st.button("Back to intro", key="board_back"):
            st.session_state.page = "intro"
            st.rerun()
    with ctrl[1]:
        if can_edit and st.button("Sync from GitHub", key="board_sync"):
            msgs = []
            for c in _board_cards(scope):
                if c.get("status") in ("ready", "doing"):
                    m = _board_poll(c)
                    if m:
                        _board_save(c)
                        msgs.append(f"{c['title']}: {m}")
            st.session_state["_board_msgs"] = msgs or ["Nothing to sync."]
            st.rerun()
    with ctrl[2]:
        if not can_edit:
            if st.button("Sign in", key="board_signin"):
                st.session_state.page = "login"
                st.rerun()

    for m in st.session_state.pop("_board_msgs", []):
        st.caption("- " + m)

    if not _github_token():
        st.info("GITHUB_TOKEN not set - cards persist and move locally, but GitHub publish/sync is off.")

    cards = _board_cards(scope)
    if not cards:
        st.info("No cards yet. Generate artifacts in the workbench, then click Add to product backlog.")
        if st.button("Open workbench", key="board_to_wb", type="primary"):
            st.session_state.page = "workbench"
            st.rerun()
        return

    cols = st.columns(len(BOARD_COLUMNS))
    order = [k for k, _ in BOARD_COLUMNS]
    for ci, (status_key, label) in enumerate(BOARD_COLUMNS):
        with cols[ci]:
            col_cards = [c for c in cards if c.get("status") == status_key]
            st.markdown(
                f'<div style="font-weight:700;color:var(--fg-strong);border-bottom:2px solid var(--primary);'
                f'padding-bottom:6px;margin-bottom:12px;">{label} '
                f'<span style="color:var(--fg-muted);font-weight:500;">{len(col_cards)}</span></div>',
                unsafe_allow_html=True,
            )
            for c in col_cards:
                _render_board_card(c, order, can_edit)



if st.session_state.page == "intro":
    page_intro()
elif st.session_state.page == "start":
    page_start()
elif st.session_state.page == "add":
    page_add()
elif st.session_state.page == "workspace":
    page_workspace()
elif st.session_state.page == "register":
    page_register()
elif st.session_state.page == "login":
    page_login()
elif st.session_state.page == "admin":
    page_admin()
elif st.session_state.page == "board":
    page_board()
else:
    page_workbench()
