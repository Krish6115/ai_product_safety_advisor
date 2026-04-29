"""Streamlit UI for the Mumzworld Smart Product Advisor."""

import streamlit as st
import json
import time
from agent.advisor import ProductAdvisor
from agent.schemas import Recommendation

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Mumzworld · AI Product Safety Advisor",
    page_icon="🛡️",
    layout="centered",
)

# ──────────────────────────────────────────────
# CSS — Premium, Mumzworld-inspired design
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Import Google Font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── Global ── */
    html, body, .stApp {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background: linear-gradient(to bottom, #fff5f7, #ffffff) !important;
    }
    .block-container {
        max-width: 700px;
        padding-top: 2rem;
    }
    h1, h2, h3 { color: #111111 !important; }
    p { color: #555555 !important; }

    /* ── Header ── */
    .mw-header {
        text-align: center;
        padding: 2rem 1rem 1rem 1rem;
    }
    .mw-logo {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #ff4d6d;
    }
    .mw-logo span {
        color: #2d2d2d;
    }
    .mw-tagline {
        font-size: 1.05rem;
        font-weight: 600;
        color: #444;
        margin-top: 4px;
    }
    .mw-subtext {
        font-size: 0.85rem;
        color: #888;
        margin-top: 2px;
    }

    /* ── Card base ── */
    .mw-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.75rem 2rem;
        margin: 1rem 0;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border: 1px solid #f0e4e8;
    }

    /* ── Status Banner ── */
    .mw-status {
        text-align: center;
        padding: 2rem 1.5rem;
        border-radius: 16px;
        margin: 0.5rem 0 1rem 0;
    }
    .mw-status-safe {
        background: linear-gradient(135deg, #e8f8ee 0%, #d0f0db 100%);
        border: 1.5px solid #34c759;
    }
    .mw-status-unsafe {
        background: linear-gradient(135deg, #fde8ec 0%, #fcd1d8 100%);
        border: 1.5px solid #ff3b5c;
    }
    .mw-status-uncertain {
        background: linear-gradient(135deg, #fff8e6 0%, #ffefc2 100%);
        border: 1.5px solid #f5a623;
    }
    .mw-status-icon {
        font-size: 2.75rem;
        line-height: 1;
    }
    .mw-status-label {
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: 1px;
        margin-top: 6px;
    }
    .mw-status-safe .mw-status-label { color: #1b7a3d; }
    .mw-status-unsafe .mw-status-label { color: #c0172b; }
    .mw-status-uncertain .mw-status-label { color: #9a6c00; }
    .mw-status-hint {
        font-size: 0.82rem;
        color: #777;
        margin-top: 4px;
    }

    /* ── Section titles ── */
    .mw-section-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #aaa;
        margin-bottom: 10px;
        margin-top: 4px;
    }

    /* ── Product detail rows ── */
    .mw-detail-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #f5f0f2;
    }
    .mw-detail-row:last-child { border-bottom: none; }
    .mw-detail-key {
        font-size: 0.88rem;
        color: #888;
        font-weight: 500;
    }
    .mw-detail-val {
        font-size: 0.92rem;
        color: #333;
        font-weight: 600;
    }

    /* ── Confidence bar ── */
    .mw-conf-track {
        width: 100%;
        height: 8px;
        background: #eee;
        border-radius: 4px;
        margin-top: 6px;
        overflow: hidden;
    }
    .mw-conf-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.6s ease;
    }

    /* ── Safety flag pills ── */
    .mw-flags { display: flex; flex-wrap: wrap; gap: 8px; }
    .mw-flag {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .mw-flag-danger { background: #ffe0e6; color: #c0172b; }
    .mw-flag-warning { background: #fff3d6; color: #9a6c00; }
    .mw-flag-info { background: #e0f0ff; color: #1a6fb5; }

    /* ── Rules applied pills ── */
    .mw-rule {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #f3e8ff;
        color: #7c3aed;
        margin: 3px 4px 3px 0;
    }

    /* ── Reasoning text ── */
    .mw-reasoning {
        font-size: 0.95rem;
        color: #444;
        line-height: 1.65;
    }

    /* ── Trace steps ── */
    .mw-trace-step {
        padding: 10px 14px;
        margin: 5px 0;
        border-left: 3px solid #ddd;
        background: #fafafa;
        border-radius: 0 8px 8px 0;
        font-size: 0.84rem;
        color: #555;
        line-height: 1.5;
    }
    .mw-trace-override {
        border-left-color: #ff3b5c;
        background: #fff5f6;
    }
    .mw-trace-num {
        font-weight: 700;
        color: #bbb;
        margin-right: 6px;
    }

    /* ── Alternative card ── */
    .mw-alt {
        padding: 12px 16px;
        margin: 6px 0;
        border-radius: 10px;
        background: #f0faf3;
        border: 1px solid #d0f0db;
    }
    .mw-alt-name {
        font-weight: 700;
        font-size: 0.9rem;
        color: #333;
    }
    .mw-alt-id {
        font-size: 0.75rem;
        color: #999;
        margin-left: 6px;
    }
    .mw-alt-reason {
        font-size: 0.82rem;
        color: #666;
        margin-top: 4px;
    }

    /* ── Disclaimer ── */
    .mw-disclaimer {
        font-size: 0.78rem;
        color: #aaa;
        text-align: center;
        padding: 8px 0 0 0;
        line-height: 1.5;
    }

    /* ── Streamlit overrides ── */
    .stTextArea textarea {
        background-color: #ffffff !important;
        color: #111111 !important;
        border: 2px solid #ff4d6d !important;
        border-radius: 12px !important;
        padding: 12px !important;
        font-size: 16px !important;
    }
    
    .stButton > button[kind="primary"] {
        background-color: #ff4d6d !important;
        color: white !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        box-shadow: 0 4px 6px -1px rgba(255, 77, 109, 0.2), 0 2px 4px -1px rgba(255, 77, 109, 0.1) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #e63e5c !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: #111827 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
        background: #ffffff !important;
    }
    .stDivider { margin: 0.75rem 0 !important; }
    
    .input-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
    }

    /* ── Example buttons ── */
    .mw-example-btn {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        border: 1px solid #e8dce0;
        background: #fff;
        color: #111111;
        font-size: 0.85rem;
        cursor: pointer;
        margin: 4px;
        transition: all 0.2s;
    }
    .mw-example-btn:hover {
        border-color: #ff4d6d;
        color: #ff4d6d;
        background: #fff5f7;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────
def get_flag_display(flag_val: str) -> tuple[str, str]:
    """Return (display_name, css_class) for a safety flag."""
    danger = {"choking_hazard", "age_inappropriate", "weight_limit", "recall_alert", "battery_hazard"}
    warning = {"supervision_required", "material_concern"}
    labels = {
        "choking_hazard": "Choking Hazard",
        "age_inappropriate": "Age Inappropriate",
        "weight_limit": "Weight Limit Exceeded",
        "recall_alert": "Recall Alert",
        "battery_hazard": "Battery Hazard",
        "supervision_required": "Supervision Required",
        "material_concern": "Material Concern",
        "insufficient_data": "Insufficient Data",
    }
    label = labels.get(flag_val, flag_val.replace("_", " ").title())
    if flag_val in danger:
        return label, "mw-flag-danger"
    elif flag_val in warning:
        return label, "mw-flag-warning"
    return label, "mw-flag-info"


def conf_color(c: float) -> str:
    if c >= 0.7:
        return "#34c759"
    elif c >= 0.4:
        return "#f5a623"
    return "#ff3b5c"


def render_response(response):
    """Render the advisor response as a premium result card."""
    rec = response.recommendation

    # ── Status Banner ──
    if rec == Recommendation.SUITABLE:
        css, icon, label = "mw-status-safe", "✅", "SAFE"
        hint = "This product appears suitable for your child."
        if response.query_language == "ar":
            label, hint = "آمن", "يبدو أن هذا المنتج مناسب لطفلك."
    elif rec == Recommendation.NOT_SUITABLE:
        css, icon, label = "mw-status-unsafe", "⛔", "NOT SUITABLE"
        hint = "This product may not be safe for your child."
        if response.query_language == "ar":
            label, hint = "غير مناسب", "قد لا يكون هذا المنتج آمناً لطفلك."
    else:
        css, icon, label = "mw-status-uncertain", "⚠️", "UNCERTAIN"
        hint = "We couldn't confidently assess this product."
        if response.query_language == "ar":
            label, hint = "غير مؤكد", "لم نتمكن من تقييم هذا المنتج بثقة."

    st.markdown(f"""
    <div class="mw-status {css}">
        <div class="mw-status-icon">{icon}</div>
        <div class="mw-status-label">{label}</div>
        <div class="mw-status-hint">{hint}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Uncertain: friendly fallback message ──
    if rec == Recommendation.UNCERTAIN:
        st.info("💡 **Tip:** Try rephrasing your question with the exact product name and your child's age for a more accurate assessment.")

    # ── Product Details Card ──
    has_product_info = response.product_name or response.product_id or response.age_range_months
    if has_product_info or response.confidence > 0:
        details_html = '<div class="mw-card"><div class="mw-section-title">Product Details</div>'
        if response.product_name:
            details_html += f"""
            <div class="mw-detail-row">
                <span class="mw-detail-key">Product</span>
                <span class="mw-detail-val">{response.product_name}</span>
            </div>"""
        if response.product_id:
            details_html += f"""
            <div class="mw-detail-row">
                <span class="mw-detail-key">ID</span>
                <span class="mw-detail-val" style="font-family:monospace">{response.product_id}</span>
            </div>"""
        if response.age_range_months:
            details_html += f"""
            <div class="mw-detail-row">
                <span class="mw-detail-key">Age Range</span>
                <span class="mw-detail-val">{response.age_range_months} months</span>
            </div>"""

        # Confidence
        color = conf_color(response.confidence)
        details_html += f"""
        <div class="mw-detail-row" style="border-bottom:none">
            <span class="mw-detail-key">Confidence</span>
            <span class="mw-detail-val" style="color:{color}">{response.confidence:.0%}</span>
        </div>
        <div class="mw-conf-track">
            <div class="mw-conf-fill" style="width:{response.confidence*100}%;background:{color}"></div>
        </div>
        """
        details_html += "</div>"
        st.markdown(details_html, unsafe_allow_html=True)

    # ── Reasoning Card ──
    if response.reasoning:
        reasoning_html = f"""
        <div class="mw-card">
            <div class="mw-section-title">Reasoning</div>
            <div class="mw-reasoning">{response.reasoning}</div>
        </div>"""
        st.markdown(reasoning_html, unsafe_allow_html=True)

    # ── Safety Flags ──
    visible_flags = [f for f in response.safety_flags
                     if (f.value if hasattr(f, "value") else str(f)) != "insufficient_data"]
    if visible_flags:
        flags_html = '<div class="mw-card"><div class="mw-section-title">Safety Flags</div><div class="mw-flags">'
        for flag in visible_flags:
            fval = flag.value if hasattr(flag, "value") else str(flag)
            label, css_class = get_flag_display(fval)
            flags_html += f'<span class="mw-flag {css_class}">{label}</span>'
        flags_html += "</div>"

        # Rules applied
        if response.rule_applied:
            flags_html += '<div style="margin-top:12px"><div class="mw-section-title">Rules Applied</div>'
            for rule in response.rule_applied:
                flags_html += f'<span class="mw-rule">{rule}</span>'
            flags_html += "</div>"

        flags_html += "</div>"
        st.markdown(flags_html, unsafe_allow_html=True)

    # ── Reasoning Trace (collapsible) ──
    if response.reasoning_trace:
        with st.expander("Show reasoning trace"):
            trace_html = ""
            for i, step in enumerate(response.reasoning_trace, 1):
                is_override = step.startswith("[OVERRIDE]")
                css = "mw-trace-step mw-trace-override" if is_override else "mw-trace-step"
                trace_html += f'<div class="{css}"><span class="mw-trace-num">{i}.</span>{step}</div>'
            st.markdown(trace_html, unsafe_allow_html=True)

    # ── Alternatives ──
    if response.alternatives:
        alts_html = '<div class="mw-card"><div class="mw-section-title">Safer Alternatives</div>'
        for alt in response.alternatives:
            alts_html += f"""
            <div class="mw-alt">
                <span class="mw-alt-name">{alt.name}</span>
                <span class="mw-alt-id">{alt.product_id}</span>
                <div class="mw-alt-reason">{alt.reason}</div>
            </div>"""
        alts_html += "</div>"
        st.markdown(alts_html, unsafe_allow_html=True)

    # ── Disclaimer ──
    st.markdown(f'<div class="mw-disclaimer">⚠️ {response.disclaimer}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Main App
# ──────────────────────────────────────────────
def main():
    # ── Header ──
    st.markdown("""
    <div class="mw-header">
        <div class="mw-logo">mumz<span>world</span></div>
        <div class="mw-tagline">AI Product Safety Advisor</div>
        <div class="mw-subtext">Helping parents make safe decisions</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Initialize advisor (cached) ──
    @st.cache_resource
    def get_advisor():
        return ProductAdvisor()

    try:
        advisor = get_advisor()
    except ValueError as e:
        st.error(f"⚠️ {str(e)}")
        st.stop()

    # ── Example queries ──
    st.markdown("")
    examples = [
        "Is the Chicco stroller safe for a 3-month-old?",
        "هل لعبة الليغو مناسبة لطفل عمره سنة؟",
        "Can my 15kg toddler use the Infantino swing?",
        "Is the marble run set safe for a 2-year-old?",
    ]
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        with cols[i]:
            if st.button(ex[:28] + "…" if len(ex) > 28 else ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.query = ex

    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    
    # ── Query Input ──
    query = st.text_area(
        "Ask about product safety",
        value=st.session_state.get("query", ""),
        height=80,
        placeholder="e.g., Is this stroller safe for my 6-month-old? / هل هذه العربة آمنة لطفل عمره 6 أشهر؟",
        label_visibility="collapsed",
    )

    col_btn, col_clear, _ = st.columns([1.2, 0.8, 3])
    with col_btn:
        submit = st.button("🛡️ Check Safety", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear", use_container_width=True):
            st.session_state.query = ""
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Results ──
    if submit and query.strip():
        with st.spinner("Analyzing product safety…"):
            start = time.time()
            response = advisor.query(query.strip())
            elapsed = time.time() - start

        st.caption(f"Analysis completed in {elapsed:.1f}s")
        render_response(response)

        # Raw JSON
        with st.expander("View raw JSON"):
            st.json(json.loads(response.model_dump_json()))

    elif submit:
        st.warning("Please enter a question about a product.")


if __name__ == "__main__":
    main()
