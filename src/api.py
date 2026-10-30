"""춘천 시설 선택·격자 접근성 API와 기존 HTML 화면을 같은 서버에서 제공합니다.

프로젝트 루트에서 실행: .venv/bin/python -m uvicorn src.api:app --host 127.0.0.1 --port 5500 --reload
"""

from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from src.scoring.accessibility import AccessibilityEngine, AnalysisError


PROJECT_DIR = Path(__file__).resolve().parents[1]
MAX_BODY_BYTES = 32 * 1024
logger = logging.getLogger(__name__)


def error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def get_engine(request):
    return getattr(request.app.state, "engine", None)


def unavailable():
    return error_response(
        "data_unavailable", "분석 자료를 읽지 못했습니다. 서버의 데이터 경로와 실행 로그를 확인하세요.", 503,
    )


async def health(request):
    engine = get_engine(request)
    if engine is None:
        return unavailable()
    return JSONResponse({"status": "ok", "dataset": engine.options()["dataset"]})


async def options(request):
    engine = get_engine(request)
    if engine is None:
        return unavailable()
    return JSONResponse(engine.options())


def reject_non_json_number(value):
    raise ValueError(f"JSON에 사용할 수 없는 숫자입니다: {value}")


async def analyze(request):
    engine = get_engine(request)
    if engine is None:
        return unavailable()
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return error_response("invalid_content_type", "Content-Type을 application/json으로 지정하세요.", 415)
    # stream으로 읽어 Content-Length가 없는 요청에도 크기 제한을 적용합니다.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            return error_response("request_too_large", "분석 요청은 32KB 이하여야 합니다.", 413)
    try:
        payload = json.loads(body, parse_constant=reject_non_json_number)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return error_response("invalid_json", "올바른 JSON 객체를 보내세요. NaN과 Infinity는 사용할 수 없습니다.", 400)
    if not isinstance(payload, dict):
        return error_response("invalid_request", "요청 본문은 JSON 객체여야 합니다.", 422)
    if not {"lon", "lat", "selected"}.issubset(payload):
        return error_response("missing_fields", "lon, lat, selected를 모두 입력하세요.", 422)
    if set(payload) - {"lon", "lat", "selected", "name"}:
        return error_response("unknown_fields", "사용할 수 있는 필드는 lon, lat, selected, name입니다.", 422)
    name = payload.get("name")
    if name is not None and (not isinstance(name, str) or len(name) > 200):
        return error_response("invalid_name", "위치 이름은 200자 이하의 문자열이어야 합니다.", 422)
    try:
        result = await run_in_threadpool(
            engine.analyze, lon=payload["lon"], lat=payload["lat"],
            selected=payload["selected"], name=name,
        )
    except AnalysisError as exc:
        return error_response(exc.code, str(exc), 422)
    return JSONResponse(result)


async def http_error(request, exc):
    if request.url.path.startswith("/api/"):
        messages = {404: "요청한 API가 없습니다.", 405: "이 API에서 지원하지 않는 HTTP 메서드입니다."}
        response = error_response(f"http_{exc.status_code}", messages.get(exc.status_code, str(exc.detail)), exc.status_code)
        if exc.headers:
            response.headers.update(exc.headers)
        return response
    return JSONResponse({"error": {"code": "not_found", "message": "요청한 파일이 없습니다."}}, status_code=exc.status_code)


async def internal_error(request, exc):
    logger.error("분석 서버 처리 오류", exc_info=(type(exc), exc, exc.__traceback__))
    return error_response("internal_error", "분석 중 오류가 발생했습니다. 서버 로그를 확인하세요.", 500)


def create_app(engine=None, project_dir: Path = PROJECT_DIR, *, serve_ui: bool = True) -> Starlette:
    """테스트에서는 준비한 엔진을 주입할 수 있습니다. 원본 자료는 시작 시 한 번 읽습니다."""
    project_dir = Path(project_dir)

    @asynccontextmanager
    async def lifespan(application):
        if engine is None:
            try:
                application.state.engine = await run_in_threadpool(AccessibilityEngine.from_project, project_dir)
            except Exception:
                # 미확보·잘못된 자료로 정상 점수(특히 0점)를 반환하지 않습니다.
                logger.exception("시설·격자·경계·가중치 자료를 불러오지 못했습니다.")
                application.state.engine = None
        yield

    routes = [
        Mount("/api", routes=[
            Route("/health", health, methods=["GET"]),
            Route("/options", options, methods=["GET"]),
            Route("/analyze", analyze, methods=["POST"]),
        ]),
    ]
    if serve_ui:
        async def ui_data(request):
            # 정적 미리보기와 API 실행 모두 동일한 정제 자료를 사용합니다.
            filename = request.path_params["filename"]
            inputs = {
                name: project_dir / "data" / "processed" / name
                for name in ("grid_500m_bounds.csv", "chuncheon_medical_facilities.csv", "chuncheon_hospitals.csv")
            }
            # 노선 JSON은 팀원이 확보한 경우에만 제공합니다. 미확보를 빈 노선으로 만들지 않습니다.
            inputs["chuncheon_bus.json"] = project_dir / "app" / "data" / "chuncheon_bus.json"
            path = inputs.get(filename)
            if path is None or not path.is_file():
                raise HTTPException(404)
            media_type = "application/json" if path.suffix == ".json" else "text/csv; charset=utf-8"
            return FileResponse(path, media_type=media_type)

        routes.append(Route("/data/{filename}", ui_data, methods=["GET"]))
        routes.append(Mount("/", app=StaticFiles(directory=project_dir / "app", html=True)))
    application = Starlette(
        routes=routes,
        lifespan=lifespan,
        exception_handlers={HTTPException: http_error, Exception: internal_error},
    )
    application.state.engine = engine
    return application


app = create_app()
