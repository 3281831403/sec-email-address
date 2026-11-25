"""Public interface for the sec-email-address exercise."""

from .address import (
    canonical,
    is_same_mailbox,
    normalize_domain,
    parse,
    split_list,
)

__all__ = [
    "parse",
    "canonical",
    "normalize_domain",
    "split_list",
    "is_same_mailbox",
]