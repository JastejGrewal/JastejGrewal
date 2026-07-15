"""Edge model sync: pull the production action model from the cloud (OTA).

The final arrow in the architecture diagram (§4.6): Model Registry -> OTA push
-> back to the edge box. The edge polls the cloud's production-model endpoint;
when the version differs from the local cache it downloads the ONNX, verifies
it loads, and only then swaps it in — a failed download or corrupt artifact
leaves the current model serving (same fail-safe posture as the outbox).

Offline behavior: on any network error the edge keeps its cached model. A box
that has never synced falls back to whatever classifier it was constructed
with (the kinematic stand-in by default), so detection never depends on the
cloud being reachable.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


class ModelSync:
    def __init__(self, cloud_url: str, cache_dir: str, timeout_s: float = 10.0, transport=None):
        self.info_url = cloud_url.rstrip("/") + "/api/v1/models/production"
        self.artifact_url = self.info_url + "/artifact"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        # Injectable for tests: callable (url) -> bytes; raises on failure.
        self._fetch = transport or self._http_get
        self._meta_path = self.cache_dir / "current.json"

    def _http_get(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
            return response.read()

    def current_version(self) -> str | None:
        if self._meta_path.exists():
            return json.loads(self._meta_path.read_text()).get("version")
        return None

    def current_model_path(self) -> str | None:
        if self._meta_path.exists():
            path = json.loads(self._meta_path.read_text()).get("path")
            if path and Path(path).exists():
                return path
        return None

    def sync(self) -> tuple[str, str] | None:
        """Check the cloud; download + swap if a new version is in production.

        Returns (version, path) after a successful swap, or None if unchanged /
        unreachable / invalid — in all None cases the existing model stays live.
        """
        try:
            info = json.loads(self._fetch(self.info_url))
        except (urllib.error.URLError, OSError, ValueError):
            return None
        version = info.get("version")
        if not version or version == self.current_version():
            return None

        try:
            artifact = self._fetch(self.artifact_url)
        except (urllib.error.URLError, OSError):
            return None

        candidate_path = self.cache_dir / f"{version}.onnx"
        candidate_path.write_bytes(artifact)

        # Verify the artifact actually loads before pointing anything at it.
        try:
            import onnxruntime as ort

            ort.InferenceSession(str(candidate_path), providers=["CPUExecutionProvider"])
        except Exception:
            candidate_path.unlink(missing_ok=True)
            return None

        self._meta_path.write_text(
            json.dumps({"version": version, "path": str(candidate_path)})
        )
        return version, str(candidate_path)

    def build_classifier(self, window_size: int):
        """OnnxActionClassifier for the cached production model, or None."""
        path = self.current_model_path()
        if not path:
            return None
        from sentinel.ml.onnx_classifier import OnnxActionClassifier

        return OnnxActionClassifier(path, window_size=window_size)
