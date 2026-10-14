# Pilot vertical slice

Adult testers can play one adaptive episode on the Grade 5 fractions slice. The server owns session creation, baseline scoring, struggle assessment, belief inference, support selection, withdrawal, and verification. The shell only renders what the server returns and reports interaction events.

Child-facing delivery stays blocked. The package is still draft, and `allow_draft` is limited to this tester path.

## Run it locally

From `backend/`, with the project virtualenv:

```bash
DATABASE_URL=sqlite:////tmp/mindbridge-pilot.db python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From `frontend/`:

```bash
npm install
npm run dev
```

Open `http://localhost:5173/#/play`. The API base is `VITE_API_URL`, defaulting to `http://127.0.0.1:8000/api/v1`, which matches Uvicorn's IPv4 bind. CORS allows `http://localhost:5173`.

PostgreSQL is not required for this path. The play store is process memory. Restarting the API drops sessions and episodes. Other routers still read `DATABASE_URL` for their own tables.

## What the tester does

1. Choose `performance_triggered_fixed` or `shadow` and start an episode.
2. Answer the baseline item. A wrong misconception-linked option asks the server for support.
3. Read the support, then continue. The shell calls support complete and then withdraw. The overlay unmounts before the verification item appears in the same template.
4. Answer the verification item. The finish message shows the episode id.
5. Open `#/inspector` with the researcher development role. It shows beliefs, candidate propensities and predicted rewards, the delivered scaffold id, both scores, Independence Gain, and validity.

`#/build` previews the fraction-bar template. Pilot items in this slice are single-select, so the episode itself uses the React `choice_quest` template.

## Modes

| Header `X-Decision-Mode` | What the server does |
| --- | --- |
| `performance_triggered_fixed` | Delivers the authored reference scaffold. A LinUCB view is logged and is not used for delivery. |
| `shadow` | Same delivery. The bandit prediction and propensities are kept on the decision. |
| `learned` | Refused with `MODEL_NOT_READY` until an approved artifact exists. |

## What is stubbed

- Authentication is the development header `X-Dev-Principal: NOT_FOR_PRODUCTION`, plus `X-Dev-Role` and `X-Learner-Id`. This is not an identity provider. UD-007 stays open.
- Sessions, idempotency, and telemetry sequence numbers live in the API process.
- The misconception predictor uses the existing engineering priors from the episode tests. Those priors are not an accuracy claim.
- Mastery and learner-state gateways are not attached, so a tester can finish without those services.
- Learner-evidence publishing and the research-consent gate are not on this path. Reconstruction is role-gated instead.
- Support duration and step limits are client hints. The server decides withdrawal.
- `sort_and_group` is deferred.

## Dependencies

Phaser `3.88.2` is pinned because the fraction-bar scene is the only canvas template. `choice_quest` stays in React DOM. The pin reason is also in `frontend/src/features/gamification/phaser/createGame.ts`, because `package.json` cannot carry a comment.

Regenerate the shell types after an API change:

```bash
cd frontend && npm run generate:api
```

The checked-in contract is `openapi-pilot-v1.json`. `backend/tests/gamification/test_openapi_pilot.py` regenerates the gamification router schema and diffs it.
