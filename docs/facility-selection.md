# 사용자 시설 선택과 4개 분석 항목

2026-10-30 변경 범위: 춘천의 **생활시설·의료·교통·여가시설**을 분석합니다. 안전성, 주거 부담, 별도 생활 서비스 항목은 이번 구현 범위에서 제외합니다.

## 사용자가 보게 될 동작

여가시설 선택지에 당구장·볼링장·탁구장이 있다면 사용자가 당구장과 볼링장만 선택할 수 있습니다. 이때 지도, 거리 계산, 항목 점수, 동네 비교, 추천 이유에 같은 선택을 적용합니다. 탁구장은 계산과 지도에서 제외합니다. 지도만 숨기고 점수는 전체 시설로 계산하지 않습니다.

| 분석 항목 | 내부 키 | 자료와 선택지 |
| --- | --- | --- |
| 생활시설(편의시설) | `daily_life` | 상권 자료의 편의점·슈퍼마켓·미용실 등 사용자 지정 11종 |
| 의료 | `healthcare` | 기존 의료 CSV의 `facility_type`. 의원·치과의원·약국 등 |
| 교통 | `transport` | 버스정류장·철도역. 같은 역을 전철과 ITX로 이중 집계하지 않음 |
| 여가시설 | `leisure_community` | 상권 자료의 당구장·볼링장·탁구장 등 확인된 세부 업종 |

사용자가 선택할 수 있는 목록은 실제로 정리된 자료에서 만듭니다. 아직 자료가 없는 항목은 ‘자료 준비 중’으로 표시합니다. 자료가 없는 업종을 시설 0개로 표시하지 않습니다.

## 현재 데이터 분류 결과

의료·교통 2,420개에 춘천 상권의 편의·여가시설 2,832개를 추가하여 실제 시설 **5,252개**, 선택용 세부 종류 **40개**를 만들었습니다. 기존 의료·교통 CSV와 시설 ID는 변경하지 않았습니다.

| 항목 | 시설 수 | 선택 가능한 세부 종류 |
| --- | ---: | --- |
| 생활시설(편의시설) | 2,200 | 사용자 지정 11종. 편의점 403, 슈퍼마켓 382, 미용실 900 등 |
| 의료 | 524 | 의원 181, 약국 144, 치과의원 88, 한의원 67, 보건진료소 13, 보건지소 10, 요양병원 8, 정신병원 5, 병원 4, 종합병원 2, 보건소 1, 한방병원 1 |
| 교통 | 1,896 | 버스정류장 1,890, 철도역 6 |
| 여가시설 | 632 | 사용자 지정 15종. 헬스장 140, 당구장 77, 볼링장 7 등 |

상권 26종의 전체 목록과 코드별 개수는 [편의·여가시설 데이터](commerce-data.md)에 정리했습니다. 원본에 전화번호 컬럼이 없어 상권 시설의 전화번호는 빈 값입니다.

분류한 자료의 `analysis_category`와 `analysis_subtype`을 기존 선택 함수에 바로 전달할 수 있습니다.

- `data/processed/chuncheon_facilities_classified.csv`: 시설별 공통 분류와 위치·출처를 포함한 **분석 입력 파일**. 앱은 이 파일 하나를 읽습니다.
- `data/processed/facility_type_catalog.csv`: 항목·세부 시설별 개수와 좌표 보유 개수를 담은 40행 요약. 시설별 자료에 다시 합쳐 집계하지 않습니다.
- `data/processed/facility_dataset_status.csv`: 네 항목의 분류 상태와 시설 수. 현재 네 항목 모두 `classified`입니다.

기존 의료·교통·상권 통합 CSV 또는 개별 CSV를 새 분석 입력 파일과 다시 합치면 같은 시설이 중복됩니다. 같은 이름이나 좌표의 서로 다른 시설은 각자 ID를 유지하고, 전철·ITX가 공유하는 역도 복제하지 않습니다. 의료 세부 종류는 심평원 원본 종별 분류이며 진료과·진료 가능 시간으로 해석하지 않습니다.

