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
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: #10b981;
        text-transform: uppercase;
    }
    .status-dot {
        width: 7px;
        height: 7px;
        background-color: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
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

    /* ── Custom Styled Table ─────────────────────────────────── */
    .stitch-table-container {
        background: #121216;
        border: 1px solid #27272a;
        border-radius: 10px;
        overflow: hidden;
        margin-top: 1rem;
    }
    table.stitch-table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
        font-size: 0.875rem;
    }
    table.stitch-table th {
        background: #18181b;
        color: #a1a1aa;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 12px 18px;
        border-bottom: 1px solid #27272a;
    }
    table.stitch-table td {
        padding: 14px 18px;
        color: #f4f4f5;
        border-bottom: 1px solid #1f1f23;
    }
    table.stitch-table tr:last-child td {
        border-bottom: none;
    }
    table.stitch-table tr:hover {
        background: #18181b;
    }
    .badge-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    .badge-no {
        background: rgba(113, 113, 122, 0.18);
        color: #a1a1aa;
        border: 1px solid #3f3f46;
    }
    .badge-yes {
        background: rgba(239, 68, 68, 0.18);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.35);
    }
    .mono-val {
        font-family: 'JetBrains Mono', monospace;
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
def get_verifier() -> TitleVerifier:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "dataset", "titles_dataset.csv")
    return TitleVerifier(csv_path)

verifier = get_verifier()

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
# Input Form Section
# ═══════════════════════════════════════════════════════════════════════════

candidate_title = st.text_input(
    "PROPOSED PUBLICATION TITLE",
    placeholder="e.g., Daily Hindustan, Sumit ke news, The Quantum Herald",
    help="Type the newspaper or periodical title you wish to evaluate.",
)

# Centered large trigger button
col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
with col_b2:
    verify_button = st.button("Verify Title", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# Verification Results & Analysis
# ═══════════════════════════════════════════════════════════════════════════

if verify_button and candidate_title.strip():
    with st.spinner("Running 7-stage verification pipeline..."):
        result: VerificationResult = verifier.verify(candidate_title.strip())

    # Save to session state
    st.session_state["last_result"] = result
    st.session_state["last_candidate"] = candidate_title.strip()

    # ── Verdict Banner ─────────────────────────────────────────────
    if result.is_approved:
        st.markdown(f"""
        <div class="verdict-approved">
            <div>
                <p class="verdict-title" style="color: #34d399;">
                    VERIFIED — "{candidate_title.strip()}" is eligible for registration
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
                    REJECTED — "{candidate_title.strip()}" cannot be registered
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

    prob_color = "#10b981" if prob >= 50 else "#ef4444"
    sim_color = "#ef4444" if sim >= 60 else ("#f59e0b" if sim >= 40 else "#10b981")
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
            if st.button("Register this Title to Database", type="primary", use_container_width=True):
                verifier.register_title(candidate_title.strip())
                st.success(
                    f"Successfully registered \"{candidate_title.strip()}\"! "
                    f"Database now contains {len(verifier.df):,} titles."
                )

elif verify_button:
    st.warning("Please enter a proposed publication title before clicking Verify.")
