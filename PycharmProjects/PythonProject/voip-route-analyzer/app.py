"""
app.py
------
Streamlit UI for VoIP Route Analyzer Lite.

Run with:
    streamlit run app.py

This UI imports the analysis logic from analyzer.py.
"""

import pandas as pd
import streamlit as st

from analyzer import (
    REQUIRED_COLUMNS,
    analyze_all_routes,
    create_sample_dataframe,
    get_global_summary,
)


# -----------------------------
# Page configuration
# -----------------------------

st.set_page_config(
    page_title="VoIP Route Analyzer Lite",
    page_icon="📞",
    layout="wide",
)


# -----------------------------
# Helper functions
# -----------------------------


def results_to_dataframe(results):
    """Convert route analysis results into a Streamlit-friendly DataFrame."""
    return pd.DataFrame(results)


def show_status_badge(row):
    """Return a readable status label for one route."""
    if row["fas_suspected"]:
        return "🚨 FAS Alert"
    if row["asr_interpretation"] == "Bad route quality":
        return "🔴 Bad Route"
    if row["asr_interpretation"] == "Weak / needs monitoring":
        return "🟠 Monitor"
    if row["average_pdd"] > 5:
        return "🟡 High PDD"
    return "🟢 Stable"


def load_data_from_upload(uploaded_file):
    """Load CSV from Streamlit uploader or fallback to sample data."""
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)

    return create_sample_dataframe()


# -----------------------------
# Header
# -----------------------------

st.title("📞 VoIP Route Analyzer Lite")
st.caption("NOC-style dashboard for route quality, ASR, PDD, SIP failures, RBT issues and FAS suspicion.")

with st.expander("What this prototype demonstrates", expanded=False):
    st.write(
        """
        This prototype simulates a basic VoIP/NOC route investigation workflow.
        It processes call logs, calculates route KPIs, detects suspicious patterns,
        and recommends next actions.

        It is not a production telecom monitoring platform. It is a portfolio prototype
        created to demonstrate analytical thinking, Python automation and VoIP quality understanding.
        """
    )


# -----------------------------
# Sidebar controls
# -----------------------------

st.sidebar.header("Input data")

uploaded_file = st.sidebar.file_uploader(
    "Upload call_logs.csv",
    type=["csv"],
)

st.sidebar.markdown("Required CSV columns:")
st.sidebar.code(
    ", ".join(REQUIRED_COLUMNS),
    language="text",
)

st.sidebar.info("No CSV uploaded? The app will use built-in sample VoIP call logs.")


# -----------------------------
# Main app logic
# -----------------------------

try:
    call_logs_df = load_data_from_upload(uploaded_file)
    results = analyze_all_routes(call_logs_df)
    summary = get_global_summary(call_logs_df, results)
    results_df = results_to_dataframe(results)
    results_df["status"] = results_df.apply(show_status_badge, axis=1)

except Exception as error:
    st.error(f"Could not analyze the file: {error}")
    st.stop()


# -----------------------------
# KPI cards
# -----------------------------

st.subheader("Global KPIs")

kpi_1, kpi_2, kpi_3, kpi_4, kpi_5 = st.columns(5)

kpi_1.metric("Total calls", summary["total_calls"])
kpi_2.metric("Answered calls", summary["answered_calls"])
kpi_3.metric("Global ASR", f"{summary['global_asr']}%")
kpi_4.metric("Average PDD", f"{summary['average_pdd']}s")
kpi_5.metric("FAS alerts", summary["fas_alerts"])

st.divider()


# -----------------------------
# Preferred route
# -----------------------------

preferred_route = summary["preferred_route"]

st.subheader("Preferred route")

if preferred_route != "None":
    best_route = results_df[results_df["route"] == preferred_route].iloc[0]

    col_a, col_b, col_c = st.columns([1, 1, 2])

    col_a.metric("Route", best_route["route"])
    col_b.metric("ASR", f"{best_route['asr']}%")
    col_c.success(
        f"Recommended candidate based on current sample: {best_route['route']} "
        f"with {best_route['asr']}% ASR and {best_route['average_pdd']}s average PDD."
    )
else:
    st.warning("No preferred route could be selected.")

st.divider()


# -----------------------------
# Filters
# -----------------------------

st.subheader("Route investigation")

route_options = ["All routes"] + results_df["route"].tolist()
selected_route = st.selectbox("Select route", route_options)

if selected_route == "All routes":
    visible_results_df = results_df.copy()
else:
    visible_results_df = results_df[results_df["route"] == selected_route].copy()


# -----------------------------
# Charts
# -----------------------------

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.markdown("### ASR by route")
    st.bar_chart(
        visible_results_df.set_index("route")[["asr"]]
    )

with chart_col_2:
    st.markdown("### Average PDD by route")
    st.bar_chart(
        visible_results_df.set_index("route")[["average_pdd"]]
    )

st.divider()


# -----------------------------
# Route table
# -----------------------------

st.markdown("### Investigation table")

columns_to_show = [
    "route",
    "destination",
    "total_calls",
    "asr",
    "asr_interpretation",
    "average_pdd",
    "pdd_interpretation",
    "main_failure_status",
    "main_sip_code",
    "missing_rbt_count",
    "missing_rbt_ratio",
    "short_answered_calls",
    "short_answered_ratio",
    "fas_suspected",
    "status",
    "recommendation",
]

st.dataframe(
    visible_results_df[columns_to_show],
    use_container_width=True,
    hide_index=True,
)


# -----------------------------
# NOC interpretation cards
# -----------------------------

st.markdown("### NOC interpretation")

for _, row in visible_results_df.iterrows():
    with st.container(border=True):
        st.markdown(f"#### Route {row['route']} — {row['status']}")

        detail_col_1, detail_col_2, detail_col_3, detail_col_4 = st.columns(4)
        detail_col_1.metric("ASR", f"{row['asr']}%")
        detail_col_2.metric("Average PDD", f"{row['average_pdd']}s")
        detail_col_3.metric("Main SIP code", row["main_sip_code"])
        detail_col_4.metric("Missing RBT", f"{row['missing_rbt_ratio']}%")

        if row["fas_suspected"]:
            st.error(
                f"Possible FAS detected: {row['short_answered_calls']} short answered calls "
                f"({row['short_answered_ratio']}% of answered calls)."
            )
        elif row["average_pdd"] > 5:
            st.warning("High PDD detected. The route may have slow call setup.")
        elif row["missing_rbt_ratio"] > 20:
            st.warning("Missing RBT detected. Caller experience may be affected.")
        else:
            st.success("No major issue detected in the current sample.")

        st.write("**Recommendation:**", row["recommendation"])


# -----------------------------
# Raw data
# -----------------------------

with st.expander("Show raw call logs"):
    st.dataframe(call_logs_df, use_container_width=True, hide_index=True)


# -----------------------------
# Footer
# -----------------------------

st.divider()
st.caption(
    "Prototype scope: CSV-based analysis only. Future improvements could include SIP trace parsing, "
    "audio/RBT validation, scheduled testing and real-time monitoring integration."
)
