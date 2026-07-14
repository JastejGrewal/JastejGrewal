"""Alert/event publishers: how the edge box talks to the cloud.

Webhook (HTTP POST to the cloud API) is the Phase 1 default; stdout is for
demos and debugging; MQTT is the production-fleet path (import-guarded).
All publishers return bool so the Outbox can decide durability.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from sentinel.common.events import DetectionEvent


class StdoutPublisher:
    def publish(self, event: DetectionEvent) -> bool:
        print(f"[{event.tier.upper():5}] cam={event.camera_id} track={event.track_id} "
              f"score={event.fused_score:.2f} flags={','.join(event.rule_flags) or '-'}")
        return True


class WebhookPublisher:
    """POSTs events to the cloud API (`/api/v1/events`; alerts route server-side)."""

    def __init__(self, cloud_url: str, timeout_s: float = 5.0, transport=None):
        self.endpoint = cloud_url.rstrip("/") + "/api/v1/events"
        self.timeout_s = timeout_s
        # Injectable transport for tests: callable (url, body_bytes) -> status_code.
        self._transport = transport or self._http_post

    def _http_post(self, url: str, body: bytes) -> int:
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            return response.status

    def publish(self, event: DetectionEvent) -> bool:
        body = json.dumps(event.to_dict()).encode()
        try:
            status = self._transport(self.endpoint, body)
        except (urllib.error.URLError, OSError):
            return False
        return 200 <= status < 300


class MqttPublisher:
    """Fleet-scale publisher (optional; requires `pip install ".[mqtt]"`)."""

    def __init__(self, broker_host: str, store_id: str, port: int = 1883):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as e:
            raise RuntimeError("MqttPublisher requires the mqtt extra: pip install '.[mqtt]'") from e
        self._topic = f"sentinel/{store_id}/events"
        self._client = mqtt.Client()
        self._client.connect(broker_host, port)
        self._client.loop_start()

    def publish(self, event: DetectionEvent) -> bool:
        info = self._client.publish(self._topic, json.dumps(event.to_dict()), qos=1)
        return info.rc == 0
