"""RTSP endpoint probing: the §4.3a connection flow.

At install time: (1) ONVIF WS-Discovery scan; (2) on failure, port-554 probe +
vendor URL-pattern candidates against detected hosts; (3) on failure, the site
is classified tier (c) and routed to the partner-upgrade path.

The RTSP probe sends DESCRIBE and inspects the status line: 200 means a live,
authorized stream; 401 means the path exists but credentials are wrong (still
a successful *family* identification — the installer fixes credentials); 404
means the path is wrong for this device.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

from .onvif import discover as onvif_discover
from .url_patterns import candidate_urls, redact


@dataclass
class CameraEndpoint:
    host: str
    url: str
    family: str            # "onvif" or a vendor-family name
    channel: int
    status: str            # "ok" | "auth_required"

    @property
    def redacted_url(self) -> str:
        return redact(self.url)


@dataclass
class ProbeReport:
    """Outcome of probing one host, for the site-survey record (§3.3)."""

    host: str
    endpoints: list[CameraEndpoint] = field(default_factory=list)
    attempts: int = 0

    @property
    def tier(self) -> str:
        """Integration tier per blueprint §4.3a."""
        if any(e.family == "onvif" for e in self.endpoints):
            return "a"
        if self.endpoints:
            return "b"
        return "c_candidate"  # nothing reachable digitally: refer to partner path


def _parse_rtsp_status(response: bytes) -> int | None:
    """Extract the status code from an RTSP response status line."""
    try:
        line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    except Exception:
        return None
    parts = line.split()
    if len(parts) >= 2 and parts[0].startswith("RTSP/"):
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def rtsp_describe(url: str, host: str, port: int = 554, timeout: float = 2.0) -> int | None:
    """Send an RTSP DESCRIBE and return the status code, or None on failure."""
    request = (
        f"DESCRIBE {url} RTSP/1.0\r\n"
        "CSeq: 1\r\n"
        "Accept: application/sdp\r\n"
        "User-Agent: sentinel-prober/0.1\r\n"
        "\r\n"
    ).encode()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request)
            response = sock.recv(4096)
    except OSError:
        return None
    return _parse_rtsp_status(response)


def port_open(host: str, port: int = 554, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_host(
    host: str,
    user: str = "admin",
    password: str = "admin",
    channels: int = 4,
    port: int = 554,
    describe=rtsp_describe,
    check_port=port_open,
) -> ProbeReport:
    """Try vendor URL patterns against one host (tier-b path).

    `describe` and `check_port` are injectable for testing. Once one family
    yields a hit, remaining families are skipped (a recorder speaks exactly
    one dialect) but the family's other channels are still enumerated.
    """
    report = ProbeReport(host=host)
    if not check_port(host, port):
        return report

    matched_family: str | None = None
    for family, url, channel in candidate_urls(
        host, user=user, password=password, channels=channels, port=port
    ):
        if matched_family is not None and family != matched_family:
            continue
        report.attempts += 1
        status = describe(url, host, port)
        if status == 200:
            report.endpoints.append(
                CameraEndpoint(host=host, url=url, family=family, channel=channel, status="ok")
            )
            matched_family = family
        elif status == 401:
            report.endpoints.append(
                CameraEndpoint(
                    host=host, url=url, family=family, channel=channel, status="auth_required"
                )
            )
            matched_family = family
    return report


def survey_site(
    hosts: list[str] | None = None,
    user: str = "admin",
    password: str = "admin",
    channels: int = 4,
    onvif_timeout: float = 3.0,
) -> list[ProbeReport]:
    """Full §4.3a flow: ONVIF discovery first, then URL patterns per host."""
    reports: list[ProbeReport] = []
    onvif_hosts: set[str] = set()

    for device in onvif_discover(timeout=onvif_timeout):
        if device.host:
            onvif_hosts.add(device.host)
            reports.append(
                ProbeReport(
                    host=device.host,
                    endpoints=[
                        CameraEndpoint(
                            host=device.host,
                            url=device.xaddrs[0],
                            family="onvif",
                            channel=0,
                            status="ok",
                        )
                    ],
                )
            )

    for host in hosts or []:
        if host in onvif_hosts:
            continue
        reports.append(probe_host(host, user=user, password=password, channels=channels))
    return reports
