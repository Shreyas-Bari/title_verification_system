"""
app.py — Streamlit Dashboard for Press Title Verification System
=================================================================
Modern, polished dark-mode interface generated from Stitch design tokens.

Features:
- Minimalist top bar with branding and live engine status indicator
- Elevated hero card for title submission
- Bento-grid status verdict and real-time metric cards
- Contextual alert badges for compliance violations
- High-fidelity styled data table for top-5 similarity analysis
- Guideline compliance checklist
- In-memory title registration for instant real-time re-verification
"""

import os
import streamlit as st
import pandas as pd
from matcher import TitleVerifier, VerificationResult
import rule_store


ADMIN_PINS = {"1234", "PRGI-ADMIN"}
RULE_CATEGORIES = [
    "Law Enforcement",
    "Defense & Armed Forces",
    "Government / Statutory",
    "Anti-Corruption",
    "Investigation Agencies",
    "National Symbols",
    "Custom",
]


def _show_rule_store_error() -> None:
    error = rule_store.get_last_error()
    if error:
        st.error(error)


def _after_rule_change(verifier: TitleVerifier) -> None:
    if hasattr(verifier, "reload_rules"):
        verifier.reload_rules()


def _render_admin_login() -> None:
    st.subheader("Protected PRGI Admin Panel")
    st.caption("Enter the admin credential to manage verification rules.")
    with st.form("admin_login_form"):
        pin = st.text_input("Admin PIN", type="password")
        submitted = st.form_submit_button("Unlock Admin Panel", type="primary")
    if submitted:
        if pin in ADMIN_PINS:
            st.session_state["prgi_admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid admin credential.")


def _render_rules_overview() -> None:
    detailed_words = rule_store.get_disallowed_words_detailed()
    prefixes = rule_store.get_prefixes()
    suffixes = rule_store.get_suffixes()
    _show_rule_store_error()

    col1, col2, col3 = st.columns(3)
    col1.metric("Disallowed Words", len(detailed_words))
    col2.metric("Prefixes", len(prefixes))
    col3.metric("Periodicity Terms", len(suffixes))


def _render_add_disallowed_word(verifier: TitleVerifier) -> None:
    st.subheader("Add Disallowed Word")
    with st.form("add_disallowed_word_form", clear_on_submit=True):
        word = st.text_input("Word or phrase", placeholder="e.g., classified")
        category = st.selectbox("Category", RULE_CATEGORIES)
        submitted = st.form_submit_button("Add to Blocklist", type="primary")

    if submitted:
        if rule_store.add_disallowed_word(word, category):
            _after_rule_change(verifier)
            st.success(f"Added '{word.strip().lower()}' to the blocklist.")
            if hasattr(st, "toast"):
                st.toast("Rule saved.")
        else:
            _show_rule_store_error()


def _render_active_disallowed_words(verifier: TitleVerifier) -> None:
    st.subheader("Active Disallowed Words")
    rows = rule_store.get_disallowed_words_detailed()
    search = st.text_input("Search words", key="admin_word_search")
    filtered_rows = [
        row for row in rows
        if not search
        or search.lower() in row.get("word", "").lower()
        or search.lower() in row.get("category", "").lower()
    ]

    if filtered_rows:
        display_df = pd.DataFrame(filtered_rows).rename(columns={
            "word": "Word",
            "category": "Category",
            "date_added": "Date Added",
        })
        st.dataframe(display_df, hide_index=True, use_container_width=True)
    else:
        st.info("No matching disallowed words found.")

    with st.expander("Remove a disallowed word"):
        words = [row["word"] for row in filtered_rows]
        selected_word = st.selectbox("Word", words, disabled=not words)
        confirm = st.checkbox("Confirm removal", key="confirm_word_removal")
        if st.button("Remove Selected Word", disabled=not words or not confirm):
            if rule_store.remove_disallowed_word(selected_word):
                _after_rule_change(verifier)
                st.success(f"Removed '{selected_word}'.")
                st.rerun()
            else:
                _show_rule_store_error()


