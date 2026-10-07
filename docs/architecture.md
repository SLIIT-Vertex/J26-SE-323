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

| Owner | Shared key | Future owned data |
| --- | --- | --- |
| `shared/learner` | `learner_id` (UUID) | grade and preferred language |
| `knowledge_tracing` | references `learner_id` | mastery data |
| `learner_state` | references `learner_id` | learner-state data |
| `adaptive_tutor` | references `learner_id` | scaffolding/tutoring data |
| `gamification` | references `learner_id` | points/reward data |

Only the shared learner table exists now. A module must own its future tables and migrations; it
must not duplicate the learner profile. Cross-module behavior should use an explicit application
contract or event defined by the owning module, never another module's ORM model or repository.

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

## Intentional omissions

- Knowledge Tracing, Learner State, and Gamification algorithms
- research-specific persistence models
- authentication implementation (only its shared boundary exists)
- background workers, queues, caches, microservices, and orchestration infrastructure
- generated Android and iOS projects

These should be added only when a concrete research use case requires them.
