# Model cards

One card per model the games run: [the Bayesian misconception expert tables](misconception-expert-tables.md)
(Model 1) and the help-order bandit of each subject ([Mathematics](help-order-bandit-MAT.md),
[English](help-order-bandit-ENG.md), [Sinhala](help-order-bandit-SIN.md); Model 2). Model 3,
Independence Gain, is a measurement, not a learned model.

The cards sit next to the expert model data because every model starts from it, but outside the
versioned package `v1/`: that folder holds exactly what the generator builds, while a card also
records an approval, which is state in a database, not data. Each card names the package version
and the artifact hash it describes, so a card that no longer matches the data or the database is
easy to spot.