def _render_token_manager(
    title: str,
    input_label: str,
    add_func,
    remove_func,
    get_func,
    verifier: TitleVerifier,
    key_prefix: str,
) -> None:
    st.subheader(title)
    active_items = sorted(get_func())
    st.dataframe(pd.DataFrame({input_label: active_items}), hide_index=True, use_container_width=True)

    add_col, remove_col = st.columns(2)
    with add_col:
        with st.form(f"add_{key_prefix}_form", clear_on_submit=True):
            value = st.text_input(f"Add {input_label.lower()}", key=f"add_{key_prefix}_input")
            submitted = st.form_submit_button(f"Add {input_label}")
        if submitted:
            if add_func(value):
                _after_rule_change(verifier)
                st.success(f"Added '{value.strip().lower()}'.")
                st.rerun()
            else:
                _show_rule_store_error()

    with remove_col:
        selected = st.selectbox(
            f"Remove {input_label.lower()}",
            active_items,
            disabled=not active_items,
            key=f"remove_{key_prefix}_select",
        )
        confirm = st.checkbox("Confirm removal", key=f"confirm_{key_prefix}_removal")
        if st.button(f"Remove {input_label}", disabled=not active_items or not confirm, key=f"remove_{key_prefix}_button"):
            if remove_func(selected):
                _after_rule_change(verifier)
                st.success(f"Removed '{selected}'.")
                st.rerun()
            else:
                _show_rule_store_error()


def _render_live_sandbox(verifier: TitleVerifier) -> None:
    st.subheader("Live Rule Sandbox")
    with st.form("rule_sandbox_form"):
        title = st.text_input("Enter a publication/title to test", placeholder="e.g., The Daily Hacker")
        submitted = st.form_submit_button("Test Rule", type="primary")

    if submitted:
        if not title.strip():
            st.warning("Enter a title to test.")
            return
        with st.spinner("Running the verification pipeline..."):
            result = verifier.verify(title.strip())
        if result.is_approved:
            st.success("PASS / ALLOWED")
        else:
            st.error("HARD REJECT / BLOCKED")
        if result.issues:
            st.write("Triggered rule details:")
            for issue in result.issues:
                st.warning(issue)
        else:
            st.info("No rule issue was reported by the matcher.")


def _render_reset_defaults(verifier: TitleVerifier) -> None:
    st.subheader("Reset to PRGI Statutory Defaults")
    st.warning("This removes custom rules and restores the baseline PRGI rule configuration.")
    confirm_text = st.text_input("Type RESET to confirm", key="reset_rules_confirm")
    if st.button("Reset to PRGI Statutory Defaults", disabled=confirm_text != "RESET"):
        if rule_store.reset_to_defaults():
            _after_rule_change(verifier)
            st.success("Rules reset to PRGI statutory defaults.")
            st.rerun()
        else:
            _show_rule_store_error()


def render_admin_panel(verifier: TitleVerifier) -> None:
    st.markdown("## PRGI Admin Panel")
    if not st.session_state.get("prgi_admin_authenticated", False):
        _render_admin_login()
        return

    lock_col, status_col = st.columns([1, 4])
    with lock_col:
        if st.button("Logout / Lock Admin Panel"):
            st.session_state["prgi_admin_authenticated"] = False
            st.rerun()
    with status_col:
        st.caption("Authenticated rule-management session.")

    overview_tab, words_tab, prefixes_tab, suffixes_tab, sandbox_tab, reset_tab = st.tabs([
        "Rules Overview",
        "Disallowed Words",
        "Prefix Manager",
        "Periodicity Manager",
        "Live Sandbox",
        "Reset Defaults",
    ])

    with overview_tab:
        _render_rules_overview()
    with words_tab:
        _render_add_disallowed_word(verifier)
        st.divider()
        _render_active_disallowed_words(verifier)
    with prefixes_tab:
        _render_token_manager(
            "Prefix Manager",
            "Prefix",
            rule_store.add_prefix,
            rule_store.remove_prefix,
            rule_store.get_prefixes,
            verifier,
            "prefix",
        )
    with suffixes_tab:
        _render_token_manager(
            "Periodicity / Suffix Manager",
            "Periodicity Term",
            rule_store.add_suffix,
            rule_store.remove_suffix,
            rule_store.get_suffixes,
            verifier,
            "suffix",
        )
    with sandbox_tab:
        _render_live_sandbox(verifier)
    with reset_tab:
        _render_reset_defaults(verifier)

