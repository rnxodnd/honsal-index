# 춘천 혼살지수 분석 API

현재 API는 한 위치가 속한 후보 격자를 분석하여 선택한 시설의 목록·거리·점수를 JSON으로 반환합니다. `codex/ui-facility-results`의 UI는 이 응답을 종합·항목별 점수, 시설 개수·상호명 목록과 지도에 연결합니다. 두 위치 비교는 같은 선택 조건의 응답을 화면에서 저장해 비교합니다. 전체 후보 순위와 사용자 가중치 편집은 후속 작업입니다. 이번 UI 연결은 아직 `main`과 Netlify에 반영하지 않았습니다.

## 실행과 파일

프로젝트 루트에서 실행합니다. Python 3.12 가상환경과 `requirements.txt`의 설치가 필요합니다.

```bash
.venv/bin/python -m uvicorn src.api:app --host 127.0.0.1 --port 5500 --reload
```

Windows에서는 `.venv/bin/python`을 `.\.venv\Scripts\python.exe`로 바꿉니다. 현재 개발 PC의 별도 `honsal-index-api-test` 폴더에서는 `../honsal-index/.venv/bin/python`을 사용할 수 있습니다. <http://127.0.0.1:5500>은 연결된 UI, <http://127.0.0.1:5500/api/health>는 API 준비 상태입니다. UI는 기본적으로 같은 서버의 `/api`를 호출합니다.

API만 실행할 때는 `src.public_api:app --host 127.0.0.1 --port 8001`을 사용합니다. 이 진입점의 `/`, UI 자산, CSV 경로는 404를 반환합니다. UI를 제공하는 `src.api:app`만 `/data/grid_500m_bounds.csv`와 `/data/chuncheon_medical_facilities.csv`를 지도용으로 제공합니다. 다른 데이터 파일은 정적 경로로 공개하지 않습니다.

정적 HTTPS 화면에서 API를 호출하려면 별도의 HTTPS 백엔드 주소와 허용 출처 설정이 필요합니다. `analysis.js`를 불러오기 전에 `window.HONSAL_API_BASE_URL`에 해당 서버의 기본 주소를 설정합니다. [프론트엔드 API 테스트 안내](frontend-api-test.md)에 로컬 테스트와 선택적인 임시 HTTPS 연결 방법이 있습니다.

| 파일 | 역할 |
| --- | --- |
| `src/api.py` | HTTP 입력 검사, API 경로, 정적 화면 제공 |
| `src/public_api.py` | API 전용 실행, 허용한 배포 화면의 CORS 설정 |
| `src/scoring/accessibility.py` | 자료 읽기, 위치·격자 확인, 최근접 거리·유형별 점수 |
| `src/scoring/preferences.py` | 선택 유형 검증, 항목 평균, 가중치 재조정 |
| `app/app/index.html`, `app/app/js/map.js` | 기존 디자인의 UI, 지도 검색·시설 마커 표시 |
| `app/app/js/analysis.js` | 네 항목 선택, API 호출, 점수·개수·전체 상호명 목록 표시 |
| `app/app/js/main.js` | 실제 분석 응답을 저장하는 두 위치 비교 |

서버는 시작할 때 다음 네 파일을 읽습니다. 자료나 가중치를 수정한 뒤에는 서버를 재시작합니다.

- `data/processed/chuncheon_facilities_classified.csv`
- `data/processed/grid_500m_filtered.csv`
- `data/raw/chuncheon_dong.geojson`
- `config/weights.json`

로컬 생성 파일인 `chuncheon_facilities_with_grid.csv`, `grid_3x3_facility_counts.csv`는 API 실행의 필수 입력이 아닙니다. 원본 시설을 읽어 좌표와 격자를 검증합니다. 후보 격자 밖 시설도 주변 격자 분석에 필요하므로 보존합니다.

## API 목록