프로젝트 루트에서 `python src/data/classify_facilities.py`로 다시 만들 수 있습니다. `data/processed/chuncheon_commerce_facilities.csv`가 있으면 자동으로 포함하므로, 재실행할 때 상권 데이터가 빠지지 않습니다. 다른 공통 형식 상권 파일을 지정하려면 `python src/data/classify_facilities.py --commerce <상권CSV경로>`를 사용합니다. 상권 원본에서 공통 형식까지 만드는 코드는 `src/data/prepare_commerce.py`이며, 실제 소분류 코드 대응표는 `config/commerce_categories.json`입니다.

## 데이터 담당자가 보존할 컬럼

기존 CSV는 그대로 두고 분석용 파일에 공통 컬럼을 추가합니다. 기존 `category`, `facility_type`을 덮어쓰지 않습니다.

| 컬럼 | 의미 |
| --- | --- |
| `facility_id` | 전체 자료에서 고유한 시설 식별자. 필요하면 출처 접두사를 사용 |
| `name` | 시설 이름 |
| `lat`, `lon` | 위도·경도 |
| `analysis_category` | 위의 네 내부 키 중 하나 |
| `analysis_subtype` | 사용자가 선택할 세부 시설 종류. 예: `당구장`, `볼링장`, `탁구장` |
| `source_business_code`, `source_business_name` | 상권 원본의 세부 업종 코드·명칭. 원본 컬럼을 함께 유지해도 됨 |
| `source`, `source_file`, `source_url`, `data_date` | 출처와 자료 기준일 |

상권 데이터는 **원본 소분류 코드 → 분석 항목 → 선택용 세부 시설 종류**의 명시적 대응표를 사용합니다. 상호명에 ‘볼링’ 등이 들어가는지만으로 시설을 분류하지 않습니다. 현재 원본의 `독서실/스터디 카페`(`R10202`)는 선택용 이름 `독서실/스터디카페`로 연결하며 원본 명칭도 보존합니다. 지정한 26종 이외의 업종은 이번 분석에 넣지 않습니다. 다른 원본을 적용할 때 코드와 명칭이 맞지 않으면 먼저 대응표를 확인합니다.

최종 집계 전에 세부 업종을 지우거나 생활·여가 총개수로만 합산하면 사용자 선택에 따른 재계산이 어려워집니다. 시설별 위치와 세부 분류를 유지하세요.

## 백엔드 입력과 계산 규칙

`src/scoring/preferences.py`의 함수:

- `available_facility_types(facilities)`: 실제 자료의 항목별 세부 선택지.
- `filter_facilities(facilities, selected)`: 사용자가 선택한 시설만 남김. 지도와 거리 계산에 함께 사용.
- `normalize_selected_weights(selected, weights=None)`: 선택 유형이 있는 항목만 남겨 가중치 합계를 1로 맞춤.
- `calculate_preference_scores(type_scores, selected, weights=None)`: 격자·세부유형별 점수를 선택해 항목 평균과 총점·순위를 계산.

선택값의 예:

```python
selected = {
    "daily_life": ["편의점"],
    "healthcare": ["약국"],
    "transport": ["버스정류장"],
    "leisure_community": ["당구장", "볼링장"],
}
```

위 선택값은 현재 확보한 유형을 이용한 예입니다. 전체 선택지는 `available_facility_types`로 만듭니다. 빈 목록은 해당 항목을 분석에서 제외한다는 뜻입니다. 네 목록이 모두 비면 시설을 하나 이상 선택하도록 안내합니다.

`type_scores`에는 `grid_id`, `analysis_category`, `analysis_subtype`, `score` 컬럼이 필요합니다. 한 행은 **격자 하나·세부 시설 종류 하나의 접근성 점수(0~100)**입니다. 점수가 원본 시설 개수나 거리인 상태로 전달하면 안 됩니다. 각 세부 유형에 적용할 접근성 산식·거리 기준은 후속 공간 분석 단계에서 확정합니다.

