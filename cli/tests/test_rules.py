from rl.rules import find_terms, load_terms


def test_negated_term_is_ignored() -> None:
    assert find_terms("gentle rain, no sudden sounds", ("sudden",)) == []
    assert find_terms("soft fire without any loud pops", ("loud",)) == []


def test_plain_term_is_found() -> None:
    assert find_terms("sudden thunder in the distance", ("sudden",)) == ["sudden"]


def test_negation_window_is_limited() -> None:
    # "no" is more than three tokens before "loud", so it does not negate it.
    assert find_terms("no wind at all tonight but loud rain", ("loud",)) == ["loud"]


def test_multi_word_terms() -> None:
    assert find_terms("ocean with breaking waves", ("breaking waves",)) == ["breaking waves"]
    assert find_terms("calm sea, no breaking waves", ("breaking waves",)) == []


def test_rule_lists_load_without_comments() -> None:
    terms = load_terms("hard-block")
    assert "explosion" in terms
    assert all(not t.startswith("#") for t in terms)
