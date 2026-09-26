"""Parsing and formatting of BIND-style zone file record lines."""

from __future__ import annotations

from typing import List, Optional

from .records import (
    AAAARecord,
    ARecord,
    CNAMERecord,
    MXRecord,
    NSRecord,
    Record,
    SOARecord,
    SRVRecord,
    TXTRecord,
    is_valid_hostname,
)

DEFAULT_TTL = 3600


def _qualify(name: str, origin: Optional[str]) -> str:
    """Expand a relative (non-FQDN) name against $ORIGIN, BIND-style.

    A name ending in "." is already fully qualified and passed through
    unchanged (this also covers SRV's "." target, which means "not
    available here" rather than a name at all). Otherwise, if an origin
    is known, it's appended; with no origin the name is left as-is since
    there's nothing to qualify it against.
    """
    if origin is None or name.endswith("."):
        return name
    return f"{name}.{origin}"


_BUILDERS = {
    "A": lambda name, ttl, fields, origin: ARecord(name, ttl, fields[0]),
    "AAAA": lambda name, ttl, fields, origin: AAAARecord(name, ttl, fields[0]),
    "CNAME": lambda name, ttl, fields, origin: CNAMERecord(
        name, ttl, _qualify(fields[0], origin)
    ),
    "NS": lambda name, ttl, fields, origin: NSRecord(
        name, ttl, _qualify(fields[0], origin)
    ),
    "MX": lambda name, ttl, fields, origin: MXRecord(
        name, ttl, int(fields[0]), _qualify(fields[1], origin)
    ),
    "TXT": lambda name, ttl, fields, origin: TXTRecord(
        name, ttl, " ".join(fields).strip('"')
    ),
    "SOA": lambda name, ttl, fields, origin: SOARecord(
        name,
        ttl,
        _qualify(fields[0], origin),
        _qualify(fields[1], origin),
        int(fields[2]),
        int(fields[3]),
        int(fields[4]),
        int(fields[5]),
        int(fields[6]),
    ),
    "SRV": lambda name, ttl, fields, origin: SRVRecord(
        name,
        ttl,
        int(fields[0]),
        int(fields[1]),
        int(fields[2]),
        _qualify(fields[3], origin),
    ),
}


def parse_line(
    line: str,
    *,
    origin: Optional[str] = None,
    default_ttl: int = DEFAULT_TTL,
) -> Optional[Record]:
    """Parse one line of zone-file syntax into a Record.

    Returns None for blank lines and comments so callers can filter a
    whole file without special-casing those lines themselves.

    `origin` and `default_ttl` carry the state that `$ORIGIN`/`$TTL`
    directives set elsewhere in the file: pass the current origin so a
    bare `@` owner name resolves and any relative (non-FQDN) name in the
    owner field or a hostname-valued rdata field gets `$ORIGIN` appended,
    and the current default TTL so lines that omit one pick up the right
    value. Directive lines themselves are not records; `parse_zone`
    handles those before calling here.
    """
    stripped = line.split(";", 1)[0].strip()
    if not stripped:
        return None

    tokens = stripped.split()
    name = tokens.pop(0)
    if name.startswith("$"):
        raise ValueError(
            f"{name!r} is a zone-file directive, not a record; "
            "use parse_zone to process $ORIGIN/$TTL"
        )
    if name == "@":
        if origin is None:
            raise ValueError("'@' owner name used with no $ORIGIN set")
        name = origin
    else:
        name = _qualify(name, origin)
    ttl = default_ttl
    rtype = None
    # Class ("IN") and TTL are both optional and can appear in either
    # order before the type, so walk left to right until the type shows up.
    while tokens:
        token = tokens.pop(0)
        if token.isdigit():
            ttl = int(token)
        elif token.upper() == "IN":
            continue
        elif token.upper() in _BUILDERS:
            rtype = token.upper()
            break
        else:
            raise ValueError(f"unrecognized record type: {token!r}")

    if rtype is None:
        raise ValueError(f"no record type found in line: {line!r}")

    return _BUILDERS[rtype](name, ttl, tokens, origin)


def _parse_origin_directive(stripped: str) -> str:
    tokens = stripped.split()
    if len(tokens) != 2:
        raise ValueError(f"malformed $ORIGIN directive: {stripped!r}")
    origin = tokens[1]
    if not is_valid_hostname(origin):
        raise ValueError(f"invalid $ORIGIN value: {origin!r}")
    return origin


def _parse_ttl_directive(stripped: str) -> int:
    tokens = stripped.split()
    if len(tokens) != 2 or not tokens[1].isdigit():
        raise ValueError(f"malformed $TTL directive: {stripped!r}")
    return int(tokens[1])


def parse_zone(text: str) -> List[Record]:
    """Parse every record line in a zone file, skipping blanks and comments.

    Tracks `$ORIGIN` and `$TTL` directives as it goes: `$ORIGIN` resolves
    a bare `@` owner name and expands any other relative name on later
    lines (owner name or a hostname-valued rdata field), and `$TTL`
    becomes the default TTL for lines that omit one. Both apply from the
    point they appear onward, matching BIND's behavior.

    Records may also span multiple lines by wrapping the rdata fields in
    parentheses, as is conventional for SOA:

        example.com. IN SOA ns1.example.com. admin.example.com. (
            2024010101 ; serial
            3600       ; refresh
            900        ; retry
            604800     ; expire
            86400 )    ; minimum

    Lines inside an open pair of parentheses are joined with spaces
    before being handed to `parse_line`, so the parens themselves never
    reach it.
    """
    records = []
    origin: Optional[str] = None
    default_ttl = DEFAULT_TTL
    pending: Optional[str] = None  # accumulated text of a record still open inside parens

    for raw_line in text.splitlines():
        content = raw_line.split(";", 1)[0].strip()

        if pending is not None:
            if content:
                pending = f"{pending} {content}"
            if pending.count("(") < pending.count(")"):
                raise ValueError(f"unbalanced parentheses in zone file: {raw_line!r}")
            if pending.count("(") > pending.count(")"):
                continue
            record = parse_line(
                pending.replace("(", " ").replace(")", " "),
                origin=origin,
                default_ttl=default_ttl,
            )
            pending = None
            if record is not None:
                records.append(record)
            continue

        if not content:
            continue

        first_token = content.split(None, 1)[0].upper()
        if first_token == "$ORIGIN":
            origin = _parse_origin_directive(content)
            continue
        if first_token == "$TTL":
            default_ttl = _parse_ttl_directive(content)
            continue

        if content.count("(") < content.count(")"):
            raise ValueError(f"unbalanced parentheses in zone file: {raw_line!r}")
        if content.count("(") > content.count(")"):
            pending = content
            continue

        record = parse_line(content, origin=origin, default_ttl=default_ttl)
        if record is not None:
            records.append(record)

    if pending is not None:
        raise ValueError("unterminated parenthesized record in zone file")

    return records


def format_zone(records: List[Record]) -> str:
    return "\n".join(record.to_line() for record in records)
