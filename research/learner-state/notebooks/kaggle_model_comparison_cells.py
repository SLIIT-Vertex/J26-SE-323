# Learner-state models: model comparison and feature importance (run on Kaggle)
#
# Copy each "# %%" cell into a Kaggle notebook that has the datasets of the original training
# notebooks attached (mindbridge-assistments-2012-2013, mindbridge-daisee and
# mindbridge-fusion-artifacts). Run the cells in order. Results are written to /kaggle/working.
#
# Purpose
# - Justify the model choice: compare the deployed XGBoost models with Logistic Regression, a
#   Random Forest and (if installed) LightGBM on exactly the same data, features and splits.
# - Identify which features drive each deployed model (XGBoost gain and mean |contribution|).
#
# Fixed so the comparison is fair and reproducible:
# - Data, label rules, features and learner-wise splits are those of the deployed models
#   (mindbridge-behaviour-model-01, mindbridge-disengagement-model-01, mindbridge-visual-model-01,
#   kaggle_behaviour_ablation_cells.py "without_position_and_first_action").
# - XGBoost uses the deployed settings, so its test ROC-AUC must reproduce the published values.
# - The other models use common, untuned settings with class weighting; none of the models is
#   tuned on the test set. Missing values are median-imputed (with missing-value indicators) for
#   Logistic Regression and the Random Forest; XGBoost and LightGBM handle them natively.
# - ROC-AUC and PR-AUC are threshold-free and are the main comparison. Macro-F1 uses a threshold
#   chosen on validation by the same search (0.01-0.99) for every model.
# - The test split is used once per model.

# %% [1] Configuration and shared helpers
import gc
import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMClassifier
except ImportError:
    LGBMClassifier = None

RANDOM_STATE = 42
ASSIST_PATH = (
    "/kaggle/input/datasets/rasangabawanthi/mindbridge-assistments-2012-2013/"
    "2012-2013-data-with-predictions-4-final.csv"
)
DAISEE_LABELS = "/kaggle/input/datasets/rasangabawanthi/mindbridge-daisee/DAiSEE/Labels"
VISUAL_FEATURES = "/kaggle/input/datasets/rasangabawanthi/mindbridge-fusion-artifacts"
THRESHOLDS = np.arange(0.01, 1.00, 0.01)

# Published test ROC-AUC of the deployed models (docs/learner-state/07_EVALUATION_AND_LIMITATIONS.md)
PUBLISHED_ROC_AUC = {
    "confusion_behaviour": 0.7601,
    "disengagement_behaviour": 0.5337,
    "confusion_visual": 0.576,
    "disengagement_visual": 0.687,
}


def best_threshold(y_true, probability):
    scores = [
        (round(float(t), 2), f1_score(y_true, (probability >= t).astype(int), average="macro"))
        for t in THRESHOLDS
    ]
    return max(scores, key=lambda item: item[1])


def scores(y_val, val_probability, y_test, test_probability):
    threshold, val_macro_f1 = best_threshold(y_val, val_probability)
    test_pred = (test_probability >= threshold).astype(int)
    return {
        "test_roc_auc": round(float(roc_auc_score(y_test, test_probability)), 4),
        "test_pr_auc": round(float(average_precision_score(y_test, test_probability)), 4),
        "test_positive_rate": round(float(np.mean(y_test)), 4),
        "threshold": threshold,
        "val_macro_f1": round(float(val_macro_f1), 4),
        "test_macro_f1": round(float(f1_score(y_test, test_pred, average="macro")), 4),
    }


def class_weight(y):
    return float((y == 0).sum() / (y == 1).sum())


def candidates(deployed_xgboost, positive_weight, large):
    """The deployed XGBoost and the comparison models, all with class weighting."""
    models = {
        "xgboost_deployed": deployed_xgboost,
        "logistic_regression": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000),
        ),
        # Bounded so it fits Kaggle memory and time on 4.3 million rows.
        "random_forest": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True),
            RandomForestClassifier(
                n_estimators=200 if not large else 100,
                max_depth=None if not large else 14,
                min_samples_leaf=5 if not large else 50,
                max_samples=None if not large else 0.2,
                class_weight="balanced_subsample",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        ),
    }
    if LGBMClassifier is not None:
        models["lightgbm"] = LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=31, subsample=0.8,
            subsample_freq=1, colsample_bytree=0.8, scale_pos_weight=positive_weight,
            random_state=RANDOM_STATE, n_jobs=-1, verbose=-1,
        )
    return models


