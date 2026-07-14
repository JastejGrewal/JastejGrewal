"""ONVIF WS-Discovery — blueprint §4.3a tier (a), tried before URL patterns.

Implements the multicast Probe/ProbeMatch handshake with the standard library
only. We deliberately do not pull in an ONVIF client dependency for Phase 1:
discovery (does a compliant device exist, and where) is all the pipeline needs,
because media-profile negotiation can fall back to the URL-pattern library.
"""

from __future__ import annotations

import re
import socket
import uuid
from dataclasses import dataclass, field

WS_DISCOVERY_ADDR = ("239.255.255.250", 3702)

_PROBE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{message_id}</w:MessageID>
    <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>"""

_XADDRS_RE = re.compile(r"<[^>]*XAddrs[^>]*>([^<]+)<", re.IGNORECASE)


@dataclass
class OnvifDevice:
    """A device that answered the WS-Discovery probe."""

    xaddrs: list[str] = field(default_factory=list)
    raw_source: str = ""

    @property
    def host(self) -> str | None:
        for addr in self.xaddrs:
            m = re.match(r"https?://([^:/]+)", addr)
            if m:
                return m.group(1)
        return None


def build_probe(message_id: str | None = None) -> bytes:
    return _PROBE_TEMPLATE.format(message_id=message_id or uuid.uuid4()).encode()


def parse_probe_match(payload: bytes, source: str = "") -> OnvifDevice | None:
    """Parse a ProbeMatch response; returns None if it isn't one."""
    try:
        text = payload.decode("utf-8", errors="replace")
    except Exception:
        return None
    if "ProbeMatch" not in text:
        return None
    xaddrs: list[str] = []
    for m in _XADDRS_RE.finditer(text):
        # XAddrs is a space-separated URI list.
        xaddrs.extend(u for u in m.group(1).strip().split() if u)
    if not xaddrs:
        return None
    return OnvifDevice(xaddrs=xaddrs, raw_source=source)


def discover(timeout: float = 3.0) -> list[OnvifDevice]:
    """Broadcast a WS-Discovery probe and collect ProbeMatch responders."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)
    devices: list[OnvifDevice] = []
    seen_hosts: set[str] = set()
    try:
        sock.sendto(build_probe(), WS_DISCOVERY_ADDR)
        while True:
            try:
                payload, addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            device = parse_probe_match(payload, source=addr[0])
            if device and device.host and device.host not in seen_hosts:
                seen_hosts.add(device.host)
                devices.append(device)
    finally:
        sock.close()
    return devices
