# MindBridge architecture

## System shape

MindBridge is a **modular monolith**: one deployable FastAPI application and one PostgreSQL
database, with strong logical boundaries between research areas. This keeps local development and
operations simple while allowing four researchers to work independently.

Each research module has lightweight Clean Architecture folders:

- `domain`: framework-independent concepts and rules
- `application`: use cases and public contracts
- `infrastructure`: SQLAlchemy and other external adapters
- `api`: FastAPI routing and request/response translation

Folders are placeholders until a real use case exists. The shared learner implementation already
demonstrates the intended dependency direction: the service depends on a repository protocol,
while FastAPI and SQLAlchemy provide adapters at the boundary.

## Data ownership

There is one shared PostgreSQL database, not a database per module. Ownership is logical:

| Owner | Shared key | Current or planned owned data |
| --- | --- | --- |
| `shared/learner` | `learner_id` (UUID) | grade and preferred language |
| `knowledge_tracing` | references `learner_id` | separately owned research data; not consumed by gamification |
| `learner_state` | references `learner_id` | learner-state inference data |
| `adaptive_tutor` | references `learner_id` | separately owned prototype; not consumed by gamification |
| `gamification` | references `learner_id` | skills, content, attempts, mastery, support, models, episodes, outcomes, consent, and rewards |

The shared learner table exists now. A module must own its tables and
migrations; it must not duplicate the learner profile. Cross-module behavior should use an
explicit application contract or event defined by the owning module, never another module's ORM
model or repository.

## Runtime flow

```text
React / Capacitor
       |
       | REST /api/v1
       v
FastAPI routes -> application service -> repository contract
                                           |
                                           v
                                   SQLAlchemy adapter
                                           |
                                           v
                              PostgreSQL + pgvector
```

The initial migration enables PostgreSQL's `vector` extension so future RAG work can add vectors
inside the module that owns them. It does not create embeddings or research-specific tables.

## Adaptive gamified learning boundary

The gamification module defines the framework-independent `adaptive-episode-v1` state machine,
application-owned integration ports, strictly validated `gamification-boundary-v1` transport
contracts, durable model-first evidence persistence, deterministic in-memory test adapters, and
provisional three-model engineering pipelines, and a gamification-owned Grade 5 skill catalogue
whose draft records are rejected by default. Only Learner Profile and Learner State are shared.
Expert validation, approved skills, RAG, and HTTP routes remain deferred. See the
[versioned component architecture](adaptive-gamified-learning/architecture-v1.md) and
[three-model pipeline specification](adaptive-gamified-learning/model-pipelines-v1.md). The model
implementation follows the independently packaged
[three-model code architecture](adaptive-gamified-learning/model-code-architecture-v2.md).
The development-only skill binding is documented in the
[skill catalogue review contract](adaptive-gamified-learning/skill-catalogue-v1.md).

Dependency direction is API and infrastructure toward application/domain; domain code never
depends on frameworks or another research module. Learner State evidence is consumed through a
versioned port. The shared learner UUID is the only foreign product-table reference.

## Intentional omissions

- expert-labelled calibration and release approval for adaptive gamified learning models
- final curriculum/RAG, game-content, experiment, reward, and governance persistence
- authentication implementation (only its shared boundary exists)
- background workers, queues, caches, microservices, and orchestration infrastructure
- generated Android and iOS projects

These should be added only when a concrete research use case requires them.