def importance(model, X_sample):
    """XGBoost gain (normalised) and mean |contribution| per feature on a test sample."""
    booster = model.get_booster()
    gain = booster.get_score(importance_type="gain")
    total = sum(gain.values()) or 1.0
    contributions = booster.predict(xgb.DMatrix(X_sample), pred_contribs=True)[:, :-1]
    mean_abs = np.abs(contributions).mean(axis=0)
    rows = [
        {
            "feature": name,
            "gain_share": round(gain.get(name, 0.0) / total, 4),
            "mean_abs_contribution": round(float(value), 4),
        }
        for name, value in zip(X_sample.columns, mean_abs, strict=True)
    ]
    return sorted(rows, key=lambda row: row["mean_abs_contribution"], reverse=True)


def compare(task, models, split):
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = split
    results = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        results[name] = scores(
            y_val, model.predict_proba(X_val)[:, 1], y_test, model.predict_proba(X_test)[:, 1]
        )
        print(task, name, results[name])
    reproduced = results["xgboost_deployed"]["test_roc_auc"]
    print(f"{task}: deployed XGBoost test ROC-AUC {reproduced} "
          f"(published {PUBLISHED_ROC_AUC[task]})")
    return results


comparison = {}
feature_importance = {}

# %% [2] Behaviour data and learner-wise split (identical to the training notebooks)
columns = [
    "user_id", "start_time", "correct", "bottom_hint", "hint_count", "attempt_count",
    "ms_first_response", "overlap_time", "original",
    "Average_confidence(CONFUSED)", "Average_confidence(BORED)",
]
df = pd.read_csv(ASSIST_PATH, usecols=columns)
df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
df["bottom_hint_missing"] = df["bottom_hint"].isna().astype(int)
df["confused_label"] = (df["Average_confidence(CONFUSED)"] >= 0.5).astype(int)
df["disengaged_label"] = (df["Average_confidence(BORED)"] >= 0.5).astype(int)

users = df["user_id"].drop_duplicates().to_numpy()
train_users, temp_users = train_test_split(users, test_size=0.30, random_state=RANDOM_STATE)
val_users, test_users = train_test_split(temp_users, test_size=0.50, random_state=RANDOM_STATE)
print("Learners:", len(train_users), len(val_users), len(test_users), "(expected 32671 7001 7002)")

CONFUSION_BEHAVIOUR = [
    "correct", "bottom_hint", "hint_count", "attempt_count", "ms_first_response",
    "overlap_time", "original", "bottom_hint_missing",
]


def behaviour_split(frame, features, label):
    masks = [frame["user_id"].isin(part) for part in (train_users, val_users, test_users)]
    median = frame.loc[masks[0], "bottom_hint"].median()
    parts = []
    for mask in masks:
        X = frame.loc[mask, features].copy()
        X["bottom_hint"] = X["bottom_hint"].fillna(median)
        parts.append((X.astype(np.float32), frame.loc[mask, label].astype(np.uint8)))
    return parts


# %% [3] Confusion behaviour: comparison and feature importance
split = behaviour_split(df, CONFUSION_BEHAVIOUR, "confused_label")
weight = class_weight(split[0][1])
deployed = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
    scale_pos_weight=weight, objective="binary:logistic", eval_metric="aucpr",
    tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
)
comparison["confusion_behaviour"] = compare(
    "confusion_behaviour", candidates(deployed, weight, large=True), split
)
feature_importance["confusion_behaviour"] = importance(
    deployed, split[2][0].sample(20_000, random_state=RANDOM_STATE)
)
print(pd.DataFrame(feature_importance["confusion_behaviour"]))
del split
gc.collect()

# %% [4] Disengagement behaviour features (identical to the ablation script)
d = df.copy()
d["original_row_id"] = np.arange(len(d))
d = d.sort_values(["user_id", "start_time", "original_row_id"], kind="mergesort").reset_index(
    drop=True
)
valid_rt = d["ms_first_response"].astype(float).mask(d["ms_first_response"] < 0, np.nan)
d["log_response_time"] = np.log1p(valid_rt)
d["previous_interactions"] = d.groupby("user_id", sort=False).cumcount()


def previous_rolling_mean(frame, column):
    return frame.groupby("user_id", sort=False)[column].transform(
        lambda s: s.shift(1).rolling(window=20, min_periods=5).mean()
    )


d["recent_log_rt"] = previous_rolling_mean(d, "log_response_time")
d["recent_accuracy"] = previous_rolling_mean(d, "correct")
d["recent_attempts"] = previous_rolling_mean(d, "attempt_count")
d["recent_hints"] = previous_rolling_mean(d, "hint_count")
d["rt_deviation"] = d["log_response_time"] - d["recent_log_rt"]
d["attempt_deviation"] = d["attempt_count"] - d["recent_attempts"]
d["hint_deviation"] = d["hint_count"] - d["recent_hints"]
d["accuracy_deviation"] = d["correct"] - d["recent_accuracy"]
d["history_confidence"] = np.clip(d["previous_interactions"] / 20.0, 0, 1).astype(np.float32)
d["baseline_available"] = (d["previous_interactions"] >= 5).astype(np.uint8)

