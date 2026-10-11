
import streamlit as st
import pandas as pd
from pathlib import Path
from itertools import product

# --------------------------------------------------
# 1. FILE PATH
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "bus_stops.csv"

st.set_page_config(
    page_title="Bus Redistribution",
    page_icon="🚌",
    layout="wide"
)

st.title("🚌 Bus Redistribution")
st.write(
    "Plan bus movements across configured Madurai bus stops "
    "without adding buses or violating minimum service levels."
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
        "A minimum bus requirement exceeds the current allocation. "
        "Correct the data before redistribution."
    )
    st.stop()

if (buses["bus_capacity"] <= 0).any():
    st.error("Bus capacity must be greater than zero.")
    st.stop()

buses["initial_buses"] = buses["initial_buses"].astype(int)
buses["min_buses"] = buses["min_buses"].astype(int)

# --------------------------------------------------
# 3. CURRENT NETWORK
# --------------------------------------------------

current = buses["initial_buses"].tolist()
minimum = buses["min_buses"].tolist()
demand = buses["passenger_demand"].astype(float).tolist()
capacity = buses["bus_capacity"].astype(float).tolist()
names = buses["stop_name"].astype(str).tolist()

total_fleet = sum(current)
minimum_total = sum(minimum)

if minimum_total > total_fleet:
    st.error(
        "The sum of minimum bus requirements exceeds the existing fleet."
    )
    st.stop()

st.subheader("1. Current Transport Network")

col1, col2, col3 = st.columns(3)
col1.metric("Configured Bus Stops", len(names))
col2.metric("Total Existing Fleet", total_fleet)
col3.metric("Buses Above Minimum", total_fleet - minimum_total)

current_table = pd.DataFrame({
    "Bus Stop": names,
    "Current Buses": current,
    "Minimum Buses": minimum,
    "Estimated Passengers": demand,
    "Capacity per Bus": capacity
})

st.dataframe(current_table, use_container_width=True, hide_index=True)

# --------------------------------------------------
# 4. ADJUST DEMAND ASSUMPTION
# --------------------------------------------------

st.subheader("2. Demand Conditions")

event_level = st.selectbox(
    "Expected event intensity",
    ["Low", "Medium", "High"],
    index=1
)

demand_factor = {
    "Low": 0.75,
    "Medium": 1.0,
    "High": 1.5
}[event_level]

adjusted_demand = [value * demand_factor for value in demand]

st.caption(
    "The demand values come from bus_stops.csv. "
    "The selected event intensity applies a simple planning multiplier; "
    "it is not a live passenger forecast."
)

# --------------------------------------------------
# 5. GENERATE VALID ALLOCATIONS
# --------------------------------------------------

def generate_allocations(minimum_counts, fleet_count):
    """
    Generate every whole-number allocation that meets minimum
    requirements and preserves the total fleet.
    """
    count = len(minimum_counts)
    extra_buses = fleet_count - sum(minimum_counts)

    def distribute(index, remaining, allocation):
        if index == count - 1:
            yield allocation + [minimum_counts[index] + remaining]
            return

        for extra in range(remaining + 1):
            yield from distribute(
                index + 1,
                remaining - extra,
                allocation + [minimum_counts[index] + extra]
            )

    yield from distribute(0, extra_buses, [])

# --------------------------------------------------
# 6. FIND BEST ALLOCATION
# --------------------------------------------------

def score_allocation(allocation):
    """
    Primary goal: minimize estimated passengers exceeding capacity.
    Secondary goal: move as few buses as possible.
    """
    total_unserved = 0.0

    for i in range(len(names)):
        available_capacity = allocation[i] * capacity[i]
        total_unserved += max(
            0.0,
            adjusted_demand[i] - available_capacity
        )

    moved_buses = sum(
        max(0, current[i] - allocation[i])
        for i in range(len(names))
    )

    return (round(total_unserved, 6), moved_buses)

best_allocation = None
best_score = None