# ═══════════════════════════════════════════════════════════════════════════
# Page Configuration
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Press Title Verification System",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════
# Stitch-Inspired Dark Theme CSS
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* ── Import Inter Font ───────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #e5e1e4;
    }

    /* ── App Background ──────────────────────────────────────── */
    .stApp {
        background-color: #09090b;
    }

    /* ── Top App Bar ─────────────────────────────────────────── */
    .top-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.25rem 2rem;
        background: #121216;
        border: 1px solid #27272a;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .brand-group {
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .brand-icon {
        width: 38px;
        height: 38px;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #adc6ff;
    }
    .brand-title {
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #f4f4f5;
        margin: 0;
    }

    /* ── Input Card ──────────────────────────────────────────── */
    .input-card {
        background: #121216;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 1.75rem 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
    }
    .input-label {
        font-size: 0.875rem;
        font-weight: 600;
        color: #a1a1aa;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }

    /* ── Verdict Banners ─────────────────────────────────────── */
    .verdict-approved {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.08) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-left: 4px solid #10b981;
        border-radius: 10px;
        padding: 1.25rem 1.75rem;
        margin: 1.5rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .verdict-rejected {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(220, 38, 38, 0.08) 100%);
        border: 1px solid rgba(239, 68, 68, 0.35);
        border-left: 4px solid #ef4444;
        border-radius: 10px;
        padding: 1.25rem 1.75rem;
        margin: 1.5rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .verdict-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin: 0;
    }
    .verdict-tag {
        font-size: 0.75rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 6px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .tag-approved {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .tag-rejected {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }

    /* ── Bento Stat Cards ────────────────────────────────────── */
    .bento-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .bento-card:hover {
        border-color: #3f3f46;
        transform: translateY(-2px);
    }
    .bento-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #a1a1aa;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.5rem;
    }
    .bento-value {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.1;
    }
    .bento-progress {
        width: 100%;
        height: 5px;
        background: #27272a;
        border-radius: 9999px;
        margin-top: 0.85rem;
        overflow: hidden;
    }
    .bento-progress-fill {
        height: 100%;
        border-radius: 9999px;
        transition: width 0.4s ease;
    }

    /* ── Issues Alert Banner ─────────────────────────────────── */
    .issue-box {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.25);
        border-left: 3px solid #f59e0b;
        border-radius: 8px;
        padding: 0.85rem 1.25rem;
        margin-bottom: 0.6rem;
        color: #fbbf24;
        font-size: 0.875rem;
        font-weight: 500;
    }

    /* ── Checklist Card ──────────────────────────────────────── */
    .check-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
    }
    .check-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #f4f4f5;
        margin-bottom: 0.2rem;
    }
    .check-desc {
        font-size: 0.8rem;
        color: #71717a;
    }
    .check-status-pass {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
    }
    .check-status-fail {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
    }

    /* ── Streamlit Form Controls Refinement ──────────────────── */
    div[data-baseweb="input"] {
        background-color: #09090b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 1px #3b82f6, 0 0 12px rgba(59, 130, 246, 0.2) !important;
    }
    input[type="text"] {
        color: #f4f4f5 !important;
        font-size: 1rem !important;
    }
    button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border: 1px solid #3b82f6 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        padding: 0.65rem 1.5rem !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        box-shadow: 0 0 16px rgba(59, 130, 246, 0.4) !important;
        transform: translateY(-1px) !important;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# Initialize Verifier Engine
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_verifier(version: str = "v3_calibrated_matcher") -> TitleVerifier:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "dataset", "titles_dataset.csv")
    return TitleVerifier(csv_path)

verifier = get_verifier("v3_calibrated_matcher")

