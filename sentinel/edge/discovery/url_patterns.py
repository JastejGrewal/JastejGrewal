"""Vendor RTSP URL-pattern library — blueprint §4.3a tier (b).

Most budget/white-label NVRs are built on Hikvision, Dahua, or Uniview OEM
chipsets and expose per-channel RTSP streams at documented vendor URL paths
even when the box never advertises ONVIF compliance. When ONVIF WS-Discovery
fails, we try these templates against anything answering on port 554.

Stream indexes: 0 = main stream (full resolution, used for detection),
1 = sub stream (low resolution, used only for cheap liveness probing).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VendorFamily:
    name: str
    # Template variables: user, password, host, port, channel (1-based), stream (0-based)
    template: str
    default_port: int = 554


VENDOR_FAMILIES: tuple[VendorFamily, ...] = (
    # Hikvision and OEM derivatives: channel 1 main = 101, sub = 102; channel 2 = 201...
    VendorFamily(
        name="hikvision",
        template="rtsp://{user}:{password}@{host}:{port}/Streaming/Channels/{channel}0{stream_plus_one}",
    ),
    # Dahua and OEM derivatives.
    VendorFamily(
        name="dahua",
        template="rtsp://{user}:{password}@{host}:{port}/cam/realmonitor?channel={channel}&subtype={stream}",
    ),
    # Uniview via NVR: channel from 1, stream 0=main/1=sub.
    VendorFamily(
        name="uniview_nvr",
        template="rtsp://{user}:{password}@{host}:{port}/unicast/c{channel}/s{stream}/live",
    ),
    # Uniview direct IP camera: video1=main, video2=sub (channel is ignored).
    VendorFamily(
        name="uniview_ipc",
        template="rtsp://{user}:{password}@{host}:{port}/media/video{stream_plus_one}",
    ),
)


def candidate_urls(
    host: str,
    user: str = "admin",
    password: str = "admin",
    channels: int = 4,
    stream: int = 0,
    port: int = 554,
    families: tuple[VendorFamily, ...] = VENDOR_FAMILIES,
) -> list[tuple[str, str, int]]:
    """Generate (family_name, url, channel) candidates to try in order.

    Order matters: Hikvision OEMs are the most common white-label family, so
    they're tried first; within a family, channel 1 first (every recorder has
    a channel 1, so a working family is identified after at most one URL).
    """
    if stream not in (0, 1):
        raise ValueError("stream must be 0 (main) or 1 (sub)")
    if channels < 1:
        raise ValueError("channels must be >= 1")

    out: list[tuple[str, str, int]] = []
    for family in families:
        for channel in range(1, channels + 1):
            url = family.template.format(
                user=user,
                password=password,
                host=host,
                port=port,
                channel=channel,
                stream=stream,
                stream_plus_one=stream + 1,
            )
            out.append((family.name, url, channel))
    return out


def redact(url: str) -> str:
    """Strip credentials from an RTSP URL for logging.

    Never log raw camera URLs: they embed credentials.
    """
    scheme_sep = "://"
    if scheme_sep not in url:
        return url
    scheme, rest = url.split(scheme_sep, 1)
    if "@" not in rest:
        return url
    _creds, host_part = rest.rsplit("@", 1)
    return f"{scheme}{scheme_sep}***:***@{host_part}"