for allocation in generate_allocations(minimum, total_fleet):
    score = score_allocation(allocation)

    if best_score is None or score < best_score:
        best_score = score
        best_allocation = allocation

if best_allocation is None:
    st.error("No feasible allocation could be generated.")
    st.stop()

# --------------------------------------------------
# 7. SHOW RECOMMENDATION
# --------------------------------------------------

st.subheader("3. Recommended Bus Redistribution")

results = pd.DataFrame({
    "Bus Stop": names,
    "Current Buses": current,
    "Recommended Buses": best_allocation,
    "Minimum Required": minimum,
    "Estimated Passengers": [
        round(value) for value in adjusted_demand
    ],
    "Recommended Capacity": [
        int(best_allocation[i] * capacity[i])
        for i in range(len(names))
    ]
})

results["Change in Buses"] = (
    results["Recommended Buses"] - results["Current Buses"]
)

results["Estimated Unserved Passengers"] = [
    max(
        0,
        round(
            adjusted_demand[i]
            - best_allocation[i] * capacity[i]
        )
    )
    for i in range(len(names))
]

st.dataframe(results, use_container_width=True, hide_index=True)

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Total Fleet", total_fleet)
metric2.metric(
    "Estimated Unserved Passengers",
    f"{sum(results['Estimated Unserved Passengers']):,}"
)
metric3.metric("Buses Relocated", int(best_score[1]))

# --------------------------------------------------
# 8. EXPLAIN EACH BUS MOVEMENT
# --------------------------------------------------

st.subheader("4. Service Trade-off")

donors = []

receivers = []

for i in range(len(names)):
    difference = current[i] - best_allocation[i]

    if difference > 0:
        donors.append([i, difference])

    elif difference < 0:
        receivers.append([i, -difference])

if not donors and not receivers:
    st.success(
        "The current allocation is already the best allocation "
        "under the selected demand assumptions. No buses need to move."
    )
else:
    donor_index = 0
    receiver_index = 0

    while donor_index < len(donors) and receiver_index < len(receivers):
        source_index, source_surplus = donors[donor_index]
        target_index, target_need = receivers[receiver_index]

        move_count = min(source_surplus, target_need)

        st.markdown(
            f"**Move {move_count} bus(es) from {names[source_index]} "
            f"to {names[target_index]}.** "
            f"{names[source_index]} will retain "
            f"{best_allocation[source_index]} bus(es), and "
            f"{names[target_index]} will have "
            f"{best_allocation[target_index]} bus(es)."
        )

        donors[donor_index][1] -= move_count
        receivers[receiver_index][1] -= move_count

        if donors[donor_index][1] == 0:
            donor_index += 1

        if receivers[receiver_index][1] == 0:
            receiver_index += 1

# --------------------------------------------------
# 9. SAFETY CHECKS
# --------------------------------------------------

st.subheader("5. Safety and Feasibility Checks")

fleet_preserved = sum(best_allocation) == total_fleet
minimum_met = all(
    best_allocation[i] >= minimum[i]
    for i in range(len(names))
)
no_negative = all(value >= 0 for value in best_allocation)
movements_balance = (
    sum(max(0, value) for value in results["Change in Buses"])
    == sum(max(0, -value) for value in results["Change in Buses"])
)

checks = {
    "Total fleet is preserved": fleet_preserved,
    "Every location meets its minimum": minimum_met,
    "No negative bus allocation": no_negative,
    "Bus movements balance": movements_balance
}

for description, passed in checks.items():
    if passed:
        st.success(f"PASS — {description}")
    else:
        st.error(f"FAIL — {description}")

st.info(
    "This is a prototype recommendation based on the demand figures "
    "in bus_stops.csv. It assumes one trip per bus. It does not verify "
    "live traffic, road distance, actual passenger counts, route "
    "compatibility, or whether a bus can reach its destination in time. "
    "Confirm these constraints with transport operators before acting."
)