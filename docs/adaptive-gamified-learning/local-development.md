# Local development

From the repository root:

```bash
npm run dev
```

That starts the API on port 8000 and the Grade 5 app. Open the address Vite prints, usually http://localhost:5173/.

Do not set `VITE_ENABLE_MOBILE_LEARNING_DRAFT` and do not `cd frontend`. The development server turns the draft mission list on by itself (`frontend/.env.development`). Games shows Mathematics, Sinhala, and Environmental Studies.

## Not a child release

The mission catalog is development-only. Publication stays blocked. Nothing here is approved for children.

A production web build does not load `.env.development`, so the mission list stays off. The server still refuses the draft package unless the environment is development or test and the caller passes `allow_draft`.

Home, Mindy, and Progress are empty and marked "To be implemented" for other team members. Practice opens the papers flow. Games is the screen this work owns.
