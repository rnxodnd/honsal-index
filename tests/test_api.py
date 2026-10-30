"""네트워크·추가 테스트 패키지 없이 실제 ASGI 요청 경계를 검증합니다."""

import json
import unittest

from src.api import MAX_BODY_BYTES, create_app
from src.scoring.accessibility import AnalysisError


class FixtureEngine:
    """HTTP 계약 검증용 엔진. 실제 거리 계산은 test_accessibility에서 검증합니다."""

    def options(self):
        return {"categories": [], "dataset": {"facility_count": 2, "grid_count": 1}}

    def analyze(self, lon, lat, selected, name=None):
        if not selected:
            raise AnalysisError("invalid_selection", "분석할 시설을 하나 이상 선택하세요.")
        return {"location": {"lon": lon, "lat": lat, "name": name}, "total_score": 80.0, "selected": selected}


async def request(app, path, method="GET", body=b"", content_type="application/json", split=False):
    """ASGI 앱을 HTTP scope로 호출하며 chunked 요청도 검증합니다."""
    messages = []
    chunks = [body[:len(body) // 2], body[len(body) // 2:]] if split else [body]

    async def receive():
        if chunks:
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"content-type", content_type.encode())],
        "client": ("127.0.0.1", 12345), "server": ("localhost", 8000),
    }, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    raw = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], raw


class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = create_app(FixtureEngine())
        self.payload = {"lon": 127.7298, "lat": 37.8813, "selected": {"leisure_community": ["당구장", "볼링장"]}}

    async def post(self, payload, **kwargs):
        return await request(self.app, "/api/analyze", "POST", json.dumps(payload, ensure_ascii=False).encode(), **kwargs)

    async def test_valid_request_reaches_engine_and_returns_utf8_json(self):
        status, body = await self.post(self.payload, split=True)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["selected"], self.payload["selected"])
        self.assertEqual(result["location"]["lon"], self.payload["lon"])

    async def test_invalid_body_and_non_json_numbers(self):
        for body in (b"", b"{", b'{"lon":NaN}', b'{"lat":Infinity}', b"\xff"):
            with self.subTest(body=body):
                status, raw = await request(self.app, "/api/analyze", "POST", body)
                self.assertEqual(status, 400)
                self.assertEqual(json.loads(raw)["error"]["code"], "invalid_json")

    async def test_request_fields_and_name_are_validated(self):
        cases = [([], "invalid_request"), ({}, "missing_fields"),
                 ({**self.payload, "weights": {}}, "unknown_fields"),
                 ({**self.payload, "name": 12}, "invalid_name"),
                 ({**self.payload, "name": "가" * 201}, "invalid_name")]
        for payload, code in cases:
            with self.subTest(code=code):
                status, raw = await self.post(payload)
                self.assertEqual(status, 422)
                self.assertEqual(json.loads(raw)["error"]["code"], code)

    async def test_engine_validation_error_has_clear_json(self):
        status, raw = await self.post({**self.payload, "selected": {}})
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(raw)["error"]["code"], "invalid_selection")

    async def test_wrong_content_type_and_chunked_oversized_body(self):
        status, _ = await self.post(self.payload, content_type="text/plain")
        self.assertEqual(status, 415)
        status, raw = await request(self.app, "/api/analyze", "POST", b" " * (MAX_BODY_BYTES + 1), split=True)
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(raw)["error"]["code"], "request_too_large")

    async def test_no_data_is_unavailable_not_a_zero_score(self):
        self.app.state.engine = None
        for path, method in (("/api/health", "GET"), ("/api/options", "GET"), ("/api/analyze", "POST")):
            with self.subTest(path=path):
                status, raw = await request(self.app, path, method)
                self.assertEqual(status, 503)
                self.assertEqual(json.loads(raw)["error"]["code"], "data_unavailable")

    async def test_api_errors_and_static_assets_are_routed_separately(self):
        for path, expected in (("/api/analyze", 405), ("/api/unknown", 404)):
            status, body = await request(self.app, path)
            self.assertEqual(status, expected)
            self.assertIn("error", json.loads(body))
        for path in ("/", "/js/map.js", "/css/style.css"):
            status, body = await request(self.app, path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 0)
        # 정제 원본과 설정 파일은 정적 웹 루트에 노출하지 않습니다.
        status, _ = await request(self.app, "/data/processed/chuncheon_facilities_classified.csv")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
