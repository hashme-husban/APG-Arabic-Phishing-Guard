"""
APG URL Sandbox — URL Validation Helpers

Provides scheme allowlist enforcement, DNS pre-resolution, and private/internal
IP range blocking.  All helpers raise URLValidationError with a machine-readable
reason string on failure.

Security design:
  - Fail closed: any error (DNS failure, unparseable IP, empty input) → blocked.
  - Strict allowlist for schemes: only http and https are permitted.
  - All RFC 1918, loopback, link-local, metadata, and reserved ranges are blocked.
  - IPv4 AND IPv6 private ranges are covered.
  - DNS pre-resolution prevents bypasses via DNS rebinding (combined with redirect
    re-validation after page.goto()).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# ─── Allowed schemes ──────────────────────────────────────────────────────────

_ALLOWED_SCHEMES = frozenset({"http", "https"})

# ─── Blocked networks ─────────────────────────────────────────────────────────

_BLOCKED_NETWORKS: list[ipaddress._BaseNetwork] = [
    # IPv4 loopback
    ipaddress.ip_network("127.0.0.0/8"),
    # RFC 1918 private ranges
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local (includes AWS/GCP/Azure metadata endpoint 169.254.169.254)
    ipaddress.ip_network("169.254.0.0/16"),
    # This-network
    ipaddress.ip_network("0.0.0.0/8"),
    # Reserved / broadcast
    ipaddress.ip_network("240.0.0.0/4"),
    # Shared address space (RFC 6598 — used by some ISPs as carrier-grade NAT)
    ipaddress.ip_network("100.64.0.0/10"),
    # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.18.0.0/15"),
    # Documentation ranges (RFC 5737)
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    # IPv6 loopback
    ipaddress.ip_network("::1/128"),
    # IPv6 link-local
    ipaddress.ip_network("fe80::/10"),
    # IPv6 unique-local (RFC 4193 — analogous to RFC 1918)
    ipaddress.ip_network("fc00::/7"),
    # IPv4-mapped IPv6 addresses (::ffff:x.x.x.x)
    ipaddress.ip_network("::ffff:0:0/96"),
]

# ─── Error type ───────────────────────────────────────────────────────────────

class URLValidationError(ValueError):
    """Raised when a URL fails a security validation check."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_ip_blocked(ip_str: str) -> bool:
    """Return True if ip_str falls within any blocked network. Fails closed."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return True  # unparseable IP → block


def _registered_domain(hostname: str) -> str:
    """Return last-two-label registered domain (e.g. 'sub.example.com' → 'example.com')."""
    parts = [p for p in hostname.lower().strip(".").split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname.lower().strip(".")


# ─── Public validators ────────────────────────────────────────────────────────

def validate_url_scheme(url: str) -> None:
    """
    Raise URLValidationError if url does not use an allowed scheme.

    Allowed: http, https.
    Blocked: file, ftp, data, javascript, chrome, about, blob, and anything else.
    """
    url = (url or "").strip()
    if not url:
        raise URLValidationError("empty_url")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower().strip()

    if not scheme:
        raise URLValidationError("empty_scheme")
    if scheme not in _ALLOWED_SCHEMES:
        raise URLValidationError(f"blocked_scheme:{scheme}")


def resolve_and_validate_host(hostname: str) -> None:
    """
    DNS-resolve hostname and raise URLValidationError if:
      - hostname is empty
      - hostname is 'localhost' or a .localhost subdomain
      - DNS resolution fails
      - ANY resolved IP falls in a blocked network range

    Fails closed: DNS errors → blocked.
    """
    hostname = (hostname or "").lower().strip().rstrip(".")
    if not hostname:
        raise URLValidationError("empty_hostname")

    # Reject 'localhost' variants before DNS (they may not resolve externally)
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise URLValidationError("blocked_host:localhost")

    # If hostname is already a bare IP, validate it directly.
    # We must first confirm it parses as an IP — _is_ip_blocked() fails closed
    # (returns True for unparseable strings) so we cannot call it on a hostname
    # without first verifying it is actually an IP address.
    try:
        ipaddress.ip_address(hostname)  # raises ValueError if not an IP
        # hostname IS a valid IP address — check the blocked-range policy
        if _is_ip_blocked(hostname):
            raise URLValidationError(f"blocked_ip:{hostname}")
        return  # valid public bare IP — no DNS needed
    except URLValidationError:
        raise
    except ValueError:
        pass  # not a bare IP — proceed to DNS resolution

    # DNS resolution
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise URLValidationError(f"dns_failed:{exc}") from exc

    if not infos:
        raise URLValidationError("dns_no_results")

    for info in infos:
        ip_str = info[4][0]
        if _is_ip_blocked(ip_str):
            raise URLValidationError(f"blocked_ip:{ip_str}")


def validate_url_safe(url: str) -> None:
    """
    Full URL safety pre-flight check.

    Validates scheme then resolves and validates the hostname.
    Raises URLValidationError with a machine-readable reason on any failure.
    Call this before starting any browser navigation.
    """
    validate_url_scheme(url)
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().strip()
    resolve_and_validate_host(hostname)
