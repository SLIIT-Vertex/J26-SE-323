# Learner-state behaviour models: ASSISTments-only field ablation (run on Kaggle)
#
# Copy each "# %%" cell into a Kaggle notebook that has the same dataset attached as the
# original training notebooks (mindbridge-assistments-2012-2013). Run the cells in order.
#
# Purpose
# - Check the numeric coding of `first_action` on the data itself.
# - Retrain the two behaviour models exactly as in mindbridge-behaviour-model-01 and
#   mindbridge-disengagement-model-01, first with all features (must reproduce the published
#   results) and then without fields that MindBridge cannot produce truthfully
#   (`position`, and `first_action` if its coding cannot be confirmed).
#
# Every setting below is copied from those two notebooks: learner-wise 70/15/15 split with
# random_state=42, train-only median for bottom_hint, the same XGBoost parameters, the same label
# rules and the same validation threshold search. Test data is used once per variant.

# %% [1] Configuration and data
import gc

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ASSIST_PATH = (
    "/kaggle/input/datasets/rasangabawanthi/mindbridge-assistments-2012-2013/"
    "2012-2013-data-with-predictions-4-final.csv"
)
RANDOM_STATE = 42

columns = [
    "user_id", "start_time", "correct", "bottom_hint", "hint_count", "attempt_count",
    "ms_first_response", "overlap_time", "first_action", "position", "original",
    "Average_confidence(CONFUSED)", "Average_confidence(BORED)",
]
df = pd.read_csv(ASSIST_PATH, usecols=columns)
df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
df["bottom_hint_missing"] = df["bottom_hint"].isna().astype(int)
df["confused_label"] = (df["Average_confidence(CONFUSED)"] >= 0.5).astype(int)
df["disengaged_label"] = (df["Average_confidence(BORED)"] >= 0.5).astype(int)
print("Rows:", len(df), "| learners:", df["user_id"].nunique())

# %% [2] What does first_action mean in the data? (official text: "attempt or ask for a hint")
print(df["first_action"].value_counts(dropna=False).sort_index())
summary = df.groupby("first_action").agg(
    rows=("first_action", "size"),
    share_with_any_hint=("hint_count", lambda s: float((s > 0).mean())),
    mean_hints=("hint_count", "mean"),
    mean_attempts=("attempt_count", "mean"),
    share_correct=("correct", "mean"),
    share_original=("original", "mean"),
)
print(summary)
# Reading the table: the code whose rows almost always have hint_count > 0 is "asked for a hint";
# the code whose rows mostly have no hints is "attempt". Any third code needs its own explanation
# (for example scaffolding). Record the result before deciding whether to keep first_action.

# %% [3] Learner-wise split (identical to both training notebooks)
users = df["user_id"].drop_duplicates().to_numpy()
train_users, temp_users = train_test_split(users, test_size=0.30, random_state=RANDOM_STATE)
val_users, test_users = train_test_split(temp_users, test_size=0.50, random_state=RANDOM_STATE)
print("Learners:", len(train_users), len(val_users), len(test_users), "(expected 32671 7001 7002)")


def evaluate(y_true, probability, threshold):
    predicted = (probability >= threshold).astype(int)
    _, fp, fn, _ = confusion_matrix(y_true, predicted).ravel()
    return {
        "roc_auc": round(roc_auc_score(y_true, probability), 4),
        "pr_auc": round(average_precision_score(y_true, probability), 4),
        "macro_f1": round(f1_score(y_true, predicted, average="macro"), 4),
        "precision": round(precision_score(y_true, predicted, zero_division=0), 4),
        "recall": round(recall_score(y_true, predicted, zero_division=0), 4),
        "false_positives": int(fp),
        "false_negatives": int(fn),
    }


def best_threshold(y_true, probability, thresholds):
    scores = [
        (round(float(t), 2), f1_score(y_true, (probability >= t).astype(int), average="macro"))
        for t in thresholds
    ]
    return max(scores, key=lambda item: item[1])


# %% [4] Confusion behaviour model (mindbridge-behaviour-model-01, final model)
CONFUSION_FEATURES = [
    "correct", "bottom_hint", "hint_count", "attempt_count", "ms_first_response",
    "overlap_time", "first_action", "position", "original", "bottom_hint_missing",
]
CONFUSION_VARIANTS = {
    "all_features (must reproduce: test ROC-AUC 0.7604, threshold 0.79)": CONFUSION_FEATURES,
    "without_position": [f for f in CONFUSION_FEATURES if f != "position"],
    "without_position_and_first_action": [
        f for f in CONFUSION_FEATURES if f not in {"position", "first_action"}
    ],
}

masks = {
    "train": df["user_id"].isin(train_users),
    "val": df["user_id"].isin(val_users),
    "test": df["user_id"].isin(test_users),
}
median = df.loc[masks["train"], "bottom_hint"].median()
confusion_results = {}
confusion_models = {}

