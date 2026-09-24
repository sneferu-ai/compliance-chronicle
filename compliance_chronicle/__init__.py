"""The Compliance Chronicle — production tooling for the monthly,
citation-verified regulatory-change briefing for Texas cottage-food
operators.

Public surface:

* :mod:`compliance_chronicle.models` — the issue data model
* :mod:`compliance_chronicle.sources` — the authoritative-source registry
* :mod:`compliance_chronicle.verification` — the verification ledger
* :mod:`compliance_chronicle.gates` — the publish gates (falsification
  criteria made executable)
* :mod:`compliance_chronicle.assemble` — Sneferu report + curation → issue
* :mod:`compliance_chronicle.render_email` — the monthly email
* :mod:`compliance_chronicle.render_pdf` — the text-selectable PDF archive
"""

from .models import (  # noqa: F401
    ACTION_LIST_NOTE,
    DISCLAIMER,
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    Action,
    CalendarEntry,
    ChangeItem,
    Citation,
    Issue,
    SearchLogEntry,
)

__version__ = "0.1.0"
