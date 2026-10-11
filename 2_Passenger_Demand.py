
import streamlit as st
import pandas as pd
from pathlib import Path
import math

# --------------------------------------------------
# 1. FILE PATH
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "bus_stops.csv"

st.set_page_config(
    page_title="Passenger Demand Planning",
    page_icon="👥",
    layout="wide"
)

st.title("👥 Passenger Demand Planning")

st.write(
    "Estimate how many festival visitors may use buses and compare "
    "passenger demand with one-trip bus capacity at each location."
)

# --------------------------------------------------
# 2. LOAD DATA
# --------------------------------------------------

if not DATA_FILE.exists():
    st.error(f"Bus data file not found: {DATA_FILE}")
    st.stop()

try:
    buses = pd.read_csv(DATA_FILE)
except Exception as error:
    st.error(f"Could not read bus_stops.csv: {error}")
    st.stop()

required_columns = [
    "stop_id",
    "stop_name",
    "initial_buses",
    "demand_level",
    "min_buses",
    "passenger_demand",
    "bus_capacity"
]

missing_columns = [
    col for col in required_columns if col not in buses.columns
]

if missing_columns:
    st.error(
        "Missing columns in bus_stops.csv: "
        + ", ".join(missing_columns)
    )
    st.stop()

if buses.empty:
    st.warning("No bus stops are configured.")
    st.stop()

buses["stop_name"] = buses["stop_name"].astype("string").str.strip()

if buses["stop_name"].isna().any() or (buses["stop_name"] == "").any():
    st.error("Every bus stop must have a name.")
    st.stop()

if buses["stop_name"].duplicated().any():
    st.error("Bus stop names must be unique.")
    st.stop()

numeric_columns = [
    "initial_buses",
    "min_buses",
    "passenger_demand",
    "bus_capacity"
]

for col in numeric_columns:
    buses[col] = pd.to_numeric(buses[col], errors="coerce")

if buses[numeric_columns].isna().any().any():
    st.error("Some bus counts, demand values, or capacities are invalid.")
    st.stop()

if (buses[numeric_columns] < 0).any().any():
    st.error("Bus counts, demand, and capacity cannot be negative.")
    st.stop()

if (
    (buses["initial_buses"] % 1 != 0).any()
    or (buses["min_buses"] % 1 != 0).any()
):
    st.error("Bus counts and minimum requirements must be whole numbers.")
    st.stop()

if (buses["min_buses"] > buses["initial_buses"]).any():
    st.error(
        "A minimum bus requirement exceeds the current bus allocation."
    )
    st.stop()

if (buses["bus_capacity"] <= 0).any():
    st.error("Bus capacity must be greater than zero.")
    st.stop()

buses["initial_buses"] = buses["initial_buses"].astype(int)

# --------------------------------------------------
# 3. PASSENGER DEMAND INPUTS
# --------------------------------------------------

st.subheader("1. Festival Attendance Assumptions")

col1, col2 = st.columns(2)

with col1:
    visitors = st.number_input(
        "Expected festival visitors",
        min_value=0,
        max_value=1_000_000,
        value=40000,
        step=1000
    )

with col2:
    bus_user_percent = st.slider(
        "Estimated visitors using buses (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5
    )

total_bus_passengers = round(
    visitors * bus_user_percent / 100
)

st.metric(
    "Estimated Bus Passengers",
    f"{total_bus_passengers:,}"
)

# --------------------------------------------------
# 4. DISTRIBUTE ESTIMATED PASSENGERS
# --------------------------------------------------

# Existing passenger_demand figures act as relative weights.
# They are not treated as verified live counts.

weights = buses["passenger_demand"].astype(float)

if weights.sum() > 0:
    shares = weights / weights.sum()
else:
    shares = pd.Series(
        [1 / len(buses)] * len(buses),
        index=buses.index
    )

estimated_demand = [
    int(round(total_bus_passengers * share))
    for share in shares
]

# Correct rounding so the row values sum to the total estimate.
difference = total_bus_passengers - sum(estimated_demand)

if estimated_demand:
    estimated_demand[0] += difference

# --------------------------------------------------
# 5. CALCULATE CAPACITY
# --------------------------------------------------

results = buses.copy()

results["Estimated Passenger Demand"] = estimated_demand

results["Current Bus Capacity"] = (
    results["initial_buses"] * results["bus_capacity"]
).round().astype(int)

results["Estimated Unserved Passengers"] = [
    max(
        0,
        int(
            results.iloc[i]["Estimated Passenger Demand"]
            - results.iloc[i]["Current Bus Capacity"]
        )
    )
    for i in range(len(results))
]

results["Estimated Buses Needed for One Trip"] = [
    math.ceil(
        results.iloc[i]["Estimated Passenger Demand"]
        / results.iloc[i]["bus_capacity"]
    )
    for i in range(len(results))
]

# --------------------------------------------------
# 6. SUMMARY
# --------------------------------------------------

st.subheader("2. Demand and Capacity Summary")

total_buses = int(results["initial_buses"].sum())
total_capacity = int(results["Current Bus Capacity"].sum())
total_unserved = int(results["Estimated Unserved Passengers"].sum())

col1, col2, col3, col4 = st.columns(4)

col1.metric("Configured Bus Stops", len(results))
col2.metric("Existing Buses", total_buses)
col3.metric("Estimated Bus Passengers", f"{total_bus_passengers:,}")
col4.metric("One-Trip Capacity", f"{total_capacity:,}")

# --------------------------------------------------
# 7. RESULTS TABLE
# --------------------------------------------------

st.subheader("3. Location-wise Passenger Demand")

display_results = results[
    [
        "stop_name",
        "initial_buses",
        "min_buses",
        "Estimated Passenger Demand",
        "Current Bus Capacity",
        "Estimated Buses Needed for One Trip",
        "Estimated Unserved Passengers"
    ]
].rename(columns={
    "stop_name": "Bus Stop",
    "initial_buses": "Current Buses",
    "min_buses": "Minimum Buses"
})

st.dataframe(
    display_results,
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# 8. CHART
# --------------------------------------------------

st.subheader("4. Passenger Demand vs Bus Capacity")

chart_data = results.set_index("stop_name")[
    [
        "Estimated Passenger Demand",
        "Current Bus Capacity"
    ]
]

st.bar_chart(chart_data)

# --------------------------------------------------
# 9. INTERPRETATION
# --------------------------------------------------

st.subheader("5. Planning Insight")

if total_bus_passengers == 0:
    st.info(
        "The current inputs estimate no bus passengers. "
        "Increase the visitor estimate or bus-use percentage "
        "to examine a festival scenario."
    )
elif total_unserved > 0:
    st.warning(
        f"The estimate exceeds one-trip bus capacity by "
        f"{total_unserved:,} passengers across the locations. "
        "Review the bus allocation, passenger distribution, and "
        "whether buses can complete additional trips."
    )
else:
    st.success(
        "The estimated demand fits within the combined one-trip "
        "bus capacity. Check the individual locations as well."
    )

st.info(
    "This page uses the passenger_demand values in bus_stops.csv "
    "as relative weights to distribute the total estimated bus "
    "passengers. These weights are sample assumptions, not verified "
    "passenger counts. Capacity assumes one trip per bus and does "
    "not account for repeat trips, boarding time, or buses in transit."
)