for name, features in CONFUSION_VARIANTS.items():
    split = {}
    for part, mask in masks.items():
        X = df.loc[mask, features].copy()
        X["bottom_hint"] = X["bottom_hint"].fillna(median)
        split[part] = (X, df.loc[mask, "confused_label"])
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = split["train"], split["val"], split["test"]

    model = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        objective="binary:logistic", eval_metric="aucpr", tree_method="hist",
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    threshold, val_macro_f1 = best_threshold(
        y_val, model.predict_proba(X_val)[:, 1], np.arange(0.50, 0.91, 0.01)
    )
    test = evaluate(y_test, model.predict_proba(X_test)[:, 1], threshold)
    confusion_results[name] = {"threshold": threshold, "val_macro_f1": round(val_macro_f1, 4), **test}
    confusion_models[name] = (model, features, threshold)
    print(name, confusion_results[name])
    del split, X_train, X_val, X_test
    gc.collect()

print(pd.DataFrame(confusion_results).T)

# %% [5] Disengagement behaviour model v2 features (mindbridge-disengagement-model-01)
d = df.copy()
d["original_row_id"] = np.arange(len(d))
d = d.sort_values(["user_id", "start_time", "original_row_id"], kind="mergesort").reset_index(
    drop=True
)
valid_rt = d["ms_first_response"].astype(float).mask(d["ms_first_response"] < 0, np.nan)
d["log_response_time"] = np.log1p(valid_rt)
d["previous_interactions"] = d.groupby("user_id", sort=False).cumcount()


def previous_rolling_mean(column):
    return d.groupby("user_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window=20, min_periods=5).mean()
    )


d["recent_log_rt"] = previous_rolling_mean("log_response_time")
d["recent_accuracy"] = previous_rolling_mean("correct")
d["recent_attempts"] = previous_rolling_mean("attempt_count")
d["recent_hints"] = previous_rolling_mean("hint_count")
d["rt_deviation"] = d["log_response_time"] - d["recent_log_rt"]
d["attempt_deviation"] = d["attempt_count"] - d["recent_attempts"]
d["hint_deviation"] = d["hint_count"] - d["recent_hints"]
d["accuracy_deviation"] = d["correct"] - d["recent_accuracy"]
d["history_confidence"] = np.clip(d["previous_interactions"] / 20.0, 0, 1).astype(np.float32)
d["baseline_available"] = (d["previous_interactions"] >= 5).astype(np.uint8)
print("Temporal features ready")

# %% [6] Disengagement behaviour model v2 ablation
DISENGAGEMENT_FEATURES = CONFUSION_FEATURES + [
    "recent_log_rt", "recent_accuracy", "recent_attempts", "recent_hints", "rt_deviation",
    "attempt_deviation", "hint_deviation", "accuracy_deviation", "history_confidence",
    "baseline_available",
]
DISENGAGEMENT_VARIANTS = {
    "all_features (must reproduce: test ROC-AUC 0.5362, threshold 0.53)": DISENGAGEMENT_FEATURES,
    "without_position": [f for f in DISENGAGEMENT_FEATURES if f != "position"],
    "without_position_and_first_action": [
        f for f in DISENGAGEMENT_FEATURES if f not in {"position", "first_action"}
    ],
}

d_masks = {
    "train": d["user_id"].isin(train_users),
    "val": d["user_id"].isin(val_users),
    "test": d["user_id"].isin(test_users),
}
d_median = d.loc[d_masks["train"], "bottom_hint"].median()
disengagement_results = {}
disengagement_models = {}

for name, features in DISENGAGEMENT_VARIANTS.items():
    split = {}
    for part, mask in d_masks.items():
        X = d.loc[mask, features].copy()
        X["bottom_hint"] = X["bottom_hint"].fillna(d_median)
        split[part] = (X.astype(np.float32), d.loc[mask, "disengaged_label"].astype(np.uint8))
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = split["train"], split["val"], split["test"]

    model = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, min_child_weight=3,
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        objective="binary:logistic", eval_metric="logloss", tree_method="hist",
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    model.fit(X_train, y_train)

    threshold, val_macro_f1 = best_threshold(
        y_val, model.predict_proba(X_val)[:, 1], np.arange(0.05, 0.96, 0.01)
    )
    test = evaluate(y_test, model.predict_proba(X_test)[:, 1], threshold)
    disengagement_results[name] = {
        "threshold": threshold, "val_macro_f1": round(val_macro_f1, 4), **test
    }
    disengagement_models[name] = (model, features, threshold)
    print(name, disengagement_results[name])
    del split, X_train, X_val, X_test
    gc.collect()

print(pd.DataFrame(disengagement_results).T)

# %% [7] Save results and the ablation models (download from /kaggle/working)
import json

with open("/kaggle/working/behaviour_ablation_results.json", "w") as f:
    json.dump(
        {"confusion": confusion_results, "disengagement": disengagement_results}, f, indent=2
    )

for prefix, models in (("confusion", confusion_models), ("disengagement", disengagement_models)):
    for name, (model, features, threshold) in models.items():
        key = name.split(" ")[0]
        model.save_model(f"/kaggle/working/{prefix}_behaviour_{key}.json")
        with open(f"/kaggle/working/{prefix}_behaviour_{key}_info.json", "w") as f:
            json.dump({"features": features, "threshold": threshold}, f, indent=2)

print("Saved results and models to /kaggle/working")
