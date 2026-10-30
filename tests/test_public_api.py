"""허용된 배포 화면의 교차 출처 호출과 API 전용 제공 범위를 검증합니다."""

import json
import os
import unittest
from unittest.mock import patch

from src.public_api import DEFAULT_FRONTEND_ORIGIN, create_public_app, validate_origins
from src.scoring.accessibility import AnalysisError


class FixtureEngine:
    def options(self):
        return {"categories": [], "dataset": {"facility_count": 2, "grid_count": 1}}

    def analyze(self, lon, lat, selected, name=None):
        if not selected:
            raise AnalysisError("invalid_selection", "시설을 하나 이상 선택하세요.")
        return {"total_score": 80.0, "selected": selected}


async def request(app, path, method="GET", body=b"", origin=DEFAULT_FRONTEND_ORIGIN, headers=(), expected_error=None):
    messages = []
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    request_headers = [(b"content-type", b"application/json"), *headers]
    if origin is not None:
        request_headers.append((b"origin", origin.encode()))
    try:
        await app({
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": method, "scheme": "https", "path": path,
            "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": request_headers, "client": ("127.0.0.1", 12345),
            "server": ("api.example.com", 443),
        }, receive, send)
    except Exception as error:
        # ServerErrorMiddleware는 응답을 전송한 뒤 서버 로그용으로 예외를 다시 던집니다.
        if expected_error is None or not isinstance(error, expected_error):
            raise
    start = next(message for message in messages if message["type"] == "http.response.start")
    raw = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], {k.decode(): v.decode() for k, v in start["headers"]}, raw


class PublicApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = create_public_app(FixtureEngine(), [DEFAULT_FRONTEND_ORIGIN])
        self.payload = json.dumps({"lon": 127.7298, "lat": 37.8813, "selected": {"leisure_community": ["당구장"]}}).encode()

    async def test_allowed_origin_preflight_then_post_and_health(self):
        status, headers, _ = await request(self.app, "/api/analyze", "OPTIONS", headers=[
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ])
        self.assertEqual(status, 200)
        self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)
        self.assertIn("POST", headers["access-control-allow-methods"])
        self.assertNotIn("access-control-allow-credentials", headers)
        for path, method, body in (("/api/analyze", "POST", self.payload), ("/api/health", "GET", b""), ("/api/options", "GET", b"")):
            with self.subTest(path=path):
                status, headers, raw = await request(self.app, path, method, body)
                self.assertEqual(status, 200)
                self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)
                self.assertIn("Origin", headers["vary"])
                self.assertIsInstance(json.loads(raw), dict)

    async def test_unlisted_origin_cannot_read_cross_origin_response(self):
        origin = "https://unlisted.example"
        status, headers, _ = await request(self.app, "/api/analyze", "OPTIONS", origin=origin, headers=[
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ])
        self.assertEqual(status, 400)
        self.assertNotIn("access-control-allow-origin", headers)
        _, headers, _ = await request(self.app, "/api/health", origin=origin)
        self.assertNotIn("access-control-allow-origin", headers)
        # CORS는 브라우저의 응답 읽기 규칙이며 인증·비브라우저 접근 차단이 아닙니다.
        status, headers, _ = await request(self.app, "/api/health", origin=None)
        self.assertEqual(status, 200)
        self.assertNotIn("access-control-allow-origin", headers)

    async def test_ui_assets_and_raw_data_are_not_served(self):
        for path in ("/", "/index.html", "/js/map.js", "/css/style.css", "/data/processed/chuncheon_facilities_classified.csv", "/config/weights.json"):
            with self.subTest(path=path):
                status, headers, raw = await request(self.app, path)
                self.assertEqual(status, 404)
                self.assertIn("error", json.loads(raw))
                self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)

    async def test_validation_and_unavailable_errors_keep_cors_headers(self):
        for body, expected in ((b"{", 400), (b"{}", 422)):
            status, headers, raw = await request(self.app, "/api/analyze", "POST", body)
            self.assertEqual(status, expected)
            self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)
            self.assertIn("error", json.loads(raw))
        self.app.app.state.engine = None
        status, headers, _ = await request(self.app, "/api/health")
        self.assertEqual(status, 503)
        self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)

    async def test_unexpected_server_error_also_keeps_cors_headers(self):
        with patch.object(self.app.app.state.engine, "analyze", side_effect=RuntimeError("fixture failure")):
            with self.assertLogs("src.api", level="ERROR"):
                status, headers, raw = await request(self.app, "/api/analyze", "POST", self.payload, expected_error=RuntimeError)
        self.assertEqual(status, 500)
        self.assertEqual(headers["access-control-allow-origin"], DEFAULT_FRONTEND_ORIGIN)
        self.assertEqual(json.loads(raw)["error"]["code"], "internal_error")

    async def test_unallowed_method_or_header_fails_preflight(self):
        for method, header in ((b"DELETE", b"content-type"), (b"POST", b"authorization")):
            status, _, _ = await request(self.app, "/api/analyze", "OPTIONS", headers=[
                (b"access-control-request-method", method), (b"access-control-request-headers", header),
            ])
            self.assertEqual(status, 400)

    def test_origin_configuration_rejects_patterns_and_page_urls(self):
        for origin in ("*", "https://*.netlify.app", "https://example.com/", "https://example.com/path", "https://example.com?x=1", "https://example.com#part", "https://user@example.com", "file:///tmp/test", "null", "", "https://example.com:99999", "https://example.com\\path"):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    validate_origins([origin])
        with self.assertRaises(ValueError):
            validate_origins(DEFAULT_FRONTEND_ORIGIN)
        self.assertEqual(validate_origins(["https://EXAMPLE.com:443", "https://example.com"]), ["https://example.com"])
        self.assertEqual(validate_origins(["http://127.0.0.1:5500", "http://[::1]:5500"]), ["http://127.0.0.1:5500", "http://[::1]:5500"])

    def test_environment_origin_override_is_explicit_and_validated(self):
        with patch.dict(os.environ, {"HONSAL_ALLOWED_ORIGINS": "https://example.com, http://127.0.0.1:5500"}):
            self.assertEqual(create_public_app(FixtureEngine()).allow_origins, ["https://example.com", "http://127.0.0.1:5500"])
        with patch.dict(os.environ, {"HONSAL_ALLOWED_ORIGINS": "*"}):
            with self.assertRaises(ValueError):
                create_public_app(FixtureEngine())


if __name__ == "__main__":
    unittest.main()