navigation = st.radio(
    "Application Section",
    ["Public Verifier", "PRGI Admin Panel"],
    horizontal=True,
    label_visibility="collapsed",
)

if navigation == "PRGI Admin Panel":
    render_admin_panel(verifier)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# Header / App Bar
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="top-nav">
    <div class="brand-group">
        <div class="brand-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
            </svg>
        </div>
        <h1 class="brand-title">Press Title Verification System</h1>
    </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# Input Form Section
# ═══════════════════════════════════════════════════════════════════════════

with st.form("title_verification_form", clear_on_submit=False):
    candidate_title = st.text_input(
        "PROPOSED PUBLICATION TITLE",
        placeholder="e.g., Daily Hindustan, Sumit ke news, The Quantum Herald",
        help="Type the newspaper or periodical title you wish to evaluate and press Enter or click Verify.",
        key="candidate_title_input",
    )

    # Centered large trigger button
    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
    with col_b2:
        verify_submitted = st.form_submit_button("Verify Title", type="primary", use_container_width=True)

# Process new verification submission
if verify_submitted:
    if candidate_title and candidate_title.strip():
        with st.spinner("Running 7-stage verification pipeline..."):
            result: VerificationResult = verifier.verify(candidate_title.strip())
        st.session_state["last_result"] = result
        st.session_state["last_candidate"] = candidate_title.strip()
        st.session_state.pop("registration_msg", None)
    else:
        st.warning("Please enter a proposed publication title before clicking Verify.")
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_candidate", None)

# ═══════════════════════════════════════════════════════════════════════════
# Verification Results & Analysis
# ═══════════════════════════════════════════════════════════════════════════

