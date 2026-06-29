"""Tests for the stateless scan: ordering, thresholds, allowlist, and inert filters."""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.automod.detector import MessageView, scan_static
from src.modules.automod.normalize import WordMatcher


def _cfg(**over):
    base = dict(
        filter_mentions=True, mention_limit=5, block_everyone=True,
        filter_invites=True, filter_links=True,
        filter_words=True, filter_caps=True, caps_percent=70, caps_min_len=10,
        filter_emoji=True, emoji_limit=5,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _view(content="", *, mentions=0, everyone=False, can_everyone=False):
    return MessageView(content=content, mention_count=mentions,
                       mentions_everyone=everyone, author_can_mention_everyone=can_everyone)


def test_invite_detected():
    v = scan_static(_view("join discord.gg/abcd"), _cfg(), None, set())
    assert v.category == "invite"


def test_links_respect_allowlist_and_invites_ignored_by_link_filter():
    assert scan_static(_view("see http://evil.test/x"), _cfg(filter_invites=False), None, set()).category == "link"
    # allowlisted domain (and subdomain) passes
    assert scan_static(_view("see http://youtube.com/x"), _cfg(filter_invites=False), None, {"youtube.com"}) is None
    assert scan_static(_view("see http://m.youtube.com/x"), _cfg(filter_invites=False), None, {"youtube.com"}) is None
    # a discord invite is handled by the invite filter, not flagged as a bare link
    assert scan_static(_view("discord.com/invite/x"), _cfg(filter_invites=False), None, set()) is None


def test_mention_boundary_and_everyone():
    assert scan_static(_view(mentions=5), _cfg(), None, set()) is None       # == limit ok
    assert scan_static(_view(mentions=6), _cfg(), None, set()).category == "mention"
    # @everyone only trips when the author lacks the permission
    assert scan_static(_view("@everyone", everyone=True, can_everyone=False), _cfg(), None, set()).category == "everyone"
    assert scan_static(_view("@everyone", everyone=True, can_everyone=True), _cfg(), None, set()) is None


def test_words_use_matcher():
    m = WordMatcher(["badword"])
    assert scan_static(_view("this is a b a d w o r d"), _cfg(), m, set()).category == "word"
    assert scan_static(_view("totally clean"), _cfg(), m, set()) is None


def test_caps_respects_min_length():
    assert scan_static(_view("SHORT"), _cfg(), None, set()) is None                  # under min_len
    assert scan_static(_view("STOP YELLING AT ME"), _cfg(), None, set()).category == "caps"


def test_emoji_over_limit():
    assert scan_static(_view("\U0001f600" * 6), _cfg(), None, set()).category == "emoji"
    assert scan_static(_view("\U0001f600" * 5), _cfg(), None, set()) is None


def test_ordering_mention_beats_word():
    m = WordMatcher(["badword"])
    v = scan_static(_view("badword", mentions=10), _cfg(), m, set())
    assert v.category == "mention"  # mentions checked before words


def test_each_filter_off_is_inert():
    off = _cfg(filter_mentions=False, filter_invites=False, filter_links=False,
              filter_words=False, filter_caps=False, filter_emoji=False)
    assert scan_static(_view("discord.gg/x @everyone SHOUTING http://evil.test"),
                       off, WordMatcher(["evil"]), set(), ) is None
