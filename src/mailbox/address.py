"""RFC 5322 mailbox parsing, canonicalization and list splitting."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Characters that may not appear in an unquoted (dot-atom) local part.
# A dot is handled separately because it separates the atoms.
_SPECIALS = set('()<>[]:;@\\,."')


def _unescape_quoted(value: str) -> str:
    """Restore the backslash escapes inside a quoted string body."""
    out: List[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            out.append(value[index + 1])
            index += 2
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _split_display(value: str) -> str:
    """Trim a display name and drop a surrounding pair of double quotes."""
    text = value.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return _unescape_quoted(text[1:-1])
    return text


def _strip_comments(text: str) -> str:
    """Remove parenthesized comments that are outside quoted strings."""
    out: List[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            # Copy a quoted string verbatim, honouring backslash escapes.
            out.append(char)
            index += 1
            while index < length:
                current = text[index]
                if current == "\\" and index + 1 < length:
                    out.append(current)
                    out.append(text[index + 1])
                    index += 2
                    continue
                out.append(current)
                index += 1
                if current == '"':
                    break
            continue
        if char == "(":
            depth = 1
            index += 1
            while index < length and depth:
                current = text[index]
                if current == "\\" and index + 1 < length:
                    index += 2
                    continue
                if current == "(":
                    depth += 1
                elif current == ")":
                    depth -= 1
                index += 1
            if depth:
                raise ValueError("unterminated comment")
            continue
        out.append(char)
        index += 1
    return "".join(out)


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


def _find_angle(text: str) -> Optional[Tuple[str, str]]:
    """Return ``(display, address)`` if the text uses ``<...>`` syntax."""
    open_at = -1
    in_quotes = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_quotes:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_quotes = False
        else:
            if char == '"':
                in_quotes = True
            elif char == "<":
                open_at = index
                break
        index += 1
    if open_at < 0:
        return None

    in_quotes = False
    close_at = open_at + 1
    while close_at < len(text):
        char = text[close_at]
        if in_quotes:
            if char == "\\":
                close_at += 2
                continue
            if char == '"':
                in_quotes = False
        else:
            if char == '"':
                in_quotes = True
            elif char == ">":
                break
        close_at += 1
    if close_at >= len(text):
        raise ValueError("unterminated angle bracket")
    if text[close_at + 1:].strip():
        raise ValueError("trailing text after the address")
    return text[:open_at], text[open_at + 1:close_at]


def _is_dot_atom_char(char: str) -> bool:
    return not (char.isspace() or char in _SPECIALS or not char.isprintable())


def _is_dot_atom(value: str) -> bool:
    """Return whether ``value`` is a valid unquoted (dot-atom) local part."""
    if not value:
        return False
    return all(
        segment and all(_is_dot_atom_char(char) for char in segment)
        for segment in value.split(".")
    )


def _quote_local(value: str) -> str:
    """Render ``value`` as a quoted local part with backslash escapes."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % escaped


def _parse_local(raw: str) -> str:
    """Validate and normalize a local part, preserving its letter case."""
    if raw.startswith('"'):
        if len(raw) < 2 or not raw.endswith('"'):
            raise ValueError("unterminated quoted local part")
        return _unescape_quoted(raw[1:-1])

    for atom in raw.split("."):
        if not atom:
            raise ValueError("empty dot-atom segment in %r" % (raw,))
        for char in atom:
            if not _is_dot_atom_char(char):
                raise ValueError("illegal character %r in local part" % (char,))
    return raw


def _normalize_label(label: str) -> str:
    text = label.lower()
    if all(ord(char) < 128 for char in text):
        return text
    return "xn--" + text.encode("punycode").decode("ascii")


def normalize_domain(domain: str) -> str:
    """Return the normalized form of a domain."""
    if not isinstance(domain, str):
        raise ValueError("domain must be a string")
    text = domain.strip()
    if not text:
        raise ValueError("empty domain")
    return ".".join(_normalize_label(label) for label in text.split("."))


def parse(text: str) -> Dict[str, str]:
    """Split a single mailbox into display name, local part and domain."""
    if not isinstance(text, str):
        raise ValueError("mailbox must be a string")
    cleaned = _strip_comments(text).strip()
    if not cleaned:
        raise ValueError("empty mailbox")

    angle = _find_angle(cleaned)
    if angle is None:
        display_raw = ""
        address = cleaned
    else:
        display_raw, address = angle
    address = address.strip()
    if not address:
        raise ValueError("empty address")

    at = _last_at(address)
    if at < 0:
        raise ValueError("mailbox is missing @: %r" % (text,))
    local_raw = address[:at].strip()
    domain_raw = address[at + 1:].strip()
    if not local_raw:
        raise ValueError("empty local part")
    if not domain_raw:
        raise ValueError("empty domain")

    return {
        "display": _split_display(display_raw),
        "local": _parse_local(local_raw),
        "domain": domain_raw,
    }


def canonical(text: str) -> str:
    """Return the canonical ``local@domain`` form of a mailbox."""
    parsed = parse(text)
    local = parsed["local"]
    if not _is_dot_atom(local):
        local = _quote_local(local)
    return "%s@%s" % (local, normalize_domain(parsed["domain"]))


def split_list(text: str) -> List[str]:
    """Split an address list on the commas that separate addresses.

    Commas inside quoted strings, angle brackets and parenthesized comments
    are not separators.  RFC 5322 group syntax is expanded into its members.
    """
    if not isinstance(text, str):
        raise ValueError("address list must be a string")

    items: List[str] = []
    current: List[str] = []
    in_quotes = False
    in_angle = False
    depth = 0
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if in_quotes:
            current.append(char)
            if char == "\\" and index + 1 < length:
                current.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_quotes = False
            index += 1
            continue
        if depth:
            current.append(char)
            if char == "\\" and index + 1 < length:
                current.append(text[index + 1])
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
            continue
        if char == '"':
            in_quotes = True
            current.append(char)
        elif char == "(":
            depth = 1
            current.append(char)
        elif char == "<":
            in_angle = True
            current.append(char)
        elif char == ">":
            in_angle = False
            current.append(char)
        elif in_angle:
            current.append(char)
        elif char in ",;":
            fragment = "".join(current).strip()
            if fragment:
                items.append(fragment)
            current = []
        elif char == ":":
            # Start of a group: the group name itself is not a member.
            current = []
        else:
            current.append(char)
        index += 1

    fragment = "".join(current).strip()
    if fragment:
        items.append(fragment)
    return items


def is_same_mailbox(first: str, second: str) -> bool:
    """Return whether two spellings denote the same mailbox."""
    return canonical(first) == canonical(second)
