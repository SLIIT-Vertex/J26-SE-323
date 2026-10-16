# Learner State — training notebooks

Kaggle notebooks that trained the four XGBoost models used by `backend/app/learner_state/`.
They are kept with their saved outputs so that every reported number can be traced back to them.
They are reference material only and are not run by the backend.

| Notebook | Produces | Data |
| --- | --- | --- |
| `notebooks/mindbridge-visual-model-01.ipynb` | `mindbridge_visual_model.json` (confusion, visual) and the visual feature extraction (MediaPipe Face Landmarker) | DAiSEE |
| `notebooks/mindbridge-behaviour-model-01.ipynb` | the original confusion behaviour model (since replaced, see below) and learner-baseline ablations | ASSISTments 2012–13 with affect predictions |
| `notebooks/mindbridge-disengagement-model-01.ipynb` | `mindbridge_disengagement_visual_model.json`, the original disengagement behaviour model (since replaced), reliability constants | DAiSEE, ASSISTments 2012–13 |
| `notebooks/kaggle_behaviour_ablation_cells.py` | `mindbridge_behavior_model_v2.json` and `mindbridge_disengagement_behavior_model_v3.json`: the behaviour models retrained without `position` and `first_action`; results in `behaviour_ablation_results.json` and the `*_info.json` files | ASSISTments 2012–13 with affect predictions |
| `notebooks/mindbridge-fusion-model-01.ipynb` | Prototype of reliability, fusion and temporal logic on **synthetic** example windows; synchronized pilot-data template | Model outputs only; no cross-dataset pairing |

The results are summarised in
[`docs/learner-state/07_EVALUATION_AND_LIMITATIONS.md`](../../docs/learner-state/07_EVALUATION_AND_LIMITATIONS.md).

## Data and privacy

- The datasets are **not** stored in this repository. The notebooks read them from Kaggle inputs
  (`/kaggle/input/...`); use of DAiSEE and ASSISTments follows their own licences.
- DAiSEE and ASSISTments come from different learners and are never paired into multimodal samples.
- Image outputs showing DAiSEE video frames were removed from the visual notebook before it was
  added here. Do not add outputs that show participants' faces.
