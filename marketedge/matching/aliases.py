"""Deterministic, dependency-free participant-name normalisation.

Pure function only — no storage dependency, so every other matching module
(and the connector mappers, which cannot do I/O mid-mapping) can import it
without risking a cycle. The DB-backed alias-table override layer (spec
section 11.2's "controlled alias table") lives in `alias_resolver.py`,
which depends on this module, not the other way round.
"""

from __future__ import annotations

import re
import unicodedata

_SUFFIXES = (" FC", " CF", " AFC", " SC", " CLUB")
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


def normalize(raw_name: str) -> str:
    """Strip accents/punctuation, uppercase, drop common club suffixes,
    collapse whitespace. Not a full fuzzy-match algorithm — intentionally
    simple and predictable so its behaviour is easy to reason about and
    test. Good enough to join "Arsenal" / "Arsenal FC" / "ARSENAL" without
    a database round trip; genuinely ambiguous names still need the
    alias-table override (spec section 11.2 warns against relying solely
    on fuzzy matching)."""
    text = unicodedata.normalize("NFKD", raw_name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().strip()
    for suffix in _SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    text = _NON_ALNUM.sub("_", text).strip("_")
    return text
