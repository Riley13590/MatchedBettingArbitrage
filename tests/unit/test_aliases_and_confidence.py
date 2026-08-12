from datetime import UTC, datetime, timedelta

from marketedge.matching.aliases import normalize
from marketedge.matching.confidence import (
    MatchCandidate,
    competition_similarity,
    event_match_score,
    participant_similarity,
    start_time_similarity,
)
from marketedge.matching.event_matcher import MatchDecision, find_best_match


def test_normalize_strips_suffix_and_case() -> None:
    assert normalize("Arsenal FC") == "ARSENAL"
    assert normalize("arsenal") == "ARSENAL"


def test_normalize_strips_accents_and_punctuation() -> None:
    assert normalize("Étoile du Sahel") == "ETOILE_DU_SAHEL"


def _candidate(**overrides: object) -> MatchCandidate:
    base = dict(
        sport="Soccer",
        competition="EPL",
        start_time_utc=datetime(2026, 8, 15, 14, 0, tzinfo=UTC),
        home_participant="Arsenal",
        away_participant="Chelsea",
    )
    base.update(overrides)
    return MatchCandidate(**base)  # type: ignore[arg-type]


def test_participant_similarity_exact_match() -> None:
    assert participant_similarity(_candidate(), _candidate()) == 1.0


def test_participant_similarity_swapped_orientation_still_matches() -> None:
    swapped = _candidate(home_participant="Chelsea", away_participant="Arsenal")
    assert participant_similarity(_candidate(), swapped) == 1.0


def test_participant_similarity_different_teams_scores_zero() -> None:
    other = _candidate(home_participant="Liverpool", away_participant="Everton")
    assert participant_similarity(_candidate(), other) == 0.0


def test_start_time_similarity_decays_with_distance() -> None:
    close = _candidate(start_time_utc=_candidate().start_time_utc + timedelta(minutes=5))
    far = _candidate(start_time_utc=_candidate().start_time_utc + timedelta(hours=5))
    assert start_time_similarity(_candidate(), close) > start_time_similarity(_candidate(), far)


def test_competition_similarity_exact() -> None:
    assert competition_similarity(_candidate(), _candidate()) == 1.0


def test_event_match_score_identical_events_is_high() -> None:
    assert event_match_score(_candidate(), _candidate()) >= 0.98


def test_event_match_score_different_sport_is_zero() -> None:
    other = _candidate(sport="Tennis")
    assert event_match_score(_candidate(), other) == 0.0


def test_find_best_match_auto_matches_identical_candidate() -> None:
    result = find_best_match(_candidate(), [_candidate()])
    assert result.decision == MatchDecision.AUTO_MATCH
    assert result.matched_index == 0


def test_find_best_match_review_band_for_close_but_imperfect_candidate() -> None:
    # Same teams/competition, start time off by 30 minutes -> score lands in
    # the 0.90-0.98 review band rather than auto-matching or rejecting.
    near = _candidate(start_time_utc=_candidate().start_time_utc + timedelta(minutes=30))
    result = find_best_match(_candidate(), [near])
    assert result.decision == MatchDecision.REVIEW
    assert 0.90 <= result.score < 0.98


def test_find_best_match_no_candidates_is_no_match() -> None:
    result = find_best_match(_candidate(), [])
    assert result.decision == MatchDecision.NO_MATCH
    assert result.matched_index is None


def test_find_best_match_unrelated_candidate_is_no_match() -> None:
    unrelated = _candidate(
        home_participant="Liverpool",
        away_participant="Everton",
        start_time_utc=_candidate().start_time_utc + timedelta(hours=5, minutes=59),
        competition="Different Competition Entirely",
    )
    result = find_best_match(_candidate(), [unrelated])
    assert result.decision == MatchDecision.NO_MATCH