| 메서드·경로 | 기능 |
| --- | --- |
| `GET /api/health` | 준비 상태와 시설·후보 격자 수 |
| `GET /api/options` | 자료에 있는 시설 종류, 기본 가중치, 점수 방식, 기본 위치 |
| `POST /api/analyze` | 한 위치와 선택 시설의 접근성 분석 |

`GET /api/options`의 `categories`는 `key`, `label`, `weight`, `subtypes`를 제공합니다. 각 `subtypes` 항목은 `name`, `facility_count`를 가집니다. 선택지는 이 응답에서 만들고, 화면에 표시한 이름을 그대로 전송합니다.

## 요청 예시

경도·위도는 WGS84 숫자입니다. 당구장·볼링장만 분석하는 예시입니다.

```bash
curl -sS http://127.0.0.1:5500/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"lon":127.7298,"lat":37.8813,"name":"춘천시청 인근","selected":{"leisure_community":["당구장","볼링장"]}}'
```

선택 항목 키는 `daily_life`, `healthcare`, `transport`, `leisure_community`입니다. 생략한 항목이나 빈 목록은 선택하지 않은 것으로 처리합니다. 모든 항목이 비면 오류를 반환합니다. `name`은 선택 사항이며 200자 이하 문자열입니다. 사용자 지정 가중치는 현재 요청 항목이 아닙니다.

API 요청 형식 참고용 JavaScript 예시입니다. 로컬 UI와 같은 서버를 사용하면 아래처럼 상대 경로로 요청합니다. 별도 서버는 `/api/analyze` 앞에 해당 서버 주소를 붙입니다.

```javascript
const response = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    lon: 127.7298,
    lat: 37.8813,
    selected: { leisure_community: ['당구장', '볼링장'] }
  })
});
const result = await response.json();
if (!response.ok) throw new Error(result.error.message);
console.log(result.total_score, result.categories, result.facilities);
```

## 응답 내용

| 필드 | 의미 |
| --- | --- |
| `location` | 사용자가 입력한 위치의 경도·위도·이름 |
| `grid` | 해당 후보 격자 ID·행정동·중심 경도·위도 |
| `neighborhood` | 주변 3×3의 9개 격자 ID와 지도 표시용 위경도 경계 |
| `scoring` | 산식 이름, 750m 기준, 격자 중심 직선거리 기준 |
| `total_score` | 선택한 유형·항목을 반영한 0~100 총점 |
| `categories` | 항목 키·이름·적용 가중치·항목 점수. 미선택 항목 점수는 `null` |
| `types` | 선택한 세부 종류별 점수·최근접 시설·주변 개수·거리 범위 상태 |
| `facilities` | 선택 종류이면서 3×3에 있는 시설. ID·이름·종류·좌표·주소·전화·거리·경계 포함 여부 |
| `notices` | 거리 기준·자료 해석에 대한 설명 |

`types[].nearest`는 ID·이름·좌표·거리(`distance_m`)를 담고, 주변 3×3에 해당 유형이 없으면 `null`입니다. `count_3x3`는 정사각형 내 개수이고 `count_within_radius`는 격자 중심에서 750m 이내 개수이므로 서로 다를 수 있습니다.

화면의 **상호명**은 `facilities[].name`을 표시합니다. 시설 목록과 항목별 개수는 `types[].nearest`가 아닌 전체 `facilities`로 만듭니다. 상호명·유형·좌표가 같아도 `facility_id`가 다르면 각각 유지하며, 15개 제한 없이 모두 표시합니다. 같은 좌표의 지도 마커는 묶어 표시하되 팝업에는 해당 시설의 상호명을 모두 표시합니다. 점수 계산의 최근접 시설 필드와 산식은 변경하지 않습니다.

## 점수와 거리 해석

```text
유형 점수 = max(0, 100 × (1 - 최근접 거리(m) / 750))
항목 점수 = 그 항목에서 선택한 유형 점수들의 동일 비중 평균
총점 = 선택 항목별 점수 × 재조정한 가중치의 합
```

