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
| `knowledge_tracing` | references `learner_id` | skills, questions, attempts, and mastery data |
| `learner_state` | references `learner_id` | learner-state inference data |
| `adaptive_tutor` | references `learner_id` | scaffolding/tutoring contracts and policy |
| `gamification` | references `learner_id` | adaptive episodes, decisions, outcomes, and rewards |

The shared learner and knowledge-tracing tables exist now. A module must own its tables and
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
contracts, and deterministic in-memory test adapters. Persistence, learned models, RAG, and HTTP
routes remain deferred. See the
[versioned component architecture](adaptive-gamified-learning/architecture-v1.md).

Dependency direction is API and infrastructure toward application/domain; domain code never
depends on frameworks or another research module. Cross-module evidence is consumed through
versioned ports, not ORM imports or private-table access.

## Intentional omissions

- the three adaptive gamified learning research-model pipelines
- adaptive gamified learning persistence models
- authentication implementation (only its shared boundary exists)
- background workers, queues, caches, microservices, and orchestration infrastructure
- generated Android and iOS projects

These should be added only when a concrete research use case requires them.
