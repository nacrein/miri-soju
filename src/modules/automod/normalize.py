"""Bypass-resistant text normalization for the bad-content filter (pure, no Discord).

The hard part of a word filter is people dodging it: ``b a d``, ``b.a.d``, ``b​a​d``,
``b4d``, ``ｂａｄ``, ``b​а​d`` (Cyrillic а). We fold all of that to a comparable form:

* ``_fold`` — casefold, NFKD-decompose (drops accents, folds full-width/confusables),
  then map leetspeak. Keeps spaces/punctuation, so it's safe for word-boundary matching.
* ``normalize_text`` — ``_fold`` then strip every non-alphanumeric and collapse repeated
  characters, giving a de-spaced form for substring matching.

A :class:`WordMatcher` matches long needles (≥ ``MIN_SUBSTR``) as de-spaced substrings
(bypass-resistant) and short needles on word boundaries of the folded text (so ``ass``
hits "you ass" but never "class"). Building the matcher is done once per guild and cached.
"""

from __future__ import annotations

import re
import unicodedata

# Short words match on boundaries; words this long or longer use the de-spaced substring.
MIN_SUBSTR = 5

# Leetspeak / common letter substitutions. Applied after casefold, to both needle and text.
_LEET = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t",
    "8": "b", "9": "g", "@": "a", "$": "s", "!": "i", "|": "i", "+": "t",
}
# Common cross-script homoglyphs (Cyrillic/Greek that look like Latin letters). NFKD
# does not fold these, so map the frequent ones explicitly — a Cyrillic 'а' is a
# favourite way to smuggle a banned word past a naive filter.
_CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k",
    "м": "m", "н": "h", "т": "t", "в": "b", "і": "i", "ѕ": "s", "ԁ": "d", "ј": "j",
    "ο": "o", "α": "a", "ν": "v", "ρ": "p", "τ": "t", "ι": "i", "κ": "k", "ε": "e",
}
_FOLD_TABLE = str.maketrans({**_LEET, **_CONFUSABLES})

_NONALNUM = re.compile(r"[^a-z0-9]")


def _fold(s: str) -> str:
    """Casefold, drop accents/confusables (NFKD), map leetspeak. Spaces are kept."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().translate(_FOLD_TABLE)


def _collapse_repeats(s: str) -> str:
    """Collapse any run of the same character to one (``baaaad`` -> ``bad``)."""
    out: list[str] = []
    prev = ""
    for c in s:
        if c != prev:
            out.append(c)
            prev = c
    return "".join(out)


def normalize_text(s: str) -> str:
    """The de-spaced, repeat-collapsed form used for substring matching."""
    return _collapse_repeats(_NONALNUM.sub("", _fold(s)))


def normalize_token(word: str) -> str:
    """How a banned word is stored: lightly folded (casefold/accents/leet), trimmed.

    Storing the folded form keeps the DB human-readable and lets the matcher rebuild
    both the boundary and substring representations from it deterministically.
    """
    return _fold(word).strip()


class WordMatcher:
    """Compiled banned-word matcher. ``matches(text)`` returns the hit word or None."""

    def __init__(self, words: list[str]) -> None:
        self._long: list[str] = []          # normalized (de-spaced) needles, ≥ MIN_SUBSTR
        shorts: list[str] = []              # folded short needles, boundary-matched
        for raw in words:
            folded = normalize_token(raw)
            if not folded:
                continue
            norm = normalize_text(raw)
            if len(norm) >= MIN_SUBSTR:
                self._long.append(norm)
            elif folded:
                shorts.append(re.escape(folded))
        self._short_re = re.compile(rf"\b(?:{'|'.join(shorts)})\b") if shorts else None

    def matches(self, text: str) -> str | None:
        if self._short_re is not None:
            m = self._short_re.search(_fold(text))
            if m:
                return m.group(0)
        if self._long:
            norm = normalize_text(text)
            for needle in self._long:
                if needle in norm:
                    return needle
        return None


# ── cheap content metrics (pure) ──────────────────────────────────────────────

_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]*`")
_CUSTOM_EMOJI = re.compile(r"<a?:\w+:\d+>")
# Approximate unicode-emoji ranges — enough to flag emoji spam, not a full grapheme parse.
_UNICODE_EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f000-\U0001f0ff"
    "\U00002190-\U000021ff\U00002b00-\U00002bff\U0001f900-\U0001f9ff]"
)


def strip_code(text: str) -> str:
    """Remove fenced and inline code so a pasted snippet doesn't trip the caps filter."""
    return _INLINE_CODE.sub("", _CODE_BLOCK.sub("", text))


def caps_ratio(text: str) -> float:
    """Fraction of letters that are uppercase (0.0 when there are no letters)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def count_emojis(text: str) -> int:
    """Custom ``<:name:id>`` emojis plus (approximate) unicode emoji code points."""
    return len(_CUSTOM_EMOJI.findall(text)) + len(_UNICODE_EMOJI.findall(text))
