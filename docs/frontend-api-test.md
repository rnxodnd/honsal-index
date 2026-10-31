# 기존 UI에서 실제 점수와 시설 목록 테스트하기

`codex/ui-facility-results`에서 기존 디자인을 유지하면서 점수 API를 화면에 연결해 검증했습니다. **시설을 선택하면 점수·개수·상호명 목록이 자동으로 갱신됩니다.** 개발자 도구 콘솔에 코드를 붙여넣을 필요는 없습니다. 현재 소스에는 백엔드 API와 UI 연결이 함께 포함되어 있습니다. 기존 Netlify 사이트에서 시험하려면 최신 UI 파일을 별도로 배포합니다.

## 최신 팀원 UI와 통합 경로

팀원 브랜치 `codex/frontend-upoad-1030`의 `a53320a`를 통합했습니다. UI 기준 경로는 **`app/index.html`, `app/css/`, `app/js/`, `app/data/`**입니다. 이전 `app/app/`은 제거하고 루트 `index.html`은 최신 화면으로 이동하는 링크로 정리했습니다. 백엔드도 `app/`을 화면 루트로 사용합니다.

- 최신 버스 노선 화면·상단 점수 카드 배치를 유지하고 점수 API를 연결했습니다.
- 교통의 분석 시설 선택과 버스 노선 지도 표시 토글은 별도입니다.
- 버스정류장 위치는 정제 자료 1,890개를 이용해 점수와 시설 목록을 표시합니다.
- **버스 노선 번호·정류장 순서 자료 `app/data/chuncheon_bus.json`은 아직 미확보**입니다(팀 확인). 노선 화면은 자료 미연결을 표시하며, 이를 경유 버스 0개로 해석하지 않습니다. 해당 파일을 확보해 추가하면 기존 노선 화면에서 불러올 수 있습니다.
- `app/data/`의 의료·격자 CSV는 `data/processed/`의 최신 정제본과 같습니다. 격자 인구·가구 미확보 값은 빈칸을 유지합니다. 정제 자료 변경 시 이 UI용 사본도 함께 갱신합니다.
- 폴더만 Live Server로 열면 화면·지도는 확인할 수 있지만 점수 API는 실행되지 않습니다. 전체 기능은 아래 Python 서버로 실행합니다.

## 1. 로컬 UI 실행

테스트 브랜치 작업 폴더에서 Python 3.12 가상환경에 `requirements.txt`를 설치한 뒤 실행합니다.

```bash
.venv/bin/python -m uvicorn src.api:app --host 127.0.0.1 --port 5500 --reload
```

현재 개발 PC의 별도 작업 폴더 `honsal-index-api-test`에서 기존 가상환경을 사용한다면 다음과 같이 실행합니다.

```bash
../honsal-index/.venv/bin/python -m uvicorn src.api:app --host 127.0.0.1 --port 5500 --reload
```

Windows에서는 `.venv/bin/python`을 `.\.venv\Scripts\python.exe`로 바꿉니다. 다른 팀원은 자기 PC에 Python 3.12 가상환경을 생성합니다.

브라우저에서 <http://127.0.0.1:5500>을 엽니다. <http://127.0.0.1:5500/api/health>는 API 상태 확인 주소이며, 정상이라면 `status: "ok"`, 시설 5,252개·후보 격자 2,526개를 반환합니다. [기존 Netlify 주소](https://unique-dusk-66f82f.netlify.app/)에는 마지막으로 업로드한 파일이 표시되므로 Git pull 후에도 별도 배포가 필요합니다.

지도·주소 검색은 카카오 JavaScript 키에 등록한 도메인 설정에 따릅니다. 지도 SDK 로딩이 실패해도 기본 위치의 API 분석을 확인할 수 있습니다.

## 2. 화면에서 확인할 순서

