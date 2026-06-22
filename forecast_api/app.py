import json
import pickle
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request

MODEL_PATH = "model.pkl"
LOG_DIR = Path("../pred_log")
LOG_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

FEATURES = list(model.feature_names_in_)


@app.route("/predict", methods=["POST"])
def predict():
    body = request.get_json(force=True)
    missing = [f for f in FEATURES if f not in body]
    if missing:
        return jsonify({"error": f"Features faltantes: {missing}"}), 400

    row = pd.DataFrame([{f: body[f] for f in FEATURES}])
    prediction = int(model.predict(row)[0])

    entry = {
        "datetime": datetime.now(timezone.utc).isoformat(),
        "prediction": prediction,
        **row.to_dict(orient="records")[0],
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    (LOG_DIR / f"{ts}_{uuid.uuid4().hex[:8]}.json").write_text(json.dumps(entry))
    return jsonify(entry)



if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5000)