1. 선택한 세부 시설 종류마다 접근성 점수를 구합니다.
2. 같은 항목 안에서는 선택한 종류들의 점수를 동일 비중으로 평균합니다. 예: 여가 = (당구장 점수 + 볼링장 점수) / 2.
3. 선택한 항목의 가중치를 합계 1로 재조정해 총점을 구합니다.
4. 총점이 확정된 격자만 순위를 계산합니다. 같은 점수는 같은 순위입니다.

시설이 실제로 없는 경우와 자료가 없는 경우를 구분합니다. 원본 자료의 범위를 확인한 뒤 특정 격자에 시설이 없으면 공간 분석 단계에서 명시적으로 0점을 만들 수 있습니다. 선택한 세부유형 점수가 누락된 격자는 평균을 나머지 유형만으로 계산하지 않고 총점·순위를 비워 둡니다. 선택하지 않은 유형의 결측은 결과에 영향을 주지 않습니다. 가중치가 0인 항목은 총점에 기여하지 않습니다.

`config/weights.json`은 기존 네 항목의 상대 비중 25:15:20:10을 합계 1로 재조정한 초안입니다. 생활시설 약 35.71%, 의료 약 21.43%, 교통 약 28.57%, 여가 약 14.29%이며 검증된 측정 척도가 아닙니다. 시설 선택과 항목 가중치 조절은 별도 입력입니다.

## 프론트엔드 연결

`app/facility_filters.py`의 `render_facility_filters(options)`는 항목별 다중 선택 UI를 제공하고 위 형식의 선택값을 반환합니다. 초기에는 확보된 선택지를 모두 선택합니다. 전체 해제 시 경고를 표시하므로 호출 화면에서도 계산을 중단해야 합니다.

```python
import streamlit as st
from app.facility_filters import render_facility_filters
from src.scoring.preferences import (
    available_facility_types, filter_facilities, calculate_preference_scores,
)

import pandas as pd
facilities = pd.read_csv(
    "data/processed/chuncheon_facilities_classified.csv", dtype={"facility_id": "string"}
)
# type_scores: 별도 공간 분석에서 만든 격자·세부유형별 0~100점
options = available_facility_types(facilities)
selected = render_facility_filters(options)
if not any(selected.values()):
    st.stop()

map_facilities = filter_facilities(facilities, selected)
scores = calculate_preference_scores(type_scores, selected)
# 지도에는 map_facilities, 비교·추천에는 scores를 사용합니다.
```

시설 선택이 바뀌면 점수와 추천도 갱신해야 합니다. 계산 결과를 캐시할 때는 선택한 유형·가중치·자료 버전을 입력에 포함합니다. 기본 전체 시설 점수와 사용자 선택 점수를 비교한다면 어떤 선택으로 만든 결과인지 함께 표시합니다.

## 현재 구현과 다음 연결 작업

시설 5,252개의 공통 분류, 40종 선택용 목록, 자료 준비 상태와 재실행 코드를 추가했습니다. 상권 자료의 실제 코드 대응표, 시설 선택 UI 컴포넌트, 공통 필터, 세부유형 점수 평균·가중 총점·순위 함수도 있습니다. 격자별 접근성 점수 생성과 최종 지도·추천 화면 연결은 아직 진행할 작업입니다. 현재 시설 개수나 테스트용 가상 값을 실제 동네 점수로 표시하지 않습니다.

- 데이터 담당: 시설별 위치를 격자와 연결하고 원본·분류 코드·결측 처리 확인.
- 팀장: 격자별 시설 접근성 점수를 계산해 `type_scores` 생성 후 선택 함수 연결.
- 프론트엔드 담당: 다중 선택값을 지도·점수·추천에 공통 전달.
- 기획·발표 담당: 같은 지역에서 당구장 선택과 볼링장 선택에 따라 결과가 바뀌는 시연 준비.

검증 명령: 가상환경에서 `python -m unittest discover -s tests -v`.
