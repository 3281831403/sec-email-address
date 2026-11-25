"""RFC 5322 mailbox parsing, canonicalization and list splitting."""

from __future__ import annotations

from typing import Dict, List


def _unquote(value: str) -> str:
    """Remove surrounding double quotes from a display name or local part."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _last_at(text: str) -> int:
    """Return the index of the last ``@`` that is outside a quoted string."""
    in_quotes = False
    found = -1
    index = 0
    while index < len(text):
        char = text[index]
        if in_quotes:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_quotes = False
            index += 1
            continue
        if char == '"':
            in_quotes = True
            index += 1
            continue
        if char == "@":
            found = index
        index += 1
    return found


def normalize_domain(domain: str) -> str:
    """Return the normalized form of a domain."""
    text = (domain or "").strip()
    if not text:
        raise ValueError("empty domain")
    return text.lower()


def parse(text: str) -> Dict[str, str]:
    """Split a single mailbox into display name, local part and domain."""
    if not isinstance(text, str):
        raise ValueError("mailbox must be a string")
    raw = text.strip()
    if not raw:
        raise ValueError("empty mailbox")

    if "<" in raw:
        open_at = raw.index("<")
        close_at = raw.find(">", open_at)
        if close_at < 0:
            raise ValueError("unterminated angle bracket")
        display = _unquote(raw[:open_at].strip())
        address = raw[open_at + 1:close_at].strip()
        if raw[close_at + 1:].strip():
            raise ValueError("trailing text after the address")
    else:
        return {"display": "", "local": raw.lower(), "domain": ""}

    at = _last_at(address)
    if at < 0:
        raise ValueError("mailbox is missing @: %r" % (text,))
    local_raw = address[:at].strip()
    domain_raw = address[at + 1:].strip()
    if not local_raw:
        raise ValueError("empty local part")
    if not domain_raw:
        raise ValueError("empty domain")

    local = _unquote(local_raw).lower()
    return {"display": display, "local": local, "domain": domain_raw}


def canonical(text: str) -> str:
    """Return the canonical ``local@domain`` form of a mailbox."""
    parsed = parse(text)
    return "%s@%s" % (parsed["local"], parsed["domain"])


def split_list(text: str) -> List[str]:
    """Split an address list on the commas that separate addresses."""
    items: List[str] = []
    current: List[str] = []
    in_angle = False
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
            current.append(char)
            index += 1
            continue
        if char == ")" and depth:
            depth -= 1
            current.append(char)
            index += 1
            continue
        if depth:
            current.append(char)
            index += 1
            continue
        if char == "<":
            in_angle = True
        elif char == ">":
            in_angle = False
        elif char == "," and not in_angle:
            items.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    items.append("".join(current))
    return [item.strip() for item in items if item.strip()]


def is_same_mailbox(first: str, second: str) -> bool:
    """Return whether two spellings denote the same mailbox."""
    if canonical(first) != canonical(second):
        return False
    return (
        parse(first)["display"].strip().lower()
        == parse(second)["display"].strip().lower()
    )