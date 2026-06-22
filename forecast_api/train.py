import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

CSV_PATH = "../data/creditcard.csv"
MODEL_PATH = "model.pkl"
TRAIN_PATH = "../data/train.csv"
TEST_PATH = "../data/test.csv"

df = pd.read_csv(CSV_PATH)

train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

train_df.to_csv(TRAIN_PATH, index=False)
test_df.to_csv(TEST_PATH, index=False)

X_train = train_df.drop(columns=["Class"])
y_train = train_df["Class"]

model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

with open(MODEL_PATH, "wb") as f:
    pickle.dump(model, f)

print(f"Train guardado en {TRAIN_PATH} ({len(train_df)} filas)")
print(f"Test guardado en {TEST_PATH} ({len(test_df)} filas)")
print(f"Modelo guardado en {MODEL_PATH}")
