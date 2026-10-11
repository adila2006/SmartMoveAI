
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Event Setup",
    page_icon="📍",
    layout="wide"
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
DATA_FILE = DATA_DIR / "locations.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)

st.title("📍 Event and Transport Setup")
st.write(
    "Configure any event's transport network. "
    "Add, edit, or remove locations as required."
)

st.info(
    "The initial locations are sample data. Replace them "
    "with the actual locations and transport information "
    "for your event."
)

# Create sample configuration only on the first run
# Create an empty configuration for a new transport network
if not DATA_FILE.exists():
    empty_data = pd.DataFrame({
        "location": [],
        "available_buses": [],
        "minimum_buses": [],
        "bus_capacity": [],
        "transfer_time_min": []
    })

    empty_data.to_csv(DATA_FILE, index=False)

# Load saved transport locations
locations = pd.read_csv(DATA_FILE)

st.subheader("Transport Locations")

edited_locations = st.data_editor(
    locations,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="locations_editor",
    column_config={
        "location": st.column_config.TextColumn(
            "Location Name",
            required=True
        ),
        "available_buses": st.column_config.NumberColumn(
            "Available Buses",
            min_value=0,
            step=1,
            required=True
        ),
        "minimum_buses": st.column_config.NumberColumn(
            "Minimum Buses to Keep",
            min_value=0,
            step=1,
            required=True
        ),
        "bus_capacity": st.column_config.NumberColumn(
            "Passengers per Bus",
            min_value=1,
            step=1,
            required=True
        ),
        "transfer_time_min": st.column_config.NumberColumn(
            "Transfer Time (Minutes)",
            min_value=0,
            step=1,
            required=True
        )
    }
)

# Validate entries
valid = True

if edited_locations.empty:
    st.error("Add at least one transport location.")
    valid = False

elif (
    edited_locations["location"].isna().any()
    or edited_locations["location"].astype(str).str.strip().eq("").any()
):
    st.error("Every location must have a name.")
    valid = False

elif edited_locations["location"].duplicated().any():
    st.error("Each location must have a unique name.")
    valid = False

else:
    numeric_columns = [
        "available_buses",
        "minimum_buses",
        "bus_capacity",
        "transfer_time_min"
    ]

    if edited_locations[numeric_columns].isna().any().any():
        st.error("Complete all numeric fields.")
        valid = False

    elif (
        (edited_locations[numeric_columns] < 0).any().any()
        or (edited_locations["bus_capacity"] < 1).any()
        or (
            edited_locations["minimum_buses"]
            > edited_locations["available_buses"]
        ).any()
    ):
        st.error(
            "Check your values. Bus counts and travel times "
            "cannot be negative, capacity must be positive, "
            "and minimum buses cannot exceed available buses."
        )
        valid = False

    elif not all(
        (edited_locations[column] % 1 == 0).all()
        for column in [
            "available_buses",
            "minimum_buses",
            "bus_capacity",
            "transfer_time_min"
        ]
    ):
        st.error("Bus counts, capacity, and travel times must be whole numbers.")
        valid = False

if valid:
    edited_locations["location"] = (
        edited_locations["location"].astype(str).str.strip()
    )

    # Save changes automatically when the editor changes
    edited_locations.to_csv(DATA_FILE, index=False)

    st.success("Transport configuration is valid and saved.")

    total_buses = int(edited_locations["available_buses"].sum())

    col1, col2 = st.columns(2)
    col1.metric("Number of Locations", len(edited_locations))
    col2.metric("Total Available Buses", total_buses)

    st.caption(
        "Changes are saved to data/locations.csv. "
        "Transfer times should be based on realistic route estimates."
    )