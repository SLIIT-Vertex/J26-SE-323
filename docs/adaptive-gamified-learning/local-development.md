# Local development

From the repository root:

```bash
npm run dev
```

That runs `scripts/dev.sh`. It starts the API on port 8000 (with reload) unless one is already
running, then the Grade 5 app. Open the address Vite prints, usually http://localhost:5173/.
The backend needs `backend/.venv` and a running database (see the root `README.md`).

`frontend/.env.development` is loaded only by the development server. It sets the API address and
`VITE_MOBILE_LEARNING_CONDITION=proposed`. There is no flag to turn the draft missions on: the
app always sends the development caller mark (`X-Dev-Principal: NOT_FOR_PRODUCTION`), and the
server serves the draft mission list to the researcher role.

**Games** shows four subjects: Mathematics, Sinhala, Environmental Studies and English. Each area
opens its own game when it has one (see `frontend/src/features/areas/README.md`). Environment
areas play as fixture rounds, and the other areas open the draft template player.

Other tabs: **Practice** opens the papers flow, **Mindy** opens the adaptive tutor demo, and
**Home** and **Progress** show the learner's home dashboard and progress. The research dashboard
button appears in research mode.

Optional switches:

| Variable | Effect |
|---|---|
| `VITE_MOBILE_LEARNING_CONDITION` | `baseline` or `proposed` (engineering builds only, never a child setting) |
| `VITE_MOBILE_LEARNING_ENVIRONMENT` | `development` (default), `test` or `pilot` |
| `VITE_LEARNER_STATE_PROMPTS=off` | hides the learner-state prompts during games |

## Seeding a demo learner

```bash
cd backend
python -m app.gamification.demo_seed plan      # show what would be seeded
python -m app.gamification.demo_seed seed
python -m app.gamification.demo_seed verify
```

All commands: [`tools/README.md`](../../tools/README.md).

## Not a child release

The mission catalogue and every area game are development-only. Publication stays blocked.
Nothing here is approved for children.
