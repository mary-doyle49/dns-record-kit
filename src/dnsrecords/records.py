"""Data model for the DNS record types this library understands.

Each record type is a small frozen dataclass that validates its own
fields on construction, so a Record you're holding is always one that
could legally go in a zone file.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

# RFC 1035 label rules: 1-63 chars, alphanumeric plus hyphen, no
# leading/trailing hyphen per label. Trailing dot (FQDN form) is optional.
_HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)


def is_valid_hostname(name: str) -> bool:
    if not name or len(name) > 253:
        return False
    return bool(_HOSTNAME_RE.match(name))


@dataclass(frozen=True)
class Record:
    name: str
    ttl: int

    def __post_init__(self) -> None:
        if not is_valid_hostname(self.name):
            raise ValueError(f"invalid owner name: {self.name!r}")
        if self.ttl < 0:
            raise ValueError(f"ttl cannot be negative: {self.ttl}")

    @property
    def rtype(self) -> str:
        raise NotImplementedError

    def rdata(self) -> str:
        raise NotImplementedError

    def to_line(self) -> str:
        return f"{self.name}\t{self.ttl}\tIN\t{self.rtype}\t{self.rdata()}"


@dataclass(frozen=True)
class ARecord(Record):
    address: str

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            ipaddress.IPv4Address(self.address)
        except ValueError as exc:
            raise ValueError(f"invalid IPv4 address: {self.address!r}") from exc

    @property
    def rtype(self) -> str:
        return "A"

    def rdata(self) -> str:
        return self.address


@dataclass(frozen=True)
class AAAARecord(Record):
    address: str

    def __post_init__(self) -> None:
        super().__post_init__()
        try:
            ipaddress.IPv6Address(self.address)
        except ValueError as exc:
            raise ValueError(f"invalid IPv6 address: {self.address!r}") from exc

    @property
    def rtype(self) -> str:
        return "AAAA"

    def rdata(self) -> str:
        return self.address


@dataclass(frozen=True)
class CNAMERecord(Record):
    target: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not is_valid_hostname(self.target):
            raise ValueError(f"invalid CNAME target: {self.target!r}")

    @property
    def rtype(self) -> str:
        return "CNAME"

    def rdata(self) -> str:
        return self.target


@dataclass(frozen=True)
class NSRecord(Record):
    nameserver: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not is_valid_hostname(self.nameserver):
            raise ValueError(f"invalid nameserver: {self.nameserver!r}")

    @property
    def rtype(self) -> str:
        return "NS"

    def rdata(self) -> str:
        return self.nameserver


@dataclass(frozen=True)
class MXRecord(Record):
    priority: int
    exchange: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 0 <= self.priority <= 65535:
            raise ValueError(f"priority out of range: {self.priority}")
        if not is_valid_hostname(self.exchange):
            raise ValueError(f"invalid mail exchange: {self.exchange!r}")

    @property
    def rtype(self) -> str:
        return "MX"

    def rdata(self) -> str:
        return f"{self.priority} {self.exchange}"


@dataclass(frozen=True)
class TXTRecord(Record):
    text: str

    @property
    def rtype(self) -> str:
        return "TXT"

    def rdata(self) -> str:
        # Zone files require TXT data to be quoted, with internal
        # quotes and backslashes escaped so it round-trips on re-parse.
        escaped = self.text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
