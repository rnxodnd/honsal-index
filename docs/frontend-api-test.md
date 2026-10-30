# 기존 UI에서 점수 API 테스트하기

이 작업은 `codex/backend-api-test` 브랜치에서 진행합니다. **GitHub와 Netlify의 UI 코드는 변경하지 않았습니다.** 아래 브라우저 콘솔 예시는 현재 화면의 위치·시설 선택값을 읽어 API를 호출하고 결과를 로그로 출력합니다. 화면의 점수나 DOM을 변경하거나 이벤트를 자동 연결하지 않습니다.

## 1. API 서버와 임시 HTTPS 주소

테스트 브랜치 작업 폴더에서 Python 3.12 가상환경에 `requirements.txt`를 설치한 뒤 실행합니다.

```bash
.venv/bin/python -m uvicorn src.public_api:app --host 127.0.0.1 --port 8001
```

별도 터미널에서 설치된 `cloudflared`를 실행합니다.

```bash
cloudflared tunnel --url http://127.0.0.1:8001 --protocol http2 --no-autoupdate
```

터미널에 나온 `https://…trycloudflare.com` 주소를 아래 코드의 `BACKEND_URL`에 넣습니다. API 상태는 해당 주소 뒤에 `/api/health`를 붙여 확인할 수 있습니다. 성공 시 `status: "ok"`, 시설 5,252개·후보 격자 2,526개가 표시됩니다.

