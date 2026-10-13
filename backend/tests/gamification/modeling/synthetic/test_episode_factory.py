from app.gamification.modeling.synthetic import generate_synthetic_episodes


def test_synthetic_generator_is_seeded_and_covers_required_cases() -> None:
    first = generate_synthetic_episodes(seed=5)
    assert first == generate_synthetic_episodes(seed=5)
    assert all(episode.synthetic for episode in first)
    assert any(not episode.learner_state_available for episode in first)
    assert any(not episode.verification_valid for episode in first)
    assert any(episode.evidence_count == 0 for episode in first)
