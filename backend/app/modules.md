# Research module boundaries

Each research module owns its domain, application use cases, persistence adapters, and API.
Modules may depend on shared contracts, including the learner UUID, but must not import another
research module's infrastructure or persistence model.

- `knowledge_tracing`: future mastery data keyed by `learner_id`
- `learner_state`: future learner-state data keyed by `learner_id`
- `adaptive_tutor`: future tutoring/scaffolding data keyed by `learner_id`
- `gamification`: future points/reward data keyed by `learner_id`

No algorithms or research-specific tables exist in this foundation.