Quick Tunnel은 테스트용 임시 주소이며, 재실행하면 주소가 바뀌고 가동 시간을 보장하지 않습니다. PC·API 서버·터널이 모두 실행 중이어야 합니다. 이 주소를 고정된 배포 주소로 저장하지 마세요. [Cloudflare 공식 안내](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

현재 개발 PC의 별도 작업 폴더 `honsal-index-api-test`에서 기존 가상환경을 사용한다면 첫 명령의 `.venv/bin/python`을 `../honsal-index/.venv/bin/python`으로 바꿀 수 있습니다. 다른 팀원은 자기 PC에 가상환경을 생성합니다.

## 2. 기존 화면의 값과 API 입력 대응

[현재 배포 화면](https://unique-dusk-66f82f.netlify.app/)에서 위치를 고르고 편의·여가 또는 의료시설을 하나 이상 체크합니다. 현재 교통 선택은 ‘데이터 대기’ 상태이므로 예시는 교통을 선택하지 않습니다.

| 화면에서 읽는 값 | API에 보내는 값 |
| --- | --- |
| `HonsalMap.getSelected().lng` | `lon` |
| `HonsalMap.getSelected().lat`, `.name` | `lat`, `name` |
| `HonsalFacilityFilters.getSelected()`의 편의시설 `category` | `selected.daily_life` 목록 |
| 같은 함수의 여가시설 `category` | `selected.leisure_community` 목록 |
| `HonsalMedicalFilters.getSelected()` | `selected.healthcare` 목록 |
| 현재 교통 선택 없음 | `selected.transport: []` |

`HonsalGrid.getSelectedIds()`로 화면이 계산한 주변 격자 ID를 볼 수 있습니다. 분석 API는 좌표로 격자와 주변 범위를 다시 검증하므로 이 목록을 요청에 보낼 필요는 없습니다.

## 3. 브라우저 콘솔에서 독립 호출

배포 화면의 개발자 도구 콘솔에서 아래를 실행합니다. 첫 줄의 주소를 현재 테스트 서버 주소로 바꿔야 합니다.

```javascript
(async () => {
  const BACKEND_URL = 'BACKEND_URL';
  if (!BACKEND_URL.startsWith('https://')) {
    throw new Error('BACKEND_URL을 실행 중인 HTTPS API 주소로 바꿔주세요.');
  }
  if (!window.HonsalMap?.getSelected ||
      !window.HonsalFacilityFilters?.getSelected ||
      !window.HonsalMedicalFilters?.getSelected) {
    throw new Error('현재 배포 화면에서 지도와 시설 목록 로딩 후 실행하세요.');
  }

  const location = window.HonsalMap.getSelected();
  const selected = {
    daily_life: [],
    healthcare: window.HonsalMedicalFilters.getSelected(),
    transport: [],
    leisure_community: []
  };
  const groupKeys = { '편의시설': 'daily_life', '여가시설': 'leisure_community' };
  for (const item of window.HonsalFacilityFilters.getSelected()) {
    const key = groupKeys[item.group];
    if (!key) throw new Error(`확인되지 않은 시설 그룹입니다: ${item.group}`);
    selected[key].push(item.category);
  }
  for (const key of Object.keys(selected)) selected[key] = [...new Set(selected[key])];
  if (!Object.values(selected).some(types => types.length)) {
    throw new Error('화면에서 분석할 시설을 하나 이상 체크한 뒤 다시 실행하세요.');
  }

  const response = await fetch(`${BACKEND_URL.replace(/\/$/, '')}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'omit',
    body: JSON.stringify({
      lon: location.lng,
      lat: location.lat,
      name: location.name,
      selected
    })
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || `HTTP ${response.status}`);
  console.log('분석 결과', result);
  console.log('총점', result.total_score, '주변 선택 시설 수', result.facilities.length);
  console.table(result.categories);
  console.table(result.types);
})();
```

기준 예시: 경도 `127.7298`, 위도 `37.8813`에서 당구장·볼링장만 선택하면 현재 자료·산식 기준 67.8점, 주변 해당 시설 12개를 반환합니다. 다른 위치나 선택 조합에서는 점수가 달라집니다. 빈 선택값은 전체 시설 선택으로 바꾸지 않고 오류로 안내합니다.

2026-10-30 검증에서는 실제 Netlify 화면의 선택값을 읽어 임시 HTTPS API에 요청했고, 200 응답·67.8점·12개 시설을 확인했습니다. 빈 선택의 422 오류 응답도 브라우저에서 읽을 수 있었습니다. 허용하지 않은 출처의 사전 요청은 400, UI·자산·원본 CSV 경로는 404를 반환했습니다. 이 검증은 콘솔 호출이며 기존 화면의 ‘점수 준비 중’ 표시는 변경하지 않았습니다.

## 4. 프론트엔드 담당자에게 전달할 내용

- 실행 중인 `BACKEND_URL`과 [API 명세](api.md)를 전달합니다. 같은 주소에 `/api/options`, `/api/analyze`를 사용합니다.
- 기존 위치 이벤트 `honsal:selection`, 편의·여가 선택 이벤트 `honsal:facility-filters`, 의료 선택 이벤트 `honsal:medical-filters`에 맞춰 요청을 보낼 수 있습니다. 현재 이벤트의 `applied: false`는 점수·지도에 아직 반영되지 않았음을 뜻합니다.
- 응답 `total_score`, `categories`, `types`, `facilities`를 기존 점수·근거·시설 영역에 연결하는 작업은 프론트엔드 담당자가 진행합니다. 이 테스트에서는 해당 UI 연결을 적용하지 않았습니다.
- 현재 배포 UI에는 안전·주거 부담을 포함한 6개 지표가 있으나, API는 합의된 생활·의료·교통·여가 4개 항목만 제공합니다. 화면 항목 정리는 프론트엔드 담당자와 맞춰야 합니다.
- 선택하지 않은 항목의 점수는 `null`, 적용 가중치는 0입니다. 선택한 항목만 가중치 합계를 1로 조정합니다. 예를 들어 여가만 선택하면 여가 비중은 100%입니다.
- 기본 CORS 허용 출처는 배포 사이트의 정확한 주소입니다. CORS는 로그인·인증 기능이 아니며, API 전용 서버는 UI나 CSV 원본 경로를 제공하지 않습니다.
- API 코드·자료·가중치를 바꾸면 테스트 후 서버를 재시작합니다. 터널까지 다시 만들면 새 주소를 프론트엔드 담당자에게 전달해야 합니다.
