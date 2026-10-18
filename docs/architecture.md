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
| `knowledge_tracing` | references `learner_id` | separately owned research data; gamification reads mastery only through `MasteryProvider` |
| `learner_state` | references `learner_id` | learner-state inference data |
| `adaptive_tutor` | references `learner_id` | separately owned prototype; not consumed by gamification |
| `gamification` | references `learner_id` | skills, content, attempts, support, models, episodes, outcomes, consent, rewards, and learner-skill summaries; consumes Knowledge Tracing `MasteryProvider` and Learner State `SupportNeedProvider` via application contracts; uses shared `app.curriculum`; publishes learner evidence |

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

The gamification module is the Grade 5 Sinhala-medium mobile learning loop defined in
[the component definition](adaptive-gamified-learning/README.md). It owns game episodes,
scaffolds, misconception beliefs, Independence Gain, and policy updates. It does not own mastery,
learner-state fusion, or tutoring. Shared curriculum passages are read through `app.curriculum`.
Draft records are rejected for child delivery. Development HTTP routes under
`/api/v1/development/learning-flow` exercise one draft skill and a read of the 55-area draft
mission catalog. The 16 mathematics missions carry 65 medium-confidence outcome slots.
Sinhala missions carry 8 high-confidence draft items and 76 held slots. Environmental
Studies missions carry 117 held slots. A held slot stores the traced string and does not
add a child question.
Those reads require `allow_draft` and do not authorize a child release.
The default production loader rejects that package.

The client is a React/Capacitor application, not a website. React owns routing, network state,
the encrypted event queue, accessibility, and semantic scaffold content. One reusable Phaser
half-set scene owns direct manipulation and animation only, communicating through the versioned
`mobile-learning-react-phaser-bridge-v1` command/event boundary. The production entry mounts `MobileLearningApp`;
legacy browser routes and the research inspector are not reachable from the child composition.
Android and iOS projects are reproducibly generated from locked inputs and verified for portrait
orientation. The adapter is
fail-closed unless `VITE_ENABLE_MOBILE_LEARNING_DRAFT=true`; that flag is only for development and test
composition and does not authorize child delivery.

Support withdrawal uses a revision-bound request/acknowledgement. React removes semantic support,
the scene clears cached placements and announcements, and Phaser removes objects and input
handlers before the backend accepts the acknowledgement. Telemetry calls and academic mutations
share a client-side serial executor, and academic mutations are never placed in the telemetry
queue. Browser development persistence uses a non-extractable WebCrypto key stored in IndexedDB,
separate from localStorage ciphertext. Native builds deliberately use an in-memory queue until a
reviewed keystore/keychain provider is integrated.

Dependency direction is API and infrastructure toward application/domain; domain code never
depends on frameworks or another research module. Learner State evidence is consumed through a
versioned port. The shared learner UUID is the only foreign product-table reference.

## Intentional omissions

- expert-labelled calibration and release approval for adaptive gamified learning models
- final curriculum/RAG, game-content, experiment, reward, and governance persistence
- authentication implementation (only its shared boundary exists)
- background workers, queues, caches, microservices, and orchestration infrastructure
- signed/release Android and iOS builds and production distribution configuration

These should be added only when a concrete research use case requires them.
