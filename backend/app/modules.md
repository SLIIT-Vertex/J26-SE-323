# Research module boundaries

Each research module owns its domain, application use cases, persistence adapters, and API.
Modules may depend on shared contracts, including the learner UUID, but must not import another
research module's infrastructure or persistence model.

- `knowledge_tracing`: separately owned skills/questions/attempts module; no gamification dependency
- `learner_state`: learner-state inference data keyed by `learner_id`
- `adaptive_tutor`: separately owned tutoring prototype; no gamification dependency
- `gamification`: owns its skills, content, attempts, mastery, support, models, episodes, outcomes,
  consent, rewards, and datasets; shares only Learner Profile and Learner State

Existing module prototypes remain independently owned and are not validated research findings
merely because executable code exists.
