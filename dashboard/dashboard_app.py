"""
RiverGuardian AI
Module 12: Local Dashboard

Purpose:
    Display latest RiverGuardian AI status from local SQLite database.

Run:
    streamlit run dashboard_app.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def database_path() -> Path:
    return project_root() / "data" / "riverguardian.db"


def fetch_latest_records(limit: int = 200) -> pd.DataFrame:
    db_path = database_path()

    if not db_path.exists():
        return pd.DataFrame()

    with sqlite3.connect(db_path) as conn:
        query = """
        SELECT
            id,
            created_time_s,
            node_id,
            distance_cm,
            clearance_cm,
            rise_rate_cm_min,
            time_to_unsafe_min,
            fused_risk,
            rainfall_class,
            rain_hourly_mm,
            rain_daily_mm,
            confidence_score,
            confidence_level,
            recommendation_status,
            public_message,
            alert_should_send,
            alert_type
        FROM monitoring_records
        ORDER BY created_time_s DESC
        LIMIT ?;
        """

        df = pd.read_sql_query(query, conn, params=(limit,))

    if not df.empty:
        df["created_datetime"] = pd.to_datetime(df["created_time_s"], unit="s")
        df = df.sort_values("created_time_s")

    return df


def risk_badge(risk: str) -> str:
    if risk == "GREEN":
        return "🟢 GREEN"
    if risk == "YELLOW":
        return "🟡 YELLOW"
    if risk == "ORANGE":
        return "🟠 ORANGE"
    if risk == "RED":
        return "🔴 RED"
    return "⚪ UNKNOWN"


def main() -> None:
    st.set_page_config(
        page_title="RiverGuardian AI Dashboard",
        page_icon="🌊",
        layout="wide",
    )

    st.title("🌊 RiverGuardian AI Dashboard")
    st.caption("Edge Physical AI bridge flood-access monitoring system")

    df = fetch_latest_records(limit=300)

    if df.empty:
        st.warning("No database records found yet. Run `python main_runtime.py` first.")
        return

    latest = df.iloc[-1]

    st.subheader("Current Bridge Status")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Risk", risk_badge(str(latest["fused_risk"])))

    with col2:
        st.metric("Clearance", f"{latest['clearance_cm']:.1f} cm")

    with col3:
        st.metric("Rise Rate", f"{latest['rise_rate_cm_min']:.2f} cm/min")

    with col4:
        confidence = latest["confidence_score"]
        st.metric("Confidence", f"{int(confidence)}%")

    st.info(str(latest["public_message"]))

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Bridge Clearance Trend")
        st.line_chart(
            df.set_index("created_datetime")[["clearance_cm"]],
            use_container_width=True,
        )

    with col_b:
        st.subheader("River Rise Rate")
        st.line_chart(
            df.set_index("created_datetime")[["rise_rate_cm_min"]],
            use_container_width=True,
        )

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Hourly Rainfall")
        st.line_chart(
            df.set_index("created_datetime")[["rain_hourly_mm"]],
            use_container_width=True,
        )

    with col_d:
        st.subheader("Confidence Score")
        st.line_chart(
            df.set_index("created_datetime")[["confidence_score"]],
            use_container_width=True,
        )

    st.divider()

    st.subheader("Latest Records")

    display_cols = [
        "id",
        "created_datetime",
        "node_id",
        "fused_risk",
        "clearance_cm",
        "rise_rate_cm_min",
        "time_to_unsafe_min",
        "rain_hourly_mm",
        "confidence_score",
        "alert_should_send",
        "alert_type",
    ]

    st.dataframe(
        df[display_cols].sort_values("id", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    with st.expander("Latest raw record"):
        st.json(latest.to_dict())


if __name__ == "__main__":
    main()