


import streamlit as st
import pandas as pd
import joblib
from pathlib import Path

# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODEL_FILE = PROJECT_DIR / "models" / "crowd_model.joblib"
LOCATIONS_FILE = PROJECT_DIR / "data" / "locations.csv"

# --------------------------------------------------
# 2. PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Crowd Prediction",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Festival Crowd Demand Prediction")

st.write(
    "Estimate passenger demand at each configured transport "
    "location and compare it with available bus capacity."
)

# --------------------------------------------------
# 3. CHECK REQUIRED FILES
# --------------------------------------------------

if not MODEL_FILE.exists():
    st.error(
        "Crowd prediction model not found. "
        "Run train_model.py from your project folder first."
    )
    st.stop()

if not LOCATIONS_FILE.exists():
    st.error(
        "locations.csv was not found in the data folder. "
        "Open Event Setup and configure your transport locations."
    )
    st.stop()

# --------------------------------------------------
# 4. LOAD AND VALIDATE LOCATION DATA
# --------------------------------------------------

try:
    locations = pd.read_csv(LOCATIONS_FILE)
except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
    st.error(f"Could not read locations.csv: {error}")
    st.stop()

required_columns = [
    "location",
    "available_buses",
    "minimum_buses",
    "bus_capacity",
    "transfer_time_min"
]

missing_columns = [
    column for column in required_columns
    if column not in locations.columns
]

if missing_columns:
    st.error(
        "The locations.csv file is missing these columns: "
        + ", ".join(missing_columns)
    )
    st.stop()

if locations.empty:
    st.warning(
        "No locations are configured. "
        "Open Event Setup and add at least one location."
    )
    st.stop()

locations["location"] = (
    locations["location"].astype("string").str.strip()
)

if locations["location"].isna().any() or (
    locations["location"] == ""
).any():
    st.error("Every location must have a name.")
    st.stop()

if locations["location"].duplicated().any():
    st.error(
        "Duplicate location names found. "
        "Give every transport location a unique name in Event Setup."
    )
    st.stop()

numeric_columns = [
    "available_buses",
    "minimum_buses",
    "bus_capacity",
    "transfer_time_min"
]

for column in numeric_columns:
    locations[column] = pd.to_numeric(
        locations[column], errors="coerce"
    )

if locations[numeric_columns].isna().any().any():
    st.error(
        "Some location settings are missing or non-numeric. "
        "Correct the values in Event Setup."
    )
    st.stop()

if (locations[numeric_columns] < 0).any().any():
    st.error("Bus counts, capacity, and travel time cannot be negative.")
    st.stop()

if (locations["available_buses"] % 1 != 0).any():
    st.error("Available bus counts must be whole numbers.")
    st.stop()

if (locations["minimum_buses"] % 1 != 0).any():
    st.error("Minimum bus counts must be whole numbers.")
    st.stop()

if (
    locations["minimum_buses"] > locations["available_buses"]
).any():
    st.error(
        "A minimum bus requirement exceeds the available bus count. "
        "Correct this in Event Setup."
    )
    st.stop()

if (locations["bus_capacity"] <= 0).any():
    st.error("Bus capacity must be greater than zero.")
    st.stop()

# --------------------------------------------------
# 5. LOAD TRAINED MODEL
# --------------------------------------------------

try:
    model = joblib.load(MODEL_FILE)
except Exception as error:
    st.error(f"Could not load the prediction model: {error}")
    st.stop()

# --------------------------------------------------
# 6. SELECT EVENT CONDITIONS
# --------------------------------------------------

st.subheader("Current Event Conditions")

col1, col2, col3 = st.columns(3)

with col1:
    event_level = st.selectbox(
        "Event intensity",
        options=[1, 2, 3],
        format_func=lambda value: {
            1: "Low",
            2: "Medium",
            3: "High"
        }[value],
        index=1
    )

with col2:
    day_type = st.selectbox(
        "Day type",
        options=[0, 1],
        format_func=lambda value: {
            0: "Normal day",
            1: "Festival / event day"
        }[value],
        index=1
    )

with col3:
    rain = st.selectbox(
        "Rain condition",
        options=[0, 1],
        format_func=lambda value: {
            0: "No rain",
            1: "Rain"
        }[value],
        index=0
    )

event_delay = st.slider(
    "Event delay (minutes)",
    min_value=0,
    max_value=120,
    value=0,
    step=15
)

