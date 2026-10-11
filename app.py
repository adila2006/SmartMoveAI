
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="FestivalMind AI",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- DESIGN ----------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    h1, h2, h3 {
        color: #17365D;
    }

    div[data-testid="stMetric"] {
        background-color: #F4F7FB;
        border: 1px solid #E1E8F0;
        padding: 18px;
        border-radius: 12px;
    }

    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }

    .subtitle {
        color: #64748B;
        font-size: 16px;
    }

    .section-card {
        background-color: #F4F7FB;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #E1E8F0;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------- PROJECT DATA ----------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data" / "bus_stops.csv"

# ---------- SIDEBAR ----------
with st.sidebar:
    st.title("🚌 FestivalMind AI")
    st.caption("Festival transport planning")
    st.divider()

    st.markdown("### How to use")

    st.markdown("""
    **1. Home Dashboard**

    View the overall bus situation.

    **2. Bus Redistribution**

    Check travel time and test bus movements.

    **3. Passenger Demand**

    Estimate passengers and bus capacity.

    **4. AI Recommendation**

    Compare allocations and review service trade-offs.
    """)

    st.divider()
    st.caption("Prototype mode • Sample data")

# ---------- HOME DASHBOARD ----------
st.title("Festival Overview")
st.markdown(
    '<p class="subtitle">Understand the current bus distribution '
    'and plan for festival crowd movement.</p>',
    unsafe_allow_html=True
)

try:
    buses = pd.read_csv(DATA_FILE)

    required_columns = {
        "stop_id", "stop_name", "initial_buses",
        "demand_level", "min_buses"
    }

    if not required_columns.issubset(buses.columns):
        st.error("The bus data file is missing required columns.")
        st.stop()

    total_buses = int(buses["initial_buses"].sum())

    main_row = buses[
        buses["stop_name"] == "Main Bus Stand"
    ]
    nearby_row = buses[
        buses["stop_name"] == "Nearby Bus Stop"
    ]

    if main_row.empty or nearby_row.empty:
        st.error("Check the stop names in data/bus_stops.csv.")
        st.stop()

    main_buses = int(main_row.iloc[0]["initial_buses"])
    nearby_buses = int(nearby_row.iloc[0]["initial_buses"])

    st.info(
        "Scenario: approximately 40,000 festival visitors may leave "
        "within two hours. The system explores how existing buses "
        "could be redistributed."
    )

    st.subheader("Current Bus Availability")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Fleet", total_buses, help="All buses in the sample dataset")
    col2.metric("Main Bus Stand", main_buses)
    col3.metric("Nearby Bus Stop", nearby_buses)

    st.caption(
        "The figures below are initial allocations from the sample CSV file."
    )

    st.divider()
    st.subheader("Bus Distribution by Stop")
    st.bar_chart(
        buses.set_index("stop_name")["initial_buses"],
        y_label="Number of buses"
    )

    st.divider()
    st.subheader("Explore the Planning Tools")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="section-card">
        <h3>🚌 Bus Redistribution</h3>
        Check travel time, move buses between stops, and verify
        that the total fleet remains unchanged.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-card">
        <h3>👥 Passenger Demand</h3>
        Estimate how many people may need buses and compare
        demand with available capacity.
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="section-card">
        <h3>🧠 AI Recommendation</h3>
        Compare possible bus allocations and review the suggested
        plan with its service trade-offs.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-card">
        <h3>✅ Planning Checks</h3>
        Keep the fleet total fixed and respect the minimum buses
        required at each stop.
        </div>
        """, unsafe_allow_html=True)

    st.success(
        "Start with Bus Redistribution, then review Passenger Demand "
        "and AI Recommendation using the sidebar."
    )

    st.caption(
        "Important: this is a planning prototype. Crowd, capacity, "
        "and travel-time values are estimates, not live data."
    )

except FileNotFoundError:
    st.error("Cannot find data/bus_stops.csv. Check your project folders.")

except Exception as error:
    st.error(f"Unable to load project data: {error}")