if "last_result" in st.session_state and "last_candidate" in st.session_state:
    result: VerificationResult = st.session_state["last_result"]
    current_title: str = st.session_state["last_candidate"]

    # ── Verdict Banner ─────────────────────────────────────────────
    if result.is_approved:
        st.markdown(f"""
        <div class="verdict-approved">
            <div>
                <p class="verdict-title" style="color: #34d399;">
                    VERIFIED — "{current_title}" is eligible for registration
                </p>
                <p style="color: #6ee7b7; font-size: 0.85rem; margin: 4px 0 0 0;">
                    Meets PRGI similarity and anti-collision compliance guidelines.
                </p>
            </div>
            <span class="verdict-tag tag-approved">Approved</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="verdict-rejected">
            <div>
                <p class="verdict-title" style="color: #f87171;">
                    REJECTED — "{current_title}" cannot be registered
                </p>
                <p style="color: #fca5a5; font-size: 0.85rem; margin: 4px 0 0 0;">
                    Conflicts detected with existing publications or regulatory guidelines.
                </p>
            </div>
            <span class="verdict-tag tag-rejected">Rejected</span>
        </div>
        """, unsafe_allow_html=True)

    # ── 3 Bento Stat Cards ─────────────────────────────────────────
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    prob = result.verification_probability
    sim = result.highest_similarity
    issue_count = len(result.issues)

    prob_color = "#10b981" if result.is_approved else "#ef4444"
    sim_color = "#ef4444" if sim >= 65 else ("#f59e0b" if sim >= 45 else "#10b981")
    issues_color = "#ef4444" if issue_count > 0 else "#10b981"

    with stat_col1:
        st.markdown(f"""
        <div class="bento-card">
            <div class="bento-label">Verification Probability</div>
            <div class="bento-value" style="color: {prob_color};">{prob:.1f}%</div>
            <div class="bento-progress">
                <div class="bento-progress-fill" style="width: {min(100, max(0, prob))}%; background: {prob_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with stat_col2:
        st.markdown(f"""
        <div class="bento-card">
            <div class="bento-label">Highest Similarity Score</div>
            <div class="bento-value" style="color: {sim_color};">{sim:.1f}%</div>
            <div class="bento-progress">
                <div class="bento-progress-fill" style="width: {min(100, max(0, sim))}%; background: {sim_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with stat_col3:
        st.markdown(f"""
        <div class="bento-card">
            <div class="bento-label">Total Issues Found</div>
            <div class="bento-value" style="color: {issues_color};">{issue_count}</div>
            <div class="bento-progress">
                <div class="bento-progress-fill" style="width: {100 if issue_count > 0 else 0}%; background: {issues_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # ── Contextual Issue Warnings ──────────────────────────────────
    if result.issues:
        st.markdown("<p style='font-size: 0.85rem; font-weight: 700; color: #fbbf24; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;'>Detected Rule Violations</p>", unsafe_allow_html=True)
        for issue in result.issues:
            clean_issue = issue.replace("🚫 ", "").replace("⚠️ ", "")
            st.markdown(f"<div class='issue-box'>{clean_issue}</div>", unsafe_allow_html=True)
        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # ── Analysis Tabs ──────────────────────────────────────────────
    tab1, tab2 = st.tabs([
        "Closest Matching Titles",
        "Guideline Breakdown Checklist",
    ])

    # ── Tab 1: Top 5 Closest Matching Titles Table ─────────────────
    with tab1:
        st.markdown("<p style='color: #a1a1aa; font-size: 0.875rem; margin: 0.5rem 0 1rem 0;'>Top 5 closest records identified across phonetic, fuzzy, and semantic layers:</p>", unsafe_allow_html=True)
        if result.top_matches:
            table_data = []
            for match in result.top_matches:
                table_data.append({
                    "Existing Title": match.title,
                    "Fuzzy Match %": f"{match.fuzzy_score:.1f}%",
                    "Phonetic Match": "Yes" if match.phonetic_match else "No",
                    "Semantic Score %": f"{match.semantic_score * 100:.1f}%",
                    "Combined Similarity %": f"{match.combined_score:.1f}%",
                })

            matches_df = pd.DataFrame(table_data)
            st.dataframe(matches_df, hide_index=True)
        else:
            st.info("No matching records found in the database.")

    # ── Tab 2: Guideline Breakdown Checklist ───────────────────────
    with tab2:
        st.markdown("<p style='color: #a1a1aa; font-size: 0.875rem; margin: 0.5rem 0 1rem 0;'>Rule-by-rule verification against statutory Press Registrar guidelines:</p>", unsafe_allow_html=True)
        
        has_disallowed = any("Disallowed word" in i for i in result.issues)
        has_combination = any("combination" in i.lower() for i in result.issues)
        has_affix = any("Periodicity" in i or "affix" in i.lower() for i in result.issues)
        has_semantic = result.highest_similarity >= 75

        checks = [
            (
                "Disallowed Words Check",
                "Title does not contain prohibited government, defense, or security terms.",
                not has_disallowed,
            ),
            (
                "Title Combination Check",
                "Title is not a compound concatenation of two previously registered titles.",
                not has_combination,
            ),
            (
                "Affix & Periodicity Check",
                "Title is not formed merely by adding or removing periodicity tags (Daily, Weekly, Times).",
                not has_affix,
            ),
            (
                "Multilingual Semantic Similarity",
                "Title does not duplicate the meaning of existing registered titles across Indian languages.",
                not has_semantic,
            ),
        ]

        for check_name, desc, passed in checks:
            badge = '<span class="check-status-pass">Passed</span>' if passed else '<span class="check-status-fail">Failed</span>'
            st.markdown(f"""
            <div class="check-card">
                <div>
                    <div class="check-title">{check_name}</div>
                    <div class="check-desc">{desc}</div>
                </div>
                <div>{badge}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Registration Action Footer ─────────────────────────────────
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    if result.is_approved:
        col_r1, col_r2, col_r3 = st.columns([1, 2, 1])
        with col_r2:
            if st.button("Register this Title to Database", type="primary", use_container_width=True, key="register_button"):
                verifier.register_title(current_title)
                st.session_state["registration_msg"] = f"Successfully registered \"{current_title}\"! Database now contains {len(verifier.df):,} titles."
                st.rerun()

    if "registration_msg" in st.session_state:
        st.success(st.session_state["registration_msg"])
