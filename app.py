"""
app.py — Streamlit Dashboard for Press Title Verification
==========================================================

Provides an interactive web interface for the PSS06 Automated Title
Verification System. Users can submit proposed press titles, view
real-time verification results, explore similarity analysis, and
register approved titles into the live database.

Layout:
    ┌──────────────────────────────────────────────────┐
    │  Header: Title + Total Registered Titles Metric  │
    ├──────────────────────────────────────────────────┤
    │  Expandable Database Sample Viewer               │
    ├──────────────────────────────────────────────────┤
    │  Submission Form: Text Input + Verify Button     │
    ├──────────────────────────────────────────────────┤
    │  Status Banner (✅ VERIFIED / ❌ REJECTED)        │
    │  3 KPI Cards: Probability | Similarity | Issues  │
    ├──────────────────────────────────────────────────┤
    │  Issue Warnings (Yellow callouts)                │
    ├──────────────────────────────────────────────────┤
    │  Tab 1: Top 5 Closest Matching Titles Table      │
    │  Tab 2: Guideline Breakdown Checklist            │
    ├──────────────────────────────────────────────────┤
    │  Action Footer: Register Title Button            │
    └──────────────────────────────────────────────────┘
"""

import os
import streamlit as st
import pandas as pd
from matcher import TitleVerifier, VerificationResult

# ═══════════════════════════════════════════════════════════════════════════
# Page Configuration
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="PSS06 — Press Title Verification System",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════
# Custom CSS for Premium Styling
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* ── Global typography ───────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Header styling ──────────────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 50%, #3a7bd5 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 8px 32px rgba(30, 58, 95, 0.25);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1rem;
        opacity: 0.85;
    }

    /* ── Status banners ──────────────────────────────────────── */
    .status-approved {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        padding: 1.25rem 2rem;
        border-radius: 12px;
        font-size: 1.3rem;
        font-weight: 700;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(5, 150, 105, 0.3);
        animation: fadeIn 0.5s ease-in;
    }
    .status-rejected {
        background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        color: white;
        padding: 1.25rem 2rem;
        border-radius: 12px;
        font-size: 1.3rem;
        font-weight: 700;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(220, 38, 38, 0.3);
        animation: fadeIn 0.5s ease-in;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ── KPI metric cards ────────────────────────────────────── */
    .kpi-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        color: #1e3a5f;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748b;
        margin-top: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ── Subtle table and tab improvements ───────────────────── */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Button styling ──────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# Initialize the Verifier (Cached)
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_verifier() -> TitleVerifier:
    """
    Load and cache the TitleVerifier instance.

    The CSV path is resolved relative to this script's directory so
    it works regardless of the working directory used to launch Streamlit.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "dataset", "titles_dataset.csv")
    return TitleVerifier(csv_path)


verifier = get_verifier()

# ═══════════════════════════════════════════════════════════════════════════
# Header
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>📰 Press Title Verification System</h1>
    <p>PSS06 — Automated title similarity and compliance checking for the Press Registrar General of India</p>
</div>
""", unsafe_allow_html=True)

# Total registered titles metric
total_titles = len(verifier.df)
st.metric(label="📊 Total Registered Titles in Database", value=f"{total_titles:,}")

# ═══════════════════════════════════════════════════════════════════════════
# Database Sample Viewer (Expandable)
# ═══════════════════════════════════════════════════════════════════════════

