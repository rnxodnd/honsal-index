"""배포 화면에서 호출할 API 전용 서버. UI와 CSV 원본 파일은 제공하지 않습니다.

실행: python -m uvicorn src.public_api:app --host 127.0.0.1 --port 8001
허용할 화면 주소는 HONSAL_ALLOWED_ORIGINS에 쉼표로 구분합니다.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from starlette.middleware.cors import CORSMiddleware

from src.api import PROJECT_DIR, create_app


DEFAULT_FRONTEND_ORIGIN = "https://unique-dusk-66f82f.netlify.app"


def validate_origins(origins) -> list[str]:
    """와일드카드나 페이지 URL 대신 정확한 HTTP(S) 출처만 허용합니다."""
    if not isinstance(origins, (list, tuple)):
        raise ValueError("허용 출처는 HTTP(S) origin 문자열 목록이어야 합니다.")
    result = []
    for origin in origins:
        if (not isinstance(origin, str) or not origin
                or any(character.isspace() for character in origin)
                or "*" in origin or "\\" in origin):
            raise ValueError("허용 출처에 빈 값·공백·와일드카드를 사용할 수 없습니다.")
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as error:
            raise ValueError(f"잘못된 허용 출처입니다: {origin}") from error
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment
                or "?" in origin or "#" in origin):
            raise ValueError("허용 출처는 경로·쿼리·계정 정보 없는 http(s)://호스트[:포트]여야 합니다.")
        hostname = parsed.hostname.lower()
        if any(character in hostname for character in ('%', '<', '>', '"', "'")):
            raise ValueError("허용 출처의 호스트가 올바르지 않습니다.")
        if ":" in hostname:  # IPv6 host는 URL 형식의 대괄호를 유지합니다.
            hostname = f"[{hostname}]"
        normalized = f"{parsed.scheme}://{hostname}"
        if port is not None and port != {"http": 80, "https": 443}[parsed.scheme]:
            normalized += f":{port}"
        if normalized not in result:
            result.append(normalized)
    return result


def create_public_app(engine=None, allowed_origins=None, project_dir: Path = PROJECT_DIR):
    if allowed_origins is None:
        configured = os.getenv("HONSAL_ALLOWED_ORIGINS")
        allowed_origins = ([DEFAULT_FRONTEND_ORIGIN] if configured is None
                           else [value.strip() for value in configured.split(",")])
    origins = validate_origins(allowed_origins)
    # 오류 처리 계층 바깥을 감싸 400·422·503·500 응답에도 CORS를 적용합니다.
    return CORSMiddleware(
        create_app(engine=engine, project_dir=project_dir, serve_ui=False),
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
        max_age=600,
    )


app = create_public_app()
