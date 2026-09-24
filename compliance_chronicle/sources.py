"""Authoritative source registry for The Compliance Chronicle.

This module encodes, as data, the source taxonomy that
``docs/VERIFICATION_METHODOLOGY.md`` describes in prose: which source
classes qualify as authoritative for Texas cottage-food regulatory
claims, how they rank, and how conflicts between them resolve.

The registry is deliberately small and boring. A claim is only
"verified" when it carries a citation into one of the authoritative
classes; anything else — press, social media, word of mouth — is at
best a lead that must be confirmed against an authoritative source
before it can ship as verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class SourceClass:
    """One class of regulatory source and its authority metadata."""

    key: str
    label: str
    authority_rank: int  # higher wins in a conflict
    authoritative: bool  # False classes can never, alone, verify a claim
    host_patterns: Tuple[str, ...] = ()
    note: str = ""


# Authority order follows the methodology doc:
#   statute > administrative rule > official fee schedule >
#   agency guidance > county/local authority > legislative watch >
#   secondary press (never sufficient alone).
SOURCE_CLASSES = {
    "state_statute": SourceClass(
        key="state_statute",
        label="Texas statute (Texas Statutes / capitol publication)",
        authority_rank=100,
        authoritative=True,
        host_patterns=("statutes.capitol.texas.gov", "capitol.texas.gov"),
        note="Texas Health & Safety Code ch. 437 is the governing statute.",
    ),
    "state_admin_code": SourceClass(
        key="state_admin_code",
        label="Texas Administrative Code (Secretary of State publication)",
        authority_rank=90,
        authoritative=True,
        host_patterns=("texas.gov", "sos.state.tx.us"),
        note="25 TAC ch. 229 subch. N (§229.661) is the DSHS cottage-food rule.",
    ),
    "fee_schedule": SourceClass(
        key="fee_schedule",
        label="Official published fee schedule",
        authority_rank=80,
        authoritative=True,
        host_patterns=("dshs.texas.gov",),
        note="Fee claims verify only against the publishing body's own schedule.",
    ),
    "state_agency_guidance": SourceClass(
        key="state_agency_guidance",
        label="State agency guidance (DSHS / TDA publications)",
        authority_rank=70,
        authoritative=True,
        host_patterns=("dshs.texas.gov", "texasagriculture.gov"),
        note="Guidance interprets but cannot override statute or rule.",
    ),
    "county_health": SourceClass(
        key="county_health",
        label="County / local health authority publication",
        authority_rank=60,
        authoritative=True,
        host_patterns=(),
        note="Local requirements may add to, never replace, state requirements.",
    ),
    "legislative_watch": SourceClass(
        key="legislative_watch",
        label="Filed-bill watch (Texas Legislature Online)",
        authority_rank=50,
        authoritative=True,
        host_patterns=("capitol.texas.gov", "lrl.texas.gov"),
        note="A filed bill is a watch item, not a change in law.",
    ),
    "secondary_press": SourceClass(
        key="secondary_press",
        label="Secondary press / community / word of mouth",
        authority_rank=10,
        authoritative=False,
        note="A lead only. Can never verify a claim by itself.",
    ),
}

#: Source classes that must appear in the search log before an issue
#: may declare a quiet ("no material changes") month. The list mirrors
#: the sweep defined in VERIFICATION_METHODOLOGY.md §3.
REQUIRED_QUIET_MONTH_SOURCES: Tuple[str, ...] = (
    "state_statute",
    "state_admin_code",
    "state_agency_guidance",
    "fee_schedule",
)


def source_class_keys() -> Tuple[str, ...]:
    return tuple(SOURCE_CLASSES.keys())


def is_authoritative(source_class_key: str) -> bool:
    cls = SOURCE_CLASSES.get(source_class_key)
    return bool(cls and cls.authoritative)


def classify_url(url: str) -> Optional[str]:
    """Best-effort classification of a source URL into a source class.

    Returns the class key, or ``None`` when no pattern matches. The
    operator may always override classification in curation; this is a
    convenience for assembly, never a verdict.
    """

    if not url:
        return None
    lowered = url.lower()
    # More specific classes first: dshs.texas.gov is both texas.gov and
    # dshs.texas.gov; the agency classes must win over the generic TAC
    # host class when the path indicates guidance rather than rules.
    ordered = (
        "state_statute",
        "state_agency_guidance",
        "fee_schedule",
        "legislative_watch",
        "state_admin_code",
        "secondary_press",
    )
    for key in ordered:
        cls = SOURCE_CLASSES[key]
        for pattern in cls.host_patterns:
            if pattern in lowered:
                return key
    return None


def authority_rank(source_class_key: str) -> int:
    cls = SOURCE_CLASSES.get(source_class_key)
    return cls.authority_rank if cls else 0


def resolve_conflict(citation_a_class: str, citation_b_class: str) -> Optional[str]:
    """Resolve a conflict between two sources by authority rank.

    Returns the winning source-class key, or ``None`` when the two
    sources hold equal rank — an equal-authority conflict cannot be
    resolved by rule and the claim must ship as unverified with the
    conflict named in the reason.
    """

    rank_a = authority_rank(citation_a_class)
    rank_b = authority_rank(citation_b_class)
    if rank_a > rank_b:
        return citation_a_class
    if rank_b > rank_a:
        return citation_b_class
    return None


_CITATION_REF_RE = re.compile(r"(§|sec\.|section|chapter|ch\.|tac|hb|sb)\s*\d", re.IGNORECASE)


def looks_like_exact_citation(reference: str) -> bool:
    """Heuristic: does a citation reference look like an exact legal citation?

    An exact citation names an instrument and a pinpoint (section,
    chapter, bill number). "See the DSHS website" is not a citation.
    This is a floor check only; it cannot prove the citation is real —
    that is what the search log and operator spot-checks are for.
    """

    if not reference or not reference.strip():
        return False
    return bool(_CITATION_REF_RE.search(reference))