with st.expander("🗂️ View Database Sample", expanded=False):
    st.markdown("A random sample of **20 titles** from the registered database:")
    sample_df = verifier.df.sample(n=min(20, len(verifier.df)), random_state=42)
    st.dataframe(sample_df, use_container_width=True, hide_index=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Submission Form
# ═══════════════════════════════════════════════════════════════════════════

st.subheader("🔎 Submit a New Title for Verification")

candidate_title = st.text_input(
    "Enter proposed title:",
    placeholder="e.g., Daily Hindustan, Zenith Quantum Gazette",
    help="Type the proposed newspaper/periodical title you want to check.",
)

verify_button = st.button("🔍 Verify Title", type="primary", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# Verification Results
# ═══════════════════════════════════════════════════════════════════════════

if verify_button and candidate_title.strip():
    with st.spinner("⏳ Running 7-stage verification pipeline..."):
        result: VerificationResult = verifier.verify(candidate_title.strip())

    # Store result in session state for the registration button
    st.session_state["last_result"] = result
    st.session_state["last_candidate"] = candidate_title.strip()

    # ── Status Banner ──────────────────────────────────────────────
    if result.is_approved:
        st.markdown(
            f'<div class="status-approved">✅ VERIFIED — '
            f'"{candidate_title.strip()}" is eligible for registration</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status-rejected">❌ REJECTED — '
            f'"{candidate_title.strip()}" cannot be registered</div>',
            unsafe_allow_html=True,
        )

    # ── 3 KPI Metric Cards ────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        prob_color = "#059669" if result.verification_probability >= 60 else "#dc2626"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color: {prob_color}">
                {result.verification_probability:.1f}%
            </div>
            <div class="kpi-label">Verification Probability</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        sim_color = "#dc2626" if result.highest_similarity >= 60 else "#059669"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color: {sim_color}">
                {result.highest_similarity:.1f}%
            </div>
            <div class="kpi-label">Highest Similarity Score</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        issue_count = len(result.issues)
        issue_color = "#dc2626" if issue_count > 0 else "#059669"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color: {issue_color}">
                {issue_count}
            </div>
            <div class="kpi-label">Total Issues Found</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Issue Warnings ─────────────────────────────────────────────
    if result.issues:
        st.subheader("⚠️ Issues Detected")
        for issue in result.issues:
            st.warning(issue)

    # ── Analysis Tabs ──────────────────────────────────────────────
    tab1, tab2 = st.tabs([
        "📊 Closest Matching Titles",
        "📋 Guideline Breakdown Checklist",
    ])

    # ── Tab 1: Top 5 Closest Matching Titles ──────────────────────
    with tab1:
        st.markdown("**Top 5 most similar titles** in the registered database:")

        if result.top_matches:
            table_data = []
            for match in result.top_matches:
                table_data.append({
                    "Existing Title": match.title,
                    "Fuzzy Match %": f"{match.fuzzy_score:.1f}%",
                    "Phonetic Match": "✅ Yes" if match.phonetic_match else "❌ No",
                    "Semantic Score %": f"{match.semantic_score * 100:.1f}%",
                    "Combined Similarity %": f"{match.combined_score:.1f}%",
                })

            matches_df = pd.DataFrame(table_data)
            st.dataframe(matches_df, use_container_width=True, hide_index=True)
        else:
            st.info("No matching titles found in the database.")

    # ── Tab 2: Guideline Breakdown Checklist ──────────────────────
    with tab2:
        st.markdown("**Compliance check against PRGI title registration guidelines:**")

        # Determine status for each rule category
        has_disallowed = any("Disallowed word" in i for i in result.issues)
        has_combination = any("combination" in i.lower() for i in result.issues)
        has_affix = any("Periodicity" in i or "affix" in i.lower() for i in result.issues)
        has_semantic = result.highest_similarity >= 75

        checks = [
            (
                "Disallowed Words Check",
                "Title does not contain government/security terms "
                "(police, crime, army, etc.)",
                not has_disallowed,
            ),
            (
                "Title Combination Check",
                "Title is not a concatenation of two existing "
                "registered titles",
                not has_combination,
            ),
            (
                "Affix & Periodicity Check",
                "Title is not merely adding/removing periodicity "
                "markers (Daily, Weekly) to an existing title",
                not has_affix,
            ),
            (
                "Multilingual Semantic Similarity",
                "Title does not semantically duplicate an existing "
                "title across languages (threshold: 75%)",
                not has_semantic,
            ),
        ]

        for check_name, description, passed in checks:
            icon = "✅" if passed else "❌"
            status_text = "PASSED" if passed else "FAILED"
            st.markdown(f"**{icon} {check_name}** — {status_text}")
            st.caption(f"   {description}")

    # ── Action Footer: Register Button ─────────────────────────────
    st.divider()

    if result.is_approved:
        st.success(
            f"🎉 **\"{candidate_title.strip()}\"** has passed all verification "
            f"checks and is eligible for registration."
        )
        if st.button(
            "📝 Register this Title to Database",
            type="secondary",
            use_container_width=True,
        ):
            verifier.register_title(candidate_title.strip())
            # Clear the cached verifier so the count refreshes
            st.success(
                f"✅ **\"{candidate_title.strip()}\"** has been registered! "
                f"Database now contains {len(verifier.df):,} titles."
            )
    else:
        st.error(
            f"🚫 **\"{candidate_title.strip()}\"** has been rejected and "
            f"cannot be registered. Please choose a different title."
        )

elif verify_button:
    st.warning("⚠️ Please enter a title before clicking Verify.")