1. 처음에는 시설이 미선택 상태이며 점수·개수 대신 선택 안내가 표시됩니다.
2. 기본 위치인 춘천시청 인근(`127.7298`, `37.8813`)에서 여가시설의 **당구장·볼링장**만 선택합니다.
3. 현재 자료·산식 기준 종합점수 **67.8점**, 여가시설 **12곳**이 표시되는지 확인합니다. 여가만 선택했으므로 적용 비중은 100%입니다.
4. 여가시설 목록에서 12개의 **상호명**과 업종·격자 중심 직선거리·주소·전화번호 안내를 확인합니다. 같은 상호명·업종·좌표라도 시설 ID가 다르면 각각 표시합니다.
5. 위치나 시설 선택을 바꾸면 이전 결과가 지워진 뒤 새 결과로 바뀌는지 확인합니다. 교통도 버스 정류장·전철/기차역 두 종류를 선택할 수 있습니다.
6. 모든 시설 선택을 해제하면 점수·개수·목록·분석 마커가 지워지고 선택 안내로 돌아가는지 확인합니다.
7. 같은 시설 선택으로 한 위치의 분석 결과를 비교에 추가하고, 다른 격자의 위치를 골라 두 번째 결과를 추가합니다. 실제 응답의 점수·개수로 비교하며, 같은 격자는 중복 추가하지 않습니다. 시설 선택을 바꾸면 비교 결과를 초기화합니다.

주변 3×3 격자의 선택 시설은 전부 표시하며 15개 제한을 적용하지 않습니다. 같은 좌표의 시설은 지도에서 개수 마커로 묶고 팝업에 개별 상호명을 모두 보여줍니다. 별도로 제공하는 카카오 주변 검색의 1km·최대 15개 결과는 팀 데이터의 3×3 분석 목록과 범위가 다릅니다.

API 오류가 발생하면 이전 점수를 남기지 않고 오류 안내와 다시 분석 버튼을 표시합니다. 시설 수를 늘려 점수를 더하는 방식은 아니며, 점수는 유형별 최근접 직선거리와 기존 가중치로 계산합니다. [산식과 오류 응답](api.md)을 참고합니다.

## 3. 프론트엔드 연결 구조

`app/js/analysis.js`는 `/api/options`에서 네 항목·40종 선택지를 만들고 `/api/analyze`로 현재 위치와 선택을 전송합니다. 기본 API 주소는 UI와 같은 서버입니다. UI의 편의시설은 API의 `daily_life`, 의료는 `healthcare`, 교통은 `transport`, 여가는 `leisure_community`에 대응합니다.

| 화면 영역 | 응답 필드·표시 방법 |
| --- | --- |
| 종합점수 `#analysisScore` | `total_score` |
| 항목별 점수 | `categories[].score`, 적용 비중 `weight` |
| 네 항목의 시설 개수 | `facilities`를 `category`별로 집계 |
| `#facilityList`, `#leisureList`, `#healthcareList`, `#transportList` | 전체 `facilities`에서 항목별 시설 카드 생성 |
| 시설 카드 `data-facility-id` | `facility_id`로 개별 시설 구분, `name`을 **상호명**으로 표시 |
| 지도 격자·시설 | `neighborhood` 경계와 전체 `facilities` 좌표 |
| 유형별 계산 근거 | `types`의 점수·개수. `nearest`는 점수 계산 근거이며 전체 목록을 대체하지 않음 |
| 두 위치 비교 | 동일한 선택 기준으로 받은 분석 응답 스냅샷 |

위치 이벤트는 `honsal:selection`, 선택 변경은 `honsal:filters-changed`, 분석 상태 전달은 `honsal:analysis`를 사용합니다. 이전 요청은 취소하고 요청 순서를 검사해 새 선택에 옛 결과가 덮이지 않도록 처리합니다.

## 4. 선택 사항: API만 외부에 연결하기

로컬 UI 테스트에는 터널이 필요 없습니다. 다른 컴퓨터나 정적 HTTPS 사이트에서 백엔드를 시험할 때만 API 전용 서버와 임시 HTTPS 주소를 사용할 수 있습니다.

```bash
.venv/bin/python -m uvicorn src.public_api:app --host 127.0.0.1 --port 8001
```

별도 터미널에서 설치된 `cloudflared`를 실행합니다.

```bash
cloudflared tunnel --url http://127.0.0.1:8001 --protocol http2 --no-autoupdate
```

터미널에 나온 `https://…trycloudflare.com` 주소를 HTTPS API의 기본 주소로 사용합니다. 상태는 이 주소 뒤에 `/api/health`를 붙여 확인합니다. UI의 `analysis.js`를 불러오기 전에 다음 값을 설정하면 같은 서버 대신 이 주소로 요청합니다.

```html
<script>
  window.HONSAL_API_BASE_URL = 'BACKEND_URL';
</script>
```

