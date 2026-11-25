"""Public smoke tests for mailbox parsing and canonicalization."""

from __future__ import annotations

from mailbox import canonical, is_same_mailbox, normalize_domain, parse, split_list


def test_parse_splits_display_name_and_address() -> None:
    mailbox = parse("Alice Smith <Alice@Example.COM>")
    assert mailbox["display"] == "Alice Smith"
    assert mailbox["local"] == "Alice"
    assert mailbox["domain"] == "Example.COM"


def test_canonical_drops_the_display_name() -> None:
    assert canonical('"Doe, John" <John@Example.COM>') == "John@example.com"


def test_domain_is_lowered_and_punycoded() -> None:
    assert normalize_domain("BÜCHER.example") == "xn--bcher-kva.example"


def test_split_list_keeps_quoted_display_names_together() -> None:
    assert split_list('a@x.com, "Doe, John" <j@y.com>') == [
        "a@x.com",
        '"Doe, John" <j@y.com>',
    ]


def test_same_mailbox_ignores_the_display_name() -> None:
    assert is_same_mailbox("Alice <a@x.com>", "a@x.com") is True