time_slot = st.selectbox(
    "Time to predict",
    options=[
        "16:00", "16:30", "17:00", "17:30",
        "18:00", "18:30", "19:00", "19:30",
        "20:00", "20:30", "21:00", "21:30"
    ],
    index=4
)

hours, minutes = map(int, time_slot.split(":"))
time_minutes = hours * 60 + minutes

# --------------------------------------------------
# 7. PREPARE MODEL INPUT
# --------------------------------------------------

input_data = pd.DataFrame({
    "location": locations["location"].astype(str).tolist(),
    "time_minutes": [time_minutes] * len(locations),
    "event_level": [event_level] * len(locations),
    "day_type": [day_type] * len(locations),
    "rain": [rain] * len(locations),
    "event_delay_minutes": [event_delay] * len(locations)
})

# --------------------------------------------------
# 8. PREDICT PASSENGER DEMAND
# --------------------------------------------------

try:
    predictions = model.predict(input_data)
except Exception as error:
    st.error(
        "Prediction failed. Check that train_model.py uses the same "
        "feature names and preprocessing as this page. "
        f"Details: {error}"
    )
    st.stop()

results = locations.copy()

results["Predicted Passengers"] = [
    max(0, int(round(float(value))))
    for value in predictions
]

results["Estimated Bus Capacity"] = (
    results["available_buses"] * results["bus_capacity"]
).round().astype(int)

# --------------------------------------------------
# 9. CALCULATE CROWD LEVEL AND CAPACITY STATUS
# --------------------------------------------------

def classify_crowd(row):
    capacity = row["Estimated Bus Capacity"]
    demand = row["Predicted Passengers"]

    if capacity <= 0:
        return "No bus capacity"

    ratio = demand / capacity

    if ratio < 0.5:
        return "Low"
    elif ratio < 0.8:
        return "Medium"
    else:
        return "High"


results["Predicted Crowd Level"] = results.apply(
    classify_crowd, axis=1
)

results["Estimated Passengers Over Capacity"] = (
    results["Predicted Passengers"]
    - results["Estimated Bus Capacity"]
).clip(lower=0)

# --------------------------------------------------
# 10. SHOW SUMMARY METRICS
# --------------------------------------------------

st.subheader("Prediction Summary")

total_buses = int(results["available_buses"].sum())
total_demand = int(results["Predicted Passengers"].sum())
total_capacity = int(results["Estimated Bus Capacity"].sum())
total_over_capacity = int(
    results["Estimated Passengers Over Capacity"].sum()
)

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric("Configured Locations", len(results))
metric2.metric("Available Buses", total_buses)
metric3.metric("Predicted Passengers", f"{total_demand:,}")
metric4.metric("One-Trip Bus Capacity", f"{total_capacity:,}")

# --------------------------------------------------
# 11. DISPLAY RESULTS TABLE
# --------------------------------------------------

st.subheader("Prediction Results")

st.caption(
    "Capacity assumes every available bus can complete one trip "
    "during the selected time slot. This does not account for "
    "boarding time, repeat trips, or buses already in transit."
)

display_columns = results[
    [
        "location",
        "available_buses",
        "minimum_buses",
        "Predicted Passengers",
        "Estimated Bus Capacity",
        "Predicted Crowd Level",
        "Estimated Passengers Over Capacity"
    ]
].rename(columns={
    "location": "Location",
    "available_buses": "Available Buses",
    "minimum_buses": "Minimum Buses to Keep"
})

st.dataframe(
    display_columns,
    use_container_width=True,
    hide_index=True
)

if total_over_capacity > 0:
    st.warning(
        f"Estimated demand exceeds one-trip bus capacity by "
        f"{total_over_capacity:,} passengers across the configured "
        "locations. Consider reviewing the bus allocation."
    )
else:
    st.success(
        "Estimated total demand does not exceed the combined "
        "one-trip capacity. Check each location separately as well."
    )

# --------------------------------------------------
# 12. DISPLAY DEMAND CHART
# --------------------------------------------------

st.subheader("Demand Overview")

chart_data = results.set_index("location")[
    ["Predicted Passengers", "Estimated Bus Capacity"]
]

st.bar_chart(chart_data)

# --------------------------------------------------
# 13. DISPLAY IMPORTANT LIMITATIONS
# --------------------------------------------------

st.info(
    "This is a prototype prediction, not a live passenger counter. "
    "Its reliability depends on the quality of the training data. "
    "Rain and event-delay effects are assumptions in the current "
    "model and must be validated using real observations. "
    "The chart compares predicted passengers with one-trip capacity; "
    "it does not automatically redistribute buses."
)