`BACKEND_URL`은 실행 중인 HTTPS API 주소로 바꿉니다. 이 설정과 UI 연결 코드를 정적 호스팅에 실제 배포해야 해당 사이트에서 자동 연동됩니다. Netlify의 기존 화면은 자동으로 바뀌지 않습니다.

Quick Tunnel은 테스트용 임시 주소이며 재실행하면 주소가 바뀌고 가동 시간을 보장하지 않습니다. PC·API 서버·터널이 모두 실행 중이어야 합니다. 이 테스트 브랜치에는 기존 Netlify 사이트의 수동 배포 확인용 주소를 저장했으며, 고정 운영 주소가 아닙니다. 터널 주소가 바뀌면 설정을 갱신하고 다시 배포합니다. [Cloudflare 공식 안내](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

API 전용 서버의 기본 CORS 허용 출처는 `https://unique-dusk-66f82f.netlify.app`입니다. 다른 화면의 출처는 `HONSAL_ALLOWED_ORIGINS` 환경변수에 정확한 `http(s)://호스트[:포트]` 형식으로 쉼표를 구분해 지정합니다. CORS는 인증 기능이 아닙니다. API 전용 서버는 UI·CSV 경로를 제공하지 않습니다. 로컬 UI 서버만 지도용 `/data/grid_500m_bounds.csv`와 `/data/chuncheon_medical_facilities.csv`를 제공합니다.

## Netlify에 점수 API를 연결하는 방법

팀원은 Python 서버를 따로 실행하지 않아도 됩니다. API 담당자가 실행 중인 HTTPS 주소를 공유하고, 해당 API의 `HONSAL_ALLOWED_ORIGINS`에 Netlify 사이트 출처를 등록합니다. 현재 기존 사이트 `https://unique-dusk-66f82f.netlify.app`는 기본 허용 출처입니다.

### 현재 테스트 브랜치를 pull한 뒤 직접 업로드

2026-10-31 11:22(KST)에 재생성된 공개 API 주소는 `https://villages-don-clips-archived.trycloudflare.com`입니다. 추적되는 `app/js/runtime-config.js`에 이 주소를 넣어 **기존 `https://unique-dusk-66f82f.netlify.app`에서만** 기본값으로 사용합니다. 로컬에서는 같은 서버의 API를 쓰고, 별도로 지정한 `window.HONSAL_API_BASE_URL`은 우선 적용합니다.

이번 연결 복구 브랜치는 `codex/reconnect-netlify-api`입니다. 팀원은 VS Code의 프로젝트 터미널에서 다음 명령으로 받습니다. 앞 단계가 성공했을 때만 다음 단계를 실행합니다.

```powershell
git fetch origin
if ($LASTEXITCODE -eq 0) {
    git switch codex/reconnect-netlify-api
    if ($LASTEXITCODE -eq 0) {
        git pull --ff-only origin codex/reconnect-netlify-api
    }
}
```

Netlify 기존 프로젝트의 **Deploys → 수동 업로드 영역**에 최신 `app` 폴더를 올린 뒤 `Ctrl + Shift + R`로 새로고침합니다. `app/index.html`과 `css`, `js`, `data`가 함께 포함되어야 합니다. 이 테스트 방법은 빌드 없이도 API 주소가 적용됩니다. Git pull은 Netlify 사이트를 자동 갱신하지 않으며, 이전에 만든 `app/dist`도 갱신하지 않습니다. 예전 `dist`를 재사용하려면 아래 빌드부터 다시 실행해야 합니다.

시설 항목이 비어 있으면 배포된 `/js/runtime-config.js`의 API 주소와 공개 API의 `/api/health` 응답을 확인합니다. Netlify의 환경변수는 수동 업로드한 JavaScript 파일에 자동 주입되지 않습니다.

### 빌드 후 배포 또는 Git 자동 배포

GitHub 연동 배포에서는 `codex/reconnect-netlify-api`를 배포 브랜치로 선택합니다. 루트 `netlify.toml`이 다음 설정을 적용합니다.

| 설정 | 값 |
| --- | --- |
| Base directory | `app` |
| Build command | `node ../scripts/build-netlify.mjs` |
| Publish directory | `dist` (Base directory 기준) |
| 환경변수 | `HONSAL_API_BASE_URL` = `https://villages-don-clips-archived.trycloudflare.com` |

Netlify **Project configuration → Environment variables**에서 변수를 추가합니다. 범위를 선택할 수 있으면 **Builds**를 포함합니다. 주소 끝에 `/api`, 경로, 쿼리를 붙이지 않습니다. 저장한 뒤 Deploys에서 재배포합니다. 이전 안내의 빈 빌드 명령·게시 경로 `.` 대신 위 설정을 사용합니다.

빌드는 UI 파일을 `app/dist/`에 복사하고 공개 API 주소만 `js/runtime-config.js`에 기록합니다. Python 코드와 원본 설정은 배포 폴더에 포함하지 않습니다. `.env`나 인증키는 필요하지 않습니다. API 주소가 없거나 HTTPS 출처 형식이 아니면 배포를 중단해 잘못 연결된 화면으로 덮어쓰지 않습니다. 로컬 Python 미리보기는 계속 같은 서버의 API를 사용합니다.

수동 업로드를 원하면 API 담당자가 같은 환경변수로 빌드한 `app/dist/` 폴더를 전달합니다. Git 저장소에 연결되지 않은 수동 배포 사이트라면, 팀원은 Netlify의 기존 프로젝트 **Deploys** 페이지 아래 업로드 영역에 해당 폴더를 드래그해 배포합니다. 이미 빌드한 폴더에는 API 주소가 포함돼 있어 Netlify에서 별도 변수 설정이 필요 없습니다. API 주소를 바꾸면 다시 빌드한 폴더를 배포해야 합니다.

새 사이트 주소를 사용한다면 카카오 JavaScript 키의 허용 도메인과 백엔드 CORS 허용 출처도 함께 등록합니다. Quick Tunnel은 PC·서버·터널이 실행 중일 때만 사용할 수 있는 임시 테스트 주소입니다.

## 5. 검증과 변경 범위

2026-10-31 연결 복구는 최종 main `eb0c49f`를 기준으로 진행했습니다. 실행 코드에서는 `app/js/runtime-config.js`의 공개 API 주소만 바꿨으며 UI·점수 산식·데이터는 그대로입니다. 공개 `/api/health`·`/api/options`·`/api/analyze` 응답과 기존 Netlify 출처의 CORS 허용을 확인했습니다. 최종 UI와 실제 HTTPS API를 연결한 브라우저 검사에서 시설 선택 40종, 춘천시청 위치(경도 127.7298·위도 37.8813)의 당구장·볼링장 선택 결과 66.8점(원점수 66.77)과 시설 12곳을 확인했습니다. 이 결과는 배포 전 연결 검사이며, GitHub 업로드만으로 기존 수동 배포 사이트가 갱신되지는 않습니다.

### 이전 연결 검증 기록 (2026-10-30, 현재 점수 기준과 다름)

2026-10-30 로컬 5500 서버에서 Python 테스트 65개와 실제 브라우저 검증을 통과했습니다. Netlify 빌드·API 주소 설정 Node 테스트 6개도 통과했습니다. 원본 `app` 폴더와 빌드 산출물을 각각 기존 사이트 출처로 불러오는 브라우저 검사에서 공개 HTTPS API 호출·시설 유형 40종·67.8점·시설 12곳·카카오 지도 로딩을 확인했습니다. 이 검사는 실제 Netlify 사이트를 재배포하지 않고 수행했습니다.

- 시설 종류 40개 선택지와 당구장·볼링장 선택 시 67.8점·12개 전체 카드 표시
- 네 항목을 포함한 시험 선택에서 시설 카드 118개와 지도에 전달한 시설 ID 일치
- 전체 선택 해제·API 오류 시 이전 점수·목록·마커 초기화
- 상호명·좌표가 같은 서로 다른 시설 ID 3개의 개별 카드 유지
- 모바일 화면에서 지도 SDK 로딩을 차단한 경우에도 점수·시설 목록 정상 표시
- 검증 흐름에서 JavaScript 실행 오류 없음

이 결과는 로컬 테스트 브랜치 기준입니다. 다른 팀원 PC와 실제 배포 도메인에서도 지도 키 설정·API 연결·동일 결과를 확인해야 합니다.

자료·가중치를 바꾸면 테스트 후 서버를 재시작합니다. 가중치는 `config/weights.json`, 거리 산식은 `src/scoring/accessibility.py`, 항목 합산은 `src/scoring/preferences.py`에서 수정합니다. 이번 UI 연결은 **750m 기준의 최근접 거리 산식과 교통 40%·생활 30%·의료 20%·여가 10% 가중치를 변경하지 않습니다.**
