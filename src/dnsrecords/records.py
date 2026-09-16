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
# Underscore is technically outside the RFC but is allowed here anyway:
# it's required for the owner names of real-world SRV records (e.g.
# "_sip._tcp.example.com.") and is also common for TXT-based
# verification records, and every major resolver accepts it in practice.
_HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9_-]{1,63}(?<!-))*\.?$"
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
class SOARecord(Record):
    mname: str
    rname: str
    serial: int
    refresh: int
    retry: int
    expire: int
    minimum: int

    def __post_init__(self) -> None:
        super().__post_init__()
        if not is_valid_hostname(self.mname):
            raise ValueError(f"invalid primary nameserver: {self.mname!r}")
        if not is_valid_hostname(self.rname):
            raise ValueError(f"invalid responsible-party mailbox: {self.rname!r}")
        for field_name, value in (
            ("serial", self.serial),
            ("refresh", self.refresh),
            ("retry", self.retry),
            ("expire", self.expire),
            ("minimum", self.minimum),
        ):
            # All five are 32-bit unsigned in the wire format.
            if not 0 <= value <= 4294967295:
                raise ValueError(f"{field_name} out of range: {value}")

    @property
    def rtype(self) -> str:
        return "SOA"

    def rdata(self) -> str:
        return (
            f"{self.mname} {self.rname} {self.serial} "
            f"{self.refresh} {self.retry} {self.expire} {self.minimum}"
        )


@dataclass(frozen=True)
class SRVRecord(Record):
    priority: int
    weight: int
    port: int
    target: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 0 <= self.priority <= 65535:
            raise ValueError(f"priority out of range: {self.priority}")
        if not 0 <= self.weight <= 65535:
            raise ValueError(f"weight out of range: {self.weight}")
        if not 0 <= self.port <= 65535:
            raise ValueError(f"port out of range: {self.port}")
        # "." is the documented way to say "service explicitly not
        # available at this name" and isn't a valid hostname on its own.
        if self.target != "." and not is_valid_hostname(self.target):
            raise ValueError(f"invalid SRV target: {self.target!r}")

    @property
    def rtype(self) -> str:
        return "SRV"

    def rdata(self) -> str:
        return f"{self.priority} {self.weight} {self.port} {self.target}"


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
