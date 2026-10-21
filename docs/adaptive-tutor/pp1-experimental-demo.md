# PP1 local experimental Tutor demo

Status: local adult research only. Generated text is unverified and never enters the verified
response field. The unreviewed Fractions template is read directly; it is not imported into the
approved curriculum index.

## Configuration

Set these server-side values in `backend/.env` (use your own secrets and existing learner data):

```dotenv
DATABASE_URL=postgresql+psycopg://...
TUTOR_API_MODE=research-local
TUTOR_RESEARCH_COMPOSITION_ENABLED=true
TUTOR_PP1_EXPERIMENTAL_DEMO_ENABLED=true
TUTOR_RESEARCH_ACCESS_KEY=<local-secret>
TUTOR_RESEARCHER_ID=<researcher-uuid>
TUTOR_RESEARCH_GEMINI_AUTHORIZED=true
TUTOR_RESEARCH_SEVERITY_POLICY_VERSIONS=<controlled-policy-version>
TUTOR_LLM_PROVIDER=gemini
TUTOR_GEMINI_API_KEY=<server-side-secret>
TUTOR_GEMINI_MODEL=<pinned-model>
```

Set `VITE_TUTOR_RESEARCH_KEY=<same-local-secret>` in `frontend/.env`. Never put the Gemini key in
frontend configuration. This mode supports the English unreviewed content only.

## Run in the browser

The interpreter that runs uvicorn must have the `gemini` extra installed. Without it the result
reports `experimental_provider_reason_code: PROVIDER_SDK_NOT_INSTALLED`. To check connectivity with
one fixed, non-sensitive live request:

```bash
cd backend
.venv313/bin/pip install -e '.[gemini]'
GEMINI_CONNECTIVITY_CHECK_ENABLED=true .venv313/bin/python -m scripts.check_gemini_connectivity
```

```bash
docker compose up -d db
cd backend
.venv313/bin/alembic upgrade heads
.venv313/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open Research Interaction, enter an existing learner UUID and a Fractions question, then start the
session. The UI shows its trusted session UUID before asking. Record genuine, fresh `MAT-FRC`
Learner State evidence through the existing `/api/v1/learner-state` capture path using that exact
session UUID. Submit the unchanged question again. Mapper abstention, missing KT mastery, or missing
Learner State remains blocked.

## Readiness and opt-in smoke

After the smoke runner prints its session UUID and pauses, record genuine same-session Learner State
evidence and run:

```bash
cd backend
AT24_SESSION_ID=<printed-uuid> .venv313/bin/python scripts/check_adaptive_tutor_readiness.py \
  --learner-id <learner-uuid> --session-id <printed-uuid> --language en
```

Run the explicitly enabled smoke test (it performs live Gemini calls):

```bash
cd backend
AT24_LIVE_SMOKE_ENABLED=true \
AT24_PAUSE_FOR_LEARNER_STATE=true \
AT24_LEARNER_ID=<learner-uuid> \
AT24_QUESTION='Why is 1/2 equal to 2/4?' \
AT24_LANGUAGE=en \
AT24_ATTEMPT_JSON='{"idempotency_key":"pp1-1","is_correct":false,"partial_credit":null,"severity_category":"RESEARCHER_ANNOTATED_ERROR","severity_value":0.7,"severity_policy_version":"<configured-policy-version>","scoring_version":"researcher-review-v1","item_rubric_version":"researcher-supplied-v1","reviewer_confirmed":true}' \
.venv313/bin/python scripts/smoke_test_live_research_tutor.py
```

Restart the backend after changing environment values because the research composition is cached.
The synthetic demo and verified research mode remain unchanged when the experimental flag is false.
