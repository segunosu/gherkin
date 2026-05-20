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

import requests
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI


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
        "model": "gpt-5.5",
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
            "clarifying_questions": {"type": "array", "items": {"type": "string"}},
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
    model_name = model or st.session_state.get("model", "gpt-5.5")
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
    for event in stream:
        d = (event.choices[0].delta.content or "") if event.choices else ""
        if not d: continue
        chunks.append(d); cc += len(d)
        if status_placeholder is not None and cc % 120 < len(d):
            status_placeholder.caption(f"⏳ {model_name} • {cc:,} chars received…")
    if status_placeholder is not None: status_placeholder.empty()
    return json.loads("".join(chunks))


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
    ws_count = len(st.session_state.get("saved_projects", []))
    ws_label = f"View workspace ({ws_count})" if ws_count else "View workspace"
    if st.button(ws_label, key="intro_workspace_btn"):
        st.session_state.page = "workspace"
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
                INVEST_SCHEMA, model="gpt-5.5", status_placeholder=progress,
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
            progress = st.empty(); progress.caption("⏳ Generating story, acceptance criteria and Gherkin…")
            try:
                st.session_state.final_artifacts = call_openai_structured(
                    client, GENERATE_SYSTEM_PROMPT, user_message, GENERATE_SCHEMA,
                    model="gpt-5.5", status_placeholder=progress,
                )
            except Exception as e:
                progress.empty(); st.error(f"OpenAI call failed: {e}")

    if st.session_state.final_artifacts:
        a = st.session_state.final_artifacts
        stage_header("04", "Implementation-ready artifacts")

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
                        model="gpt-5.4-mini",
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
                    model="gpt-5.4-mini",
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
else:
    page_workbench()
