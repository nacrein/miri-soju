"""Tests for the bypass-resistant text core: normalization and word matching.

Pure, no Discord. These pin down both halves of "fool-proof": the matcher must
catch dodges (leetspeak, spacing, zero-width, accents, homoglyphs) AND must not
false-positive (short words match on word boundaries, not as substrings).
"""

from __future__ import annotations

from src.modules.automod.normalize import (
    WordMatcher,
    caps_ratio,
    count_emojis,
    normalize_text,
    normalize_token,
    strip_code,
)


def test_normalize_folds_leet_spacing_and_zero_width():
    assert normalize_text("b a d") == "bad"
    assert normalize_text("b.a.d") == "bad"
    assert normalize_text("b​a​d") == "bad"
    assert normalize_text("B4D") == "bad"
    assert normalize_text("baaaad") == "bad"  # repeats collapsed


def test_normalize_folds_accents_fullwidth_and_homoglyphs():
    assert normalize_text("naïve") == "naive"          # ï -> i
    assert normalize_text("ｂａｄ") == "bad"    # full-width ｂａｄ
    assert normalize_text("bаd") == "bad"              # Cyrillic а -> a


def test_normalize_token_is_folded_and_trimmed():
    assert normalize_token("  Bad  ") == "bad"
    assert normalize_token("Sh1t") == "shit"


def test_matcher_catches_long_word_dodges_as_substrings():
    m = WordMatcher(["retard"])  # 6 chars -> substring path
    for dodge in ("retard", "r3t@rd", "r e t a r d", "RETARDED", "retаrd"):
        assert m.matches(dodge) is not None, dodge


def test_matcher_short_words_use_boundaries_no_false_positives():
    m = WordMatcher(["ass"])  # short -> boundary path
    assert m.matches("you ass") is not None
    assert m.matches("don't be an @ss") is not None  # leet folded, still bounded
    assert m.matches("class") is None
    assert m.matches("assassin") is None
    assert m.matches("passsword") is None


def test_matcher_empty_and_miss():
    assert WordMatcher([]).matches("anything") is None
    assert WordMatcher(["badword"]).matches("perfectly fine text") is None


def test_caps_ratio():
    assert caps_ratio("HELLO") == 1.0
    assert caps_ratio("Hello") == 0.2
    assert caps_ratio("!!!123") == 0.0          # no letters
    assert abs(caps_ratio("HELLO world") - 0.5) < 1e-9


def test_count_emojis_custom_and_unicode():
    assert count_emojis("hi") == 0
    assert count_emojis("hi \U0001f600\U0001f600") == 2
    assert count_emojis("<:wave:123> and <a:spin:456>") == 2
    assert count_emojis("\U0001f600 <:x:1>") == 2


def test_strip_code_removes_fenced_and_inline():
    assert "SHOUT" not in strip_code("```\nSHOUT\n```")
    assert "CODE" not in strip_code("look at `CODE` here")
    assert "keep" in strip_code("keep `this`")
