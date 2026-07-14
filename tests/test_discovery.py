from sentinel.edge.discovery.onvif import build_probe, parse_probe_match
from sentinel.edge.discovery.prober import probe_host

PROBE_MATCH = b"""<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
<SOAP-ENV:Body><d:ProbeMatches><d:ProbeMatch>
<d:XAddrs>http://192.168.1.64/onvif/device_service http://[fe80::1]/onvif/device_service</d:XAddrs>
</d:ProbeMatch></d:ProbeMatches></SOAP-ENV:Body></SOAP-ENV:Envelope>"""


def test_build_probe_is_valid_soap():
    probe = build_probe("test-id")
    assert b"Probe" in probe and b"uuid:test-id" in probe


def test_parse_probe_match_extracts_host():
    device = parse_probe_match(PROBE_MATCH, source="192.168.1.64")
    assert device is not None
    assert device.host == "192.168.1.64"
    assert len(device.xaddrs) == 2


def test_parse_rejects_non_probe_match():
    assert parse_probe_match(b"<html>not soap</html>") is None
    assert parse_probe_match(b"\xff\xfe binary") is None


def _fake_describe_for(family_urls: dict[str, int]):
    def describe(url, host, port):
        for fragment, status in family_urls.items():
            if fragment in url:
                return status
        return 404
    return describe


def test_probe_host_identifies_hikvision_family():
    describe = _fake_describe_for({"/Streaming/Channels/": 200})
    report = probe_host("10.0.0.9", channels=2, describe=describe, check_port=lambda h, p: True)
    assert report.tier == "b"
    assert len(report.endpoints) == 2
    assert all(e.family == "hikvision" for e in report.endpoints)
    # Family locked in: dahua/uniview URLs must not have been attempted after the match.
    assert report.attempts <= 4


def test_probe_host_auth_required_still_identifies_family():
    describe = _fake_describe_for({"realmonitor": 401})
    report = probe_host("10.0.0.9", channels=1, describe=describe, check_port=lambda h, p: True)
    assert [e.status for e in report.endpoints] == ["auth_required"]
    assert report.endpoints[0].family == "dahua"


def test_probe_host_closed_port_is_tier_c_candidate():
    report = probe_host("10.0.0.9", describe=lambda *a: 200, check_port=lambda h, p: False)
    assert report.endpoints == []
    assert report.tier == "c_candidate"
    assert report.attempts == 0


def test_probe_host_nothing_matches():
    report = probe_host(
        "10.0.0.9", channels=2, describe=lambda *a: 404, check_port=lambda h, p: True
    )
    assert report.endpoints == []
    assert report.tier == "c_candidate"


def test_endpoint_urls_redacted_in_report():
    describe = _fake_describe_for({"/Streaming/Channels/": 200})
    report = probe_host(
        "10.0.0.9", user="admin", password="s3cret", channels=1,
        describe=describe, check_port=lambda h, p: True,
    )
    assert "s3cret" not in report.endpoints[0].redacted_url
