"""
Constraint handlers for requirement nodes.

This module imports all node handlers to register them with the dispatch system.
Import this module to ensure all handlers are registered.
"""

# Import all node handlers to register them with dispatch
from shared.optimizer.requirements.nodes import (  # noqa: F401
    allgroup,
    anygroup,
    ci,
    ci_threshold,
    course,
    gir,
    gir_threshold,
    hass,
    hass_threshold,
    plainstring,
    subject_threshold,
    unit_threshold,
)
