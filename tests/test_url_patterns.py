from sentinel.edge.discovery.url_patterns import VENDOR_FAMILIES, candidate_urls, redact


def test_hikvision_channel_encoding():
    urls = candidate_urls("10.0.0.5", user="u", password="p", channels=2)
    hik = [u for f, u, _ in urls if f == "hikvision"]
    assert "rtsp://u:p@10.0.0.5:554/Streaming/Channels/101" in hik
    assert "rtsp://u:p@10.0.0.5:554/Streaming/Channels/201" in hik


def test_hikvision_substream_encoding():
    urls = candidate_urls("10.0.0.5", user="u", password="p", channels=1, stream=1)
    hik = [u for f, u, _ in urls if f == "hikvision"]
    assert hik == ["rtsp://u:p@10.0.0.5:554/Streaming/Channels/102"]


def test_dahua_pattern():
    urls = candidate_urls("10.0.0.5", user="u", password="p", channels=1)
    dahua = [u for f, u, _ in urls if f == "dahua"]
    assert dahua == ["rtsp://u:p@10.0.0.5:554/cam/realmonitor?channel=1&subtype=0"]


def test_uniview_patterns():
    urls = candidate_urls("h", user="u", password="p", channels=1)
    by_family = {f: u for f, u, _ in urls}
    assert by_family["uniview_nvr"] == "rtsp://u:p@h:554/unicast/c1/s0/live"
    assert by_family["uniview_ipc"] == "rtsp://u:p@h:554/media/video1"


def test_order_hikvision_first():
    urls = candidate_urls("h", channels=2)
    assert urls[0][0] == "hikvision"
    assert urls[0][2] == 1  # channel 1 before channel 2


def test_all_families_covered():
    urls = candidate_urls("h", channels=1)
    assert {f for f, _, _ in urls} == {f.name for f in VENDOR_FAMILIES}


def test_invalid_args_rejected():
    import pytest

    with pytest.raises(ValueError):
        candidate_urls("h", stream=2)
    with pytest.raises(ValueError):
        candidate_urls("h", channels=0)


def test_redact_strips_credentials():
    url = "rtsp://admin:hunter2@10.0.0.5:554/Streaming/Channels/101"
    r = redact(url)
    assert "hunter2" not in r and "admin" not in r
    assert r.endswith("10.0.0.5:554/Streaming/Channels/101")


def test_redact_no_credentials_passthrough():
    assert redact("rtsp://10.0.0.5/x") == "rtsp://10.0.0.5/x"
