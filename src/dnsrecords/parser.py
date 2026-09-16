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
)

DEFAULT_TTL = 3600

_BUILDERS = {
    "A": lambda name, ttl, fields: ARecord(name, ttl, fields[0]),
    "AAAA": lambda name, ttl, fields: AAAARecord(name, ttl, fields[0]),
    "CNAME": lambda name, ttl, fields: CNAMERecord(name, ttl, fields[0]),
    "NS": lambda name, ttl, fields: NSRecord(name, ttl, fields[0]),
    "MX": lambda name, ttl, fields: MXRecord(name, ttl, int(fields[0]), fields[1]),
    "TXT": lambda name, ttl, fields: TXTRecord(name, ttl, " ".join(fields).strip('"')),
    "SOA": lambda name, ttl, fields: SOARecord(
        name,
        ttl,
        fields[0],
        fields[1],
        int(fields[2]),
        int(fields[3]),
        int(fields[4]),
        int(fields[5]),
        int(fields[6]),
    ),
    "SRV": lambda name, ttl, fields: SRVRecord(
        name, ttl, int(fields[0]), int(fields[1]), int(fields[2]), fields[3]
    ),
}


def parse_line(line: str) -> Optional[Record]:
    """Parse one line of zone-file syntax into a Record.

    Returns None for blank lines and comments so callers can filter a
    whole file without special-casing those lines themselves.
    """
    stripped = line.split(";", 1)[0].strip()
    if not stripped:
        return None

    tokens = stripped.split()
    name = tokens.pop(0)
    ttl = DEFAULT_TTL
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

    return _BUILDERS[rtype](name, ttl, tokens)


def parse_zone(text: str) -> List[Record]:
    """Parse every record line in a zone file, skipping blanks and comments."""
    records = []
    for line in text.splitlines():
        record = parse_line(line)
        if record is not None:
            records.append(record)
    return records


def format_zone(records: List[Record]) -> str:
    return "\n".join(record.to_line() for record in records)
