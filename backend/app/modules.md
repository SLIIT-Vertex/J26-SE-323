# Research module boundaries

Each research module owns its domain, application use cases, persistence adapters, and API.
Modules may depend on shared contracts, including the learner UUID, but must not import another
research module's infrastructure or persistence model.

- `knowledge_tracing`: skills, questions, attempts, and mastery data keyed by `learner_id`
- `learner_state`: learner-state inference data keyed by `learner_id`
- `adaptive_tutor`: tutoring/scaffolding contracts and policy keyed by `learner_id`
- `gamification`: adaptive episodes/contracts now; future game, model, and reward data keyed by `learner_id`

The adaptive gamified learning episode and its three research-model pipelines are not yet
implemented. Existing module prototypes remain independently owned and are not validated research
findings merely because executable code exists.
