from marketedge.matching.selection_matcher import assign_outcome_key


def test_assigns_home_and_away_for_match_odds() -> None:
    assert (
        assign_outcome_key("Arsenal", "MATCH_ODDS", "Soccer", "Arsenal", "Chelsea", "FALLBACK")
        == "HOME"
    )
    assert (
        assign_outcome_key("Chelsea", "MATCH_ODDS", "Soccer", "Arsenal", "Chelsea", "FALLBACK")
        == "AWAY"
    )


def test_assigns_draw_for_betfair_style_runner_name() -> None:
    assert (
        assign_outcome_key("The Draw", "MATCH_ODDS", "Soccer", "Arsenal", "Chelsea", "FALLBACK")
        == "DRAW"
    )


def test_home_away_join_across_differently_formatted_names() -> None:
    # Odds-provider style "Arsenal FC" should still resolve to the same key
    # as Betfair's bare "Arsenal", since both normalize identically.
    assert (
        assign_outcome_key(
            "Arsenal FC", "MATCH_ODDS", "Soccer", "Arsenal FC", "Chelsea FC", "FALLBACK"
        )
        == "HOME"
    )


def test_unrecognised_runner_falls_back() -> None:
    assert (
        assign_outcome_key("Someone Else", "MATCH_ODDS", "Soccer", "Arsenal", "Chelsea", "FALLBACK")
        == "FALLBACK"
    )


def test_totals_over_under() -> None:
    assert assign_outcome_key("Over 2.5", "TOTAL", "Soccer", None, None, "FALLBACK") == "OVER"
    assert assign_outcome_key("Under 2.5", "TOTAL", "Soccer", None, None, "FALLBACK") == "UNDER"


def test_btts_yes_no() -> None:
    assert assign_outcome_key("Yes", "BTTS", "Soccer", None, None, "FALLBACK") == "YES"
    assert assign_outcome_key("No", "BTTS", "Soccer", None, None, "FALLBACK") == "NO"


def test_unknown_market_type_falls_back() -> None:
    assert (
        assign_outcome_key("Arsenal", "SOME_NEW_TYPE", "Soccer", None, None, "FALLBACK")
        == "FALLBACK"
    )
