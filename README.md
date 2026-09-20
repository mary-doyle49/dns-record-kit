# dnsrecords

A small library for working with DNS records in Python: parse them out
of BIND-style zone file text, validate them, and format them back out.

Zone files are plain text but the syntax has enough quirks (optional
TTL, optional class, TTL and class in either order, quoted TXT data)
that hand-rolling a parser for a one-off script always ends up buggier
than expected. This wraps that in a handful of dataclasses that
validate their own fields, so a `Record` you're holding is guaranteed
to be one that could legally appear in a zone file.

No third-party dependencies, standard library only.

## Install

Not published anywhere yet. Copy `src/dnsrecords` into your project,
or add this repo as a path/git dependency.

## Usage

Parsing a zone file:

```python
from dnsrecords import parse_zone

zone_text = """
; example.com zone excerpt
www.example.com.    3600 IN A     192.0.2.10
example.com.        3600 IN MX    10 mail.example.com.
example.com.        3600 IN TXT   "v=spf1 -all"
"""

records = parse_zone(zone_text)
for record in records:
    print(record.name, record.rtype, record.rdata())
```

`$ORIGIN` and `$TTL` directives are tracked as `parse_zone` walks the
file, so `@` and TTL-less lines resolve the way BIND resolves them:

```python
zone_text = """
$ORIGIN example.com.
$TTL 7200
@       IN A     192.0.2.10
mail    IN A     192.0.2.20
"""

records = parse_zone(zone_text)
# records[0].name == "example.com.", records[0].ttl == 7200
```

Building and validating records directly:

```python
from dnsrecords import ARecord, MXRecord

a = ARecord(name="host.example.com.", ttl=300, address="203.0.113.5")

# Raises ValueError: invalid IPv4 address: '999.0.0.1'
bad = ARecord(name="host.example.com.", ttl=300, address="999.0.0.1")
```

Formatting records back to zone file lines:

```python
from dnsrecords import format_zone

print(format_zone(records))
```

## Supported record types

`A`, `AAAA`, `CNAME`, `MX`, `NS`, `SOA`, `SRV`, `TXT`. `CAA` is planned;
see the code for the current field set on each.

## Status

Early skeleton. The parser handles the common single-line record
syntax, and `parse_zone` tracks `$ORIGIN`/`$TTL` directives (so `@`
resolves and TTL-less lines pick up the right default). It does not
yet handle multi-line records in parentheses, or expanding relative
(non-FQDN, non-`@`) names against `$ORIGIN`.