DISENGAGEMENT_BEHAVIOUR = CONFUSION_BEHAVIOUR + [
    "recent_log_rt", "recent_accuracy", "recent_attempts", "recent_hints", "rt_deviation",
    "attempt_deviation", "hint_deviation", "accuracy_deviation", "history_confidence",
    "baseline_available",
]

# %% [5] Disengagement behaviour: comparison and feature importance
split = behaviour_split(d, DISENGAGEMENT_BEHAVIOUR, "disengaged_label")
weight = class_weight(split[0][1])
deployed = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
    min_child_weight=3, scale_pos_weight=weight, objective="binary:logistic",
    eval_metric="logloss", tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
)
comparison["disengagement_behaviour"] = compare(
    "disengagement_behaviour", candidates(deployed, weight, large=True), split
)
feature_importance["disengagement_behaviour"] = importance(
    deployed, split[2][0].sample(20_000, random_state=RANDOM_STATE)
)
print(pd.DataFrame(feature_importance["disengagement_behaviour"]))
del split, d
gc.collect()

# %% [6] Visual data: DAiSEE features (extracted by mindbridge-visual-model-01) and labels
VISUAL = [
    "mean_eye_openness", "std_eye_openness", "mean_gaze_ratio", "std_gaze_ratio",
    "mean_pitch", "mean_yaw", "mean_roll", "mean_abs_pitch", "mean_abs_yaw", "mean_abs_roll",
    "face_visibility_ratio",
]
FEATURE_FILES = {
    "train": "daisee_train_visual_features_rollfix.csv",
    "validation": "daisee_validation_visual_features.csv",
    "test": "daisee_test_visual_features.csv",
}
LABEL_FILES = {
    "train": "TrainLabels.csv",
    "validation": "ValidationLabels.csv",
    "test": "TestLabels.csv",
}


def visual_part(part):
    features = pd.read_csv(f"{VISUAL_FEATURES}/{FEATURE_FILES[part]}")[["ClipID", *VISUAL]]
    labels = pd.read_csv(f"{DAISEE_LABELS}/{LABEL_FILES[part]}")
    labels.columns = labels.columns.str.strip()
    frame = features.merge(labels[["ClipID", "Confusion", "Engagement"]], on="ClipID")
    frame["confused_label"] = (frame["Confusion"] >= 1).astype(int)
    frame["disengaged_label"] = (frame["Engagement"] <= 1).astype(int)
    return frame


visual = {part: visual_part(part) for part in FEATURE_FILES}
print({part: len(frame) for part, frame in visual.items()}, "(expected 5358 1429 1784)")


def visual_split(label):
    return [
        (visual[part][VISUAL], visual[part][label]) for part in ("train", "validation", "test")
    ]


# %% [7] Visual confusion and disengagement: comparison and feature importance
for task, label, metric in (
    ("confusion_visual", "confused_label", "aucpr"),
    ("disengagement_visual", "disengaged_label", "logloss"),
):
    split = visual_split(label)
    weight = class_weight(split[0][1])
    deployed = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
        min_child_weight=3, scale_pos_weight=weight, objective="binary:logistic",
        eval_metric=metric, tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
    )
    comparison[task] = compare(task, candidates(deployed, weight, large=False), split)
    feature_importance[task] = importance(deployed, split[2][0])
    print(pd.DataFrame(feature_importance[task]))

# %% [8] Summary and save (download both JSON files from /kaggle/working)
summary = pd.DataFrame(
    {
        (task, model): {"ROC-AUC": r["test_roc_auc"], "PR-AUC": r["test_pr_auc"],
                        "macro-F1": r["test_macro_f1"]}
        for task, results in comparison.items()
        for model, r in results.items()
    }
).T
print(summary)

with open("/kaggle/working/model_comparison_results.json", "w") as f:
    json.dump(
        {
            "settings": {
                "random_state": RANDOM_STATE,
                "threshold_search": "0.01-0.99 on validation, best macro-F1",
                "lightgbm_available": LGBMClassifier is not None,
                "versions": {
                    "xgboost": xgb.__version__,
                    "scikit-learn": __import__("sklearn").__version__,
                },
            },
            "published_deployed_roc_auc": PUBLISHED_ROC_AUC,
            "results": comparison,
        },
        f,
        indent=2,
    )
with open("/kaggle/working/feature_importance_results.json", "w") as f:
    json.dump(feature_importance, f, indent=2)
print("Saved model_comparison_results.json and feature_importance_results.json")
