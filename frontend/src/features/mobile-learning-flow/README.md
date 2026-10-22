# Mobile learning flow (the child app shell)

`App.tsx` mounts only `MobileLearningApp`. This folder is that app: navigation, the home and
subject screens, the help (support) UI shared by every game, and the typed API client. The games
themselves are in [`../areas/`](../areas/README.md).

```text
mobile-learning-flow/
  MobileLearningApp.tsx      app state + screen switch (which screen, learner, camera consent, sync)
  learningAreas.ts           display titles for every Grade 5 area (MAT, SIN, ENV, ENG)
  shell/                     presentational screens used by the shell
    Onboarding.tsx           splash, onboarding slides, language + profile setup
    HomeScreen.tsx           home dashboard and featured games
    GamesHome.tsx            subject pages and the list of playable areas
    DraftTemplatePlayer.tsx  researcher-only draft mission player
    ProgressScreen.tsx, RewardsHub.tsx, Account.tsx, Settings.tsx (+ Failure)
    BottomNavigation.tsx     tab bar and its icons
    common.tsx               Back button, BrandMark, LearnerAvatar, AppIcon
  SupportRoundFrame.tsx      the frame every help round is shown in
  AdaptiveSupportActivity.tsx  the help activities (visual, worked example, step by step, …)
  useSupportRound.ts         hook that drives one help round against the backend
  AdventureShared.tsx, AdventureProgress.tsx   back button, success screen, 4-stage progress bar
  FixtureRoundPlayer.tsx     fixture rounds for areas that have no dedicated game yet
  GameApi.ts                 the slice of the API client a game may call
  phaser-board/, word-drop/  shared Phaser boards used by several English and maths games
  api/
    generated.ts             TypeScript generated from docs/adaptive-gamified-learning/mobile-learning-contracts-v1.json
                             (npm run generate:mobile-learning-types; never edit by hand)
    learningFlowClient.ts    HTTP client for /learning-flow routes
    fixtureRoundClient.ts    HTTP client for fixture rounds
    runtime.ts               runtime validation of server responses
  *.css                      shell-wide styles (navigation-refresh.css and game-play-surface.css are imported by main.tsx)
```

## How a game is opened

1. `GamesHome` lists the areas of a subject; the child taps one.
2. `MobileLearningApp.chooseMission(areaId)` looks the area up in `../areas/registry.ts` and sets
   that game's screen.
3. The registry's lazy component is rendered with `AreaGameProps`.
4. Areas without a game fall back to `FixtureRoundPlayer` or `DraftTemplatePlayer`.

The backend side of one episode is described in
`backend/app/gamification/README.md`.
