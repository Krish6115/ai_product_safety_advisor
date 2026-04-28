"""Streamlit UI for the Mumzworld Smart Product Advisor."""

import streamlit as st
import json
import time
from agent.advisor import ProductAdvisor
from agent.schemas import Recommendation

# Page config
st.set_page_config(
    page_title="Mumzworld Product Advisor",
    page_icon="🧸",
    layout="wide",
)

# Custom CSS — polished, premium feel
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0 0.5rem 0;
    }
    .status-banner {
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin: 1rem 0;
        text-align: center;
    }
    .status-safe {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 2px solid #28a745;
    }
    .status-unsafe {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border: 2px solid #dc3545;
    }
    .status-uncertain {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        border: 2px solid #ffc107;
    }
    .status-icon {
        font-size: 3rem;
        margin-bottom: 0.25rem;
    }
    .status-label {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }
    .status-safe .status-label { color: #155724; }
    .status-unsafe .status-label { color: #721c24; }
    .status-uncertain .status-label { color: #856404; }
    .safety-flag {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        margin: 4px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .flag-danger { background-color: #dc3545; color: white; }
    .flag-warning { background-color: #ffc107; color: #333; }
    .flag-info { background-color: #17a2b8; color: white; }
    .trace-step {
        padding: 8px 12px;
        margin: 4px 0;
        border-left: 3px solid #007bff;
        background-color: #f8f9fa;
        border-radius: 0 6px 6px 0;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.9rem;
    }
    .trace-override {
        border-left-color: #dc3545;
        background-color: #fff5f5;
    }
    .confidence-container {
        margin-top: 8px;
    }
    .alt-card {
        padding: 10px 14px;
        margin: 6px 0;
        border-radius: 8px;
        background-color: #e8f5e9;
        border-left: 3px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)


def get_flag_class(flag: str) -> str:
    """Map safety flag to CSS class."""
    danger_flags = {"choking_hazard", "age_inappropriate", "weight_limit", "recall_alert", "battery_hazard"}
    warning_flags = {"supervision_required", "material_concern"}
    if flag in danger_flags:
        return "flag-danger"
    elif flag in warning_flags:
        return "flag-warning"
    return "flag-info"


def render_response(response):
    """Render the advisor response with visual status indicators."""
    # === BIG STATUS BANNER ===
    rec = response.recommendation
    if rec == Recommendation.SUITABLE:
        css = "status-safe"
        icon = "🟢"
        label = "SAFE" if response.query_language == "en" else "آمن"
    elif rec == Recommendation.NOT_SUITABLE:
        css = "status-unsafe"
        icon = "🔴"
        label = "UNSAFE" if response.query_language == "en" else "غير آمن"
    else:
        css = "status-uncertain"
        icon = "🟡"
        label = "UNCERTAIN" if response.query_language == "en" else "غير مؤكد"

    st.markdown(f"""
    <div class="status-banner {css}">
        <div class="status-icon">{icon}</div>
        <p class="status-label">{label}</p>
    </div>
    """, unsafe_allow_html=True)

    # === DETAILS + SAFETY FLAGS ===
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Product Details")
        if response.product_name:
            st.write(f"**Product:** {response.product_name}")
        if response.product_id:
            st.write(f"**ID:** `{response.product_id}`")
        if response.age_range_months:
            st.write(f"**Age Range:** {response.age_range_months} months")

        # Confidence bar
        st.write(f"**Confidence:** {response.confidence:.0%}")
        bar_color = "#28a745" if response.confidence > 0.7 else "#ffc107" if response.confidence > 0.4 else "#dc3545"
        st.markdown(
            f'<div class="confidence-container">'
            f'<div style="background:#e0e0e0;border-radius:4px;height:10px;">'
            f'<div style="background:{bar_color};width:{response.confidence*100}%;height:10px;border-radius:4px;'
            f'transition:width 0.5s ease;"></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    with col2:
        st.subheader("Safety Flags")
        if response.safety_flags:
            flags_html = ""
            for flag in response.safety_flags:
                flag_val = flag.value if hasattr(flag, "value") else str(flag)
                css_class = get_flag_class(flag_val)
                flags_html += f'<span class="safety-flag {css_class}">{flag_val.replace("_", " ").upper()}</span>'
            st.markdown(flags_html, unsafe_allow_html=True)
        else:
            st.success("No safety concerns identified.")

    # === REASONING SUMMARY ===
    st.subheader("Reasoning")
    st.write(response.reasoning)

    # === REASONING TRACE (the wow factor) ===
    if response.reasoning_trace:
        st.subheader("Reasoning Trace")
        for i, step in enumerate(response.reasoning_trace, 1):
            is_override = step.startswith("[OVERRIDE]")
            css_class = "trace-step trace-override" if is_override else "trace-step"
            st.markdown(
                f'<div class="{css_class}"><strong>Step {i}:</strong> {step}</div>',
                unsafe_allow_html=True,
            )

    # === ALTERNATIVES ===
    if response.alternatives:
        st.subheader("Safer Alternatives")
        for alt in response.alternatives:
            st.markdown(
                f'<div class="alt-card">'
                f'<strong>{alt.name}</strong> (<code>{alt.product_id}</code>)<br/>'
                f'{alt.reason}</div>',
                unsafe_allow_html=True,
            )

    # === DISCLAIMER ===
    st.caption(f"⚠️ {response.disclaimer}")


def main():
    # Header
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("🧸 Mumzworld Smart Product Advisor")
    st.write("*AI-powered product safety checker for parents — English & Arabic*")
    st.markdown("</div>", unsafe_allow_html=True)

    # Initialize advisor (cached)
    @st.cache_resource
    def get_advisor():
        return ProductAdvisor()

    try:
        advisor = get_advisor()
    except ValueError as e:
        st.error(f"⚠️ {str(e)}")
        st.stop()

    # Example queries in tabs
    st.subheader("Try these examples:")
    example_col1, example_col2 = st.columns(2)

    examples_en = [
        "Is the Chicco stroller safe for a 3-month-old?",
        "Can my 15kg toddler use the Infantino swing?",
        "Is the marble run set safe for a 2-year-old?",
        "Is the XYZ-9999 blender safe for my baby?",
    ]
    examples_ar = [
        "هل عربة شيكو آمنة لطفل عمره 3 أشهر؟",
        "هل لعبة الليغو مناسبة لطفل عمره سنة؟",
        "أريد كرسي سيارة لطفلي عمره 3 أشهر",
    ]

    with example_col1:
        st.write("**English:**")
        for ex in examples_en:
            if st.button(ex, key=f"en_{ex[:25]}"):
                st.session_state.query = ex

    with example_col2:
        st.write("**العربية:**")
        for ex in examples_ar:
            if st.button(ex, key=f"ar_{ex[:25]}"):
                st.session_state.query = ex

    st.divider()

    # Query input
    query = st.text_area(
        "Ask about a product (English or Arabic):",
        value=st.session_state.get("query", ""),
        height=80,
        placeholder="e.g., Is this stroller safe for my 6-month-old? / هل هذه العربة آمنة لطفل عمره 6 أشهر؟",
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    with col_btn1:
        submit = st.button("🔍 Check Safety", type="primary", use_container_width=True)
    with col_btn2:
        clear = st.button("🗑️ Clear", use_container_width=True)

    if clear:
        st.session_state.query = ""
        st.rerun()

    if submit and query.strip():
        with st.spinner("Analyzing product safety..."):
            start = time.time()
            response = advisor.query(query.strip())
            elapsed = time.time() - start

        st.success(f"Analysis complete in {elapsed:.1f}s")

        # Render formatted response
        render_response(response)

        # Raw JSON (collapsible)
        with st.expander("Raw JSON Response"):
            st.json(json.loads(response.model_dump_json()))

    elif submit:
        st.warning("Please enter a question about a Mumzworld product.")


if __name__ == "__main__":
    main()