- 0m 100점, 150m 80점, 300m 60점, 450m 40점, 600m 20점, 750m 이상 0점입니다.
- 거리는 EPSG:5179 평면 좌표에서 **입력 위치가 속한 500m 격자 중심**부터 계산합니다. 같은 격자의 다른 주소는 같은 점수를 받습니다. 도로 경로·횡단시설·도보 시간은 반영하지 않습니다.
- 3×3 범위는 1.5km 정사각형입니다. 모서리의 시설은 750m보다 멀 수 있으며 목록에는 포함되지만 점수는 0일 수 있습니다.
- 기본 가중치는 교통 40%·생활 30%·의료 20%·여가 10%입니다. 여가만 선택하면 여가 비중이 100%가 됩니다. 당구장·볼링장만 선택한 총점은 두 유형 점수의 평균입니다.
- 확보한 종류지만 주변 3×3에 시설이 없으면 `no_facility_in_neighborhood`와 0점을 반환합니다. 최근접 시설이 750m 이상이면 `outside_scoring_radius`입니다. 자료 전체에 없는 종류를 요청하거나 자료의 좌표가 누락된 경우는 0점으로 처리하지 않습니다.
- 일부 원본 교통시설은 춘천 행정경계 밖에 있습니다. 3×3에 포함되면 보존해 계산하며 `in_city_boundary`로 구분합니다. 요청 위치 자체는 춘천 안에 있어야 합니다.
- 상권 원본에는 전화번호가 없어 `phone`이 `null`입니다.

## 오류와 연결 시 주의점

오류 응답은 `{"error":{"code":"invalid_selection","message":"설명"}}` 형식입니다.

| HTTP | 사례 |
| --- | --- |
| 400 | JSON 문법 오류, NaN·Infinity |
| 413 | 요청 본문 32KB 초과 |
| 415 | Content-Type이 application/json이 아님 |
| 422 | 필수값 누락·잘못된 좌표·전체 선택 해제·미확보 종류·춘천 밖 위치·후보 밖 격자 |
| 503 | 서버가 원본 자료·설정을 읽거나 검증하지 못함 |
| 500 | 예상하지 못한 서버 처리 오류. 서버 실행 로그 확인 |

현재 테스트 UI는 선택·위치가 바뀌면 이전 점수·개수·목록·마커를 지우고 다시 분석합니다. 요청 취소와 순서 검사를 통해 늦게 도착한 이전 응답을 표시하지 않습니다. 전체 선택 해제와 API 오류 시에도 이전 결과를 남기지 않습니다. 지도 SDK 사용 여부와 관계없이 좌표를 보내는 분석 API 요청은 사용할 수 있습니다. 실제 지도·주소 검색은 카카오 JavaScript 키와 등록 도메인 설정에 따릅니다.

`src.public_api:app`의 기본 허용 출처는 `https://unique-dusk-66f82f.netlify.app`이며, 허용 메서드는 GET·POST, 요청 헤더는 Content-Type입니다. 자격 증명은 사용하지 않습니다. `HONSAL_ALLOWED_ORIGINS`에는 경로·쿼리 없이 정확한 `http(s)://호스트[:포트]` 출처를 쉼표로 구분할 수 있습니다. 와일드카드는 허용하지 않습니다. 이 CORS 설정은 사용자 인증을 대신하지 않습니다.

서버는 로컬 `127.0.0.1:8001`에서 실행하고, 외부 연동 확인 시 임시 HTTPS 터널을 사용할 수 있습니다. 임시 주소는 서버·터널·PC가 실행되는 동안 사용하는 테스트용 주소이며, 고정 주소를 가진 상시 배포와는 운영 조건이 다릅니다.

검증 명령:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Python 테스트 63개가 통과했습니다. 기본 위치에서 당구장·볼링장만 선택하면 현재 자료·산식 기준 총점 67.8, 전체 시설 12개입니다.
