
import streamlit as st
import pandas as pd
import joblib
import math
from pathlib import Path
from itertools import product

# =====================================================
# 1. PAGE SETUP
# =====================================================

st.set_page_config(
    page_title="AI Recommendation",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 AI Bus Redistribution Recommendation")

st.write(
    "Predict passenger demand and recommend how to redistribute "
    "the existing buses across configured transport locations."
)

st.info(
    "This prototype uses a trained crowd prediction model and "
    "a rule-based allocation optimizer. Verify recommendations "
    "against real passenger counts and transport constraints."
)

# =====================================================
# 2. FILE PATHS
# =====================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

LOCATIONS_FILE = PROJECT_DIR / "data" / "locations.csv"
MODEL_FILE = PROJECT_DIR / "models" / "crowd_model.joblib"

# =====================================================
# 3. LOAD AND VALIDATE LOCATIONS
# =====================================================

if not LOCATIONS_FILE.exists():
    st.error("Locations file not found. Open Event Setup first.")
    st.stop()

try:
    locations = pd.read_csv(LOCATIONS_FILE)
except Exception as error:
    st.error(f"Unable to read locations.csv: {error}")
    st.stop()

required_columns = [
    "location",
    "available_buses",
    "minimum_buses",
    "bus_capacity",
    "transfer_time_min"
]

if locations.empty:
    st.warning("No transport locations configured. Open Event Setup.")
    st.stop()

missing_columns = [
    col for col in required_columns
    if col not in locations.columns
]

if missing_columns:
    st.error(f"Missing columns in locations.csv: {missing_columns}")
    st.stop()

locations = locations[required_columns].copy()

locations["location"] = (
    locations["location"].astype(str).str.strip()
)

if locations["location"].eq("").any():
    st.error("Every location must have a name.")
    st.stop()

if locations["location"].duplicated().any():
    st.error("Location names must be unique.")
    st.stop()

numeric_columns = [
    "available_buses",
    "minimum_buses",
    "bus_capacity",
    "transfer_time_min"
]

for column in numeric_columns:
    locations[column] = pd.to_numeric(
        locations[column],
        errors="coerce"
    )

if locations[numeric_columns].isna().any().any():
    st.error("Enter valid numeric values in Event Setup.")
    st.stop()

if (
    (locations["available_buses"] < 0).any()
    or (locations["minimum_buses"] < 0).any()
    or (locations["bus_capacity"] <= 0).any()
    or (locations["transfer_time_min"] < 0).any()
):
    st.error(
        "Bus counts and transfer times cannot be negative. "
        "Bus capacity must be greater than zero."
    )
    st.stop()

for column in ["available_buses", "minimum_buses"]:
    if (locations[column] % 1 != 0).any():
        st.error(f"{column} must contain whole numbers.")
        st.stop()

locations["available_buses"] = (
    locations["available_buses"].astype(int)
)
locations["minimum_buses"] = (
    locations["minimum_buses"].astype(int)
)

if (
    locations["minimum_buses"] > locations["available_buses"]
).any():
    st.error(
        "A location's minimum buses cannot exceed its current buses."
    )
    st.stop()

# =====================================================
# 4. NETWORK INFORMATION
# =====================================================

names = locations["location"].tolist()
initial_buses = locations["available_buses"].tolist()
minimum_buses = locations["minimum_buses"].tolist()
capacities = locations["bus_capacity"].tolist()
transfer_times = locations["transfer_time_min"].tolist()

number_of_locations = len(locations)
total_buses = sum(initial_buses)

if total_buses < sum(minimum_buses):
    st.error("The existing fleet cannot satisfy all minimum requirements.")
    st.stop()

st.subheader("1. Current Transport Network")

col1, col2, col3 = st.columns(3)

col1.metric("Configured Locations", number_of_locations)
col2.metric("Total Existing Fleet", total_buses)
col3.metric(
    "Buses Above Minimum Requirements",
    total_buses - sum(minimum_buses)
)

st.dataframe(
    locations,
    use_container_width=True,
    hide_index=True
)

# =====================================================
# 5. EVENT CONDITIONS
# =====================================================

st.divider()
st.subheader("2. Current Event Conditions")

col1, col2, col3 = st.columns(3)

with col1:
    event_level = st.selectbox(
        "Event intensity",
        [1, 2, 3],
        index=1,
        format_func=lambda x: {
            1: "Low",
            2: "Medium",
            3: "High"
        }[x]
    )

with col2:
    day_type = st.selectbox(
        "Day type",
        [0, 1],
        index=1,
        format_func=lambda x: {
            0: "Normal day",
            1: "Festival / event day"
        }[x]
    )

with col3:
    rain = st.selectbox(
        "Rain condition",
        [0, 1],
        index=0,
        format_func=lambda x: {
            0: "No rain",
            1: "Rain"
        }[x]
    )

event_delay = st.slider(
    "Event delay (minutes)",
    min_value=0,
    max_value=120,
    value=0,
    step=15
)

time_slot = st.selectbox(
    "Prediction time",
    [
        "16:00", "16:30", "17:00", "17:30",
        "18:00", "18:30", "19:00", "19:30",
        "20:00", "20:30", "21:00", "21:30"
    ],
    index=4
)

# =====================================================
# 6. PREDICT PASSENGER DEMAND
# =====================================================

st.divider()
st.subheader("3. Estimated Passenger Demand")

if not MODEL_FILE.exists():
    st.error("Crowd prediction model not found. Run train_model.py.")
    st.stop()

try:
    model = joblib.load(MODEL_FILE)
except Exception as error:
    st.error(f"Unable to load the crowd model: {error}")
    st.stop()

hours, minutes = map(int, time_slot.split(":"))
selected_minutes = hours * 60 + minutes

# Estimate demand at the time shifted by the event delay.
effective_time = (selected_minutes + event_delay) % (24 * 60)

prediction_input = pd.DataFrame({
    "location": names,
    "time_minutes": [effective_time] * number_of_locations,
    "event_level": [event_level] * number_of_locations,
    "day_type": [day_type] * number_of_locations,
    "rain": [rain] * number_of_locations,
    "event_delay_minutes": [event_delay] * number_of_locations
})

try:
    predictions = model.predict(prediction_input)
except Exception as error:
    st.error(f"Demand prediction failed: {error}")
    st.stop()

locations["Predicted Passengers"] = [
    max(0, int(round(float(value))))
    for value in predictions
]

locations["Current One-Trip Capacity"] = [
    initial_buses[i] * capacities[i]
    for i in range(number_of_locations)
]

locations["Estimated Required Buses"] = [
    max(
        minimum_buses[i],
        math.ceil(
            locations.iloc[i]["Predicted Passengers"]
            / capacities[i]
        )
    )
    for i in range(number_of_locations)
]

locations["Current Status"] = [
    (
        "High demand"
        if locations.iloc[i]["Predicted Passengers"]
        > locations.iloc[i]["Current One-Trip Capacity"]
        else "Within capacity"
    )
    for i in range(number_of_locations)
]

st.dataframe(
    locations[
        [
            "location",
            "available_buses",
            "Predicted Passengers",
            "Current One-Trip Capacity",
            "Estimated Required Buses",
            "Current Status"
        ]
    ].rename(columns={
        "location": "Location",
        "available_buses": "Current Buses"
    }),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Predictions use a small simulated dataset. Results are prototype "
    "estimates and are not validated real-world forecasts."
)

# =====================================================
# 7. ALLOCATION OPTIMIZER
# =====================================================

st.divider()
st.subheader("4. Recommended Bus Redistribution")

demand = locations["Predicted Passengers"].astype(int).tolist()

def evaluate_allocation(allocation):
    """Calculate demand shortfall and movement for an allocation."""

    unmet = []

    for i, bus_count in enumerate(allocation):
        available_capacity = bus_count * capacities[i]
        shortfall = max(0, demand[i] - available_capacity)
        unmet.append(int(shortfall))

    # Relative shortfall measures the proportion of demand left unmet.
    relative_shortfalls = [
        unmet[i] / max(demand[i], 1)
        for i in range(number_of_locations)
    ]

    moved = sum(
        max(0, initial_buses[i] - allocation[i])
        for i in range(number_of_locations)
    )

    # Priorities:
    # 1. Reduce the worst relative shortfall.
    # 2. Reduce total unmet passengers.
    # 3. Move fewer buses if the results are tied.
    score = (
        max(relative_shortfalls),
        sum(unmet),
        moved
    )

    return {
        "allocation": tuple(allocation),
        "unmet": unmet,
        "total_unmet": sum(unmet),
        "moved": moved,
        "score": score
    }

# The minimum allocation is fixed first.
# Remaining buses can be assigned to any configured location.
remaining_buses = total_buses - sum(minimum_buses)

# The number of possible distributions is:
# C(remaining buses + locations - 1, locations - 1).
# Search all distributions when manageable. For larger networks,
# use a local-search fallback rather than freezing the app.
def count_distributions(balls, boxes, limit=200001):
    if boxes <= 1:
        return 1
    result = 1
    for j in range(1, boxes):
        result = result * (balls + j) // j
        if result > limit:
            return result
    return result

search_size = count_distributions(
    remaining_buses,
    number_of_locations
)

best = None
search_method = ""

if search_size <= 200000:
    # Exhaustively compare all valid allocations.
    ranges = [
        range(minimum_buses[i], total_buses + 1)
        for i in range(number_of_locations)
    ]

    for allocation in product(*ranges):
        if sum(allocation) != total_buses:
            continue

        candidate = evaluate_allocation(allocation)

        if best is None or candidate["score"] < best["score"]:
            best = candidate

    search_method = "Exhaustive allocation search"

else:
    # Large network fallback:
    # Start from the current allocation and repeatedly try one-bus
    # transfers, accepting the best improvement each round.
    current = list(initial_buses)
    best = evaluate_allocation(current)

    improved = True
    iterations = 0
    max_iterations = total_buses * number_of_locations * 10

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1
        round_best = best

        for source in range(number_of_locations):
            if current[source] <= minimum_buses[source]:
                continue

            for target in range(number_of_locations):
                if source == target:
                    continue

                trial = current.copy()
                trial[source] -= 1
                trial[target] += 1

                candidate = evaluate_allocation(trial)

                if candidate["score"] < round_best["score"]:
                    round_best = candidate

        if round_best["score"] < best["score"]:
            best = round_best
            current = list(best["allocation"])
            improved = True

    search_method = "Local-search allocation (large network)"

if best is None:
    st.error("Unable to find a valid allocation.")
    st.stop()

recommended = list(best["allocation"])

st.caption(f"Optimization method: {search_method}")

# =====================================================
# 8. DISPLAY RECOMMENDED ALLOCATION
# =====================================================

recommendation_table = pd.DataFrame({
    "Location": names,
    "Current Buses": initial_buses,
    "Minimum Buses": minimum_buses,
    "Predicted Demand": demand,
    "Recommended Buses": recommended,
    "Recommended One-Trip Capacity": [
        recommended[i] * capacities[i]
        for i in range(number_of_locations)
    ],
    "Buses Added / Removed": [
        recommended[i] - initial_buses[i]
        for i in range(number_of_locations)
    ],
    "Estimated Unmet Passengers": best["unmet"],
    "Transfer Time (min)": transfer_times
})

st.dataframe(
    recommendation_table,
    use_container_width=True,
    hide_index=True
)

col1, col2, col3 = st.columns(3)

col1.metric("Total Fleet", total_buses)
col2.metric("Estimated Unmet Passengers", best["total_unmet"])
col3.metric("Buses Relocated", best["moved"])

# =====================================================
# 9. EXPLAIN BUS MOVEMENTS
# =====================================================

st.subheader("Service Trade-off")

donors = [
    [i, initial_buses[i] - recommended[i]]
    for i in range(number_of_locations)
    if initial_buses[i] > recommended[i]
]

receivers = [
    [i, recommended[i] - initial_buses[i]]
    for i in range(number_of_locations)
    if recommended[i] > initial_buses[i]
]

if not donors and not receivers:
    st.success(
        "No relocation was selected. The current allocation is the "
        "best option under the optimizer's current scoring priorities."
    )
else:
    donor_index = 0
    receiver_index = 0

    while donor_index < len(donors) and receiver_index < len(receivers):
        source, source_count = donors[donor_index]
        target, target_count = receivers[receiver_index]

        move_count = min(source_count, target_count)

        st.write(
            f"**Move {move_count} bus(es) from {names[source]} "
            f"to {names[target]}.** "
            f"{names[source]} will retain {recommended[source]} bus(es), "
            f"and {names[target]} will have {recommended[target]} bus(es). "
            f"Configured transfer time for the source location: "
            f"{transfer_times[source]} minute(s)."
        )

        donors[donor_index][1] -= move_count
        receivers[receiver_index][1] -= move_count

        if donors[donor_index][1] == 0:
            donor_index += 1

        if receivers[receiver_index][1] == 0:
            receiver_index += 1

# =====================================================
# 10. SAFETY CHECKS
# =====================================================

st.divider()
st.subheader("5. Safety and Feasibility Checks")

checks = {
    "Total fleet is preserved":
        sum(recommended) == total_buses,

    "Every location meets its minimum":
        all(
            recommended[i] >= minimum_buses[i]
            for i in range(number_of_locations)
        ),

    "No negative bus allocation":
        all(bus_count >= 0 for bus_count in recommended),

    "Bus movements balance":
        sum(
            max(0, initial_buses[i] - recommended[i])
            for i in range(number_of_locations)
        )
        ==
        sum(
            max(0, recommended[i] - initial_buses[i])
            for i in range(number_of_locations)
        )
}

for check_name, passed in checks.items():
    if passed:
        st.success(f"PASS — {check_name}")
    else:
        st.error(f"FAIL — {check_name}")

# =====================================================
# 11. FINAL NOTES
# =====================================================

st.caption(
    "Capacity assumes one trip per bus. This prototype does not yet "
    "validate real traffic, passenger counts, bus routes, or whether "
    "a bus can reach another location in time. Transfer time is shown "
    "for planning but is not included in the optimization score."
)