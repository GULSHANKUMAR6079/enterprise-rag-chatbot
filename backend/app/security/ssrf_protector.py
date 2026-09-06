"""
Server-Side Request Forgery (SSRF) Protection.
Validates outbound URLs before requests are made, preventing attacks against internal services,
loopback interfaces, and cloud metadata endpoints (e.g. AWS/GCP 169.254.169.254).
"""
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional, Set
from backend.app.core.exceptions import SSRFBlockedException

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 Private
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / Cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 Private
    ipaddress.ip_network("::1/128"),            # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),          # IPv6 Link-Local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
}


class SSRFProtector:
    def __init__(self, allowed_domains: Optional[Set[str]] = None):
        self.allowed_domains = allowed_domains or set()

    def validate_url(self, target_url: str) -> None:
        """
        Validates target URL against SSRF rules.
        Raises SSRFBlockedException if the URL targets a restricted IP or host.
        """
        if not target_url:
            raise SSRFBlockedException("Empty target URL")

        parsed = urlparse(target_url)

        # 1. Enforce HTTPS
        if parsed.scheme.lower() != "https":
            raise SSRFBlockedException(f"Scheme '{parsed.scheme}' disallowed. HTTPS is strictly required.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFBlockedException("URL must contain a valid hostname.")

        hostname_lower = hostname.lower()

        # 2. Block known malicious / metadata hostnames
        if hostname_lower in BLOCKED_HOSTNAMES or "169.254.169.254" in hostname_lower:
            raise SSRFBlockedException(f"Target host '{hostname}' is explicitly blocked.")

        # 3. If domain allowlist is active, verify membership
        if self.allowed_domains and hostname_lower not in self.allowed_domains:
            raise SSRFBlockedException(f"Domain '{hostname}' is not in approved allowlist.")

        # 4. Resolve DNS and inspect resolved IP addresses
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)

                # Check if IP falls within any blocked network
                for net in BLOCKED_IP_NETWORKS:
                    if ip_obj in net:
                        raise SSRFBlockedException(
                            f"Host '{hostname}' resolved to blocked private/metadata IP: {ip_str}"
                        )
        except socket.gaierror as exc:
            raise SSRFBlockedException(f"DNS resolution failed for '{hostname}': {exc}")


ssrf_protector = SSRFProtector()
