"""
INVEST -> Gherkin Pipeline (Teamsmiths AI)

A Streamlit tool that ingests raw business requirements, critiques them against
the INVEST criteria, captures SME clarifications, and emits implementation-ready
user stories + acceptance criteria + Gherkin scenarios + traceability stubs.

Built for AI-accelerated software delivery in regulated environments
(pensions, insurance, financial services). Brand-matched to Teamsmiths Deputee.ai.
"""

import json
import os

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
[data-testid="stExpander"] summary { color: var(--fg-strong) !important; }

.stCodeBlock, pre { background: var(--card-2) !important; border: 1px solid var(--border) !important; border-radius: var(--radius) !important; }
.stCodeBlock code, pre code { color: var(--fg) !important; }

[data-testid="stCaptionContainer"], .stCaption { color: var(--fg-muted) !important; }
hr { border-color: var(--border) !important; }
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

Then generate clarifying questions the PO should put to the SME. Be specific - vague questions get vague answers.

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


def page_intro():
    render_topbar("intro")
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

    cta_cols = st.columns([1.4, 1.6, 5])
    with cta_cols[0]:
        if st.button("Open Workbench  →", type="primary", use_container_width=True, key="hero_cta_1"):
            st.session_state.page = "workbench"
            st.rerun()
    with cta_cols[1]:
        if st.button("+ Try pensions example", use_container_width=True, key="hero_cta_2"):
            st.session_state.raw_requirement = DEFAULT_EXAMPLE
            st.session_state.invest_result = None
            st.session_state.final_artifacts = None
            st.session_state.page = "workbench"
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


def page_workbench():
    render_topbar("workbench")

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
        client = get_client()
        progress = st.empty(); progress.caption("⏳ Critiquing against INVEST…")
        try:
            st.session_state.invest_result = call_openai_structured(
                client, INVEST_SYSTEM_PROMPT,
                f"Critique this requirement:\n\n{st.session_state.raw_requirement}",
                INVEST_SCHEMA, model="gpt-5.4-mini", status_placeholder=progress,
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
        st.caption("Answer what you can. Blanks are OK - the tool will assume and flag under Assumptions.")

        answers = {}
        for i, q in enumerate(result["clarifying_questions"]):
            prior = st.session_state.clarification_answers.get(q, "")
            answers[q] = st.text_area(f"**Q{i + 1}.** {q}", value=prior, key=f"clar_{i}", height=70)
        st.session_state.clarification_answers = answers

        if st.button("Generate story + AC + Gherkin →", type="primary", use_container_width=True):
            client = get_client()
            block = "\n\n".join(
                f"Q: {q}\nA: {a or '(no answer - make a sensible assumption and surface under Assumptions)'}"
                for q, a in answers.items()
            )
            user_message = (
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

        tab_story, tab_ac, tab_gherkin, tab_trace, tab_export = st.tabs(
            ["User Story", "Acceptance Criteria", "Gherkin", "Traceability", "Export"]
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


if st.session_state.page == "intro":
    page_intro()
else:
    page_workbench()
