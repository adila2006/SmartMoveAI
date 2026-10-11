
import pandas as pd
import joblib

from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data" / "crowd_data.csv"
MODEL_DIR = PROJECT_DIR / "models"
MODEL_FILE = MODEL_DIR / "crowd_model.joblib"

print("--- FestivalMind AI Model Training ---")

# Load the existing crowd dataset
data = pd.read_csv(DATA_FILE)

required_columns = [
    "location",
    "time_slot",
    "event_level",
    "day_type",
    "passenger_count"
]

if not all(column in data.columns for column in required_columns):
    raise ValueError(
        "crowd_data.csv must contain: "
        + ", ".join(required_columns)
    )

# Convert time such as 16:30 into minutes after midnight
def convert_time(value):
    hours, minutes = map(int, str(value).split(":"))
    return hours * 60 + minutes

data["time_minutes"] = data["time_slot"].apply(convert_time)

# Add scenario variations for prototype testing.
# These are assumptions, not real measured weather data.
scenarios = []

for _, row in data.iterrows():
    for rain in [0, 1]:
        for delay in [0, 15, 30, 45]:
            new_row = row.copy()

            new_row["rain"] = rain
            new_row["event_delay_minutes"] = delay

            # Assumption for demonstration:
            # rain increases bus-passenger demand estimate by 10%.
            if rain == 1:
                new_row["passenger_count"] = (
                    float(row["passenger_count"]) * 1.10
                )

            scenarios.append(new_row)

training_data = pd.DataFrame(scenarios)

features = [
    "location",
    "time_minutes",
    "event_level",
    "day_type",
    "rain",
    "event_delay_minutes"
]

X = training_data[features]
y = training_data["passenger_count"]

preprocessor = ColumnTransformer(
    transformers=[
        (
            "location",
            OneHotEncoder(handle_unknown="ignore"),
            ["location"]
        )
    ],
    remainder="passthrough"
)

model = Pipeline([
    ("preprocessor", preprocessor),
    (
        "regressor",
        RandomForestRegressor(
            n_estimators=150,
            random_state=42
        )
    )
])

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42
)

model.fit(X_train, y_train)

predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

# Train the final model using all generated training rows
model.fit(X, y)

MODEL_DIR.mkdir(parents=True, exist_ok=True)
joblib.dump(model, MODEL_FILE)

print("Training completed successfully.")
print("Original dataset rows:", len(data))
print("Prototype scenario rows:", len(training_data))
print("Test MAE:", round(mae, 2))
print("Model saved to:", MODEL_FILE)
print(
    "Note: Rainfall effects use a demonstration assumption. "
    "The score is not real-world validation."
)