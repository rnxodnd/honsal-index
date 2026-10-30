# 팀 격자 범위·의료시설 연결 자료

`feature/grid`에서 추가한 두 CSV는 지도에 격자를 그리거나 시설의 격자 ID를 확인할 때 사용합니다.

| 파일 | 내용 |
| --- | --- |
| `data/processed/grid_500m_bounds.csv` | 전체 500m 격자 4,738개의 중심·네 모서리·위경도 범위. 이 중 후보 격자는 2,526개 |
| `data/processed/facilities_grid.csv` | 의료시설 524개에 `grid_id`와 후보 포함 플래그를 추가한 결과 |

`facilities_grid.csv`에는 의료시설만 있습니다. 의료·교통·생활·여가 전체 5,252개를 담은 `chuncheon_facilities_classified.csv`와 범위가 다르므로 전체 시설 분석 입력으로 대체하지 않습니다. 시설별 연결 파일과 원본 분류 파일의 행을 이어 붙이면 같은 시설이 중복됩니다.

## 후보 플래그와 통계의 의미

기존 프론트엔드와의 호환을 위해 `is_populated`라는 컬럼 이름을 유지합니다. 실제 의미는 **필터 결과의 후보 격자 목록에 들어 있는지**입니다.

- `1`: 후보 격자.
- `0`: 전체 격자에는 있으나 후보 목록에서는 제외된 격자. 실제 인구가 0이라는 뜻은 아닙니다.
- 시설 파일의 빈 값: 전체 격자 목록 밖이거나 시설 좌표가 없는 경우. `grid_id`가 비었는지도 함께 확인합니다.

필터는 인구 조건 외에도 경계 포함 비율과 통계 확인 여부를 사용합니다. 따라서 후보에서 제외된 2,212개 격자의 `pop_1km`, `hh_1km`, `single_hh_1km`는 **미확인으로 빈칸**을 유지합니다. 후보 격자에서 가져온 수치는 원본 그대로 보존합니다. 기존 후보 통계의 0값에 대한 제한은 [격자 데이터 안내](grid-data.md)를 따릅니다.

이 세 통계는 상위 **1km 격자**의 값입니다. 같은 상위 격자에 속한 여러 500m 행을 그대로 합산하면 중복됩니다. `is_populated=1`도 해당 500m 칸의 실제 거주 인구를 입증하지 않습니다.

시설이 후보 밖에 있더라도 후보의 주변 3×3 범위에 들어갈 수 있으므로, 주변 시설 계산 전에 `is_populated=1`인 시설만 남기지 않습니다.

## 다시 생성하기

저장소에 공유된 결과 CSV는 바로 읽을 수 있습니다. 범위 CSV를 다시 만들려면 먼저 전체 격자의 CSV·GeoJSON을 생성합니다. 프로젝트 루트의 가상환경에서 실행합니다.

```bash
python src/make_grid.py --boundary data/raw/chuncheon_dong.geojson
python src/export_grid_bounds.py
python src/assign_grid.py
```

`export_grid_bounds.py`는 `grid_500m.csv`, `grid_500m.geojson`, `grid_500m_filtered.csv`를 사용합니다. 공유된 필터 결과가 있으면 `filter_grid.py`를 다시 실행할 필요가 없습니다. 필터 결과를 재생성하려면 별도 SGIS 원본이 필요합니다.

필터 결과가 없거나 비어 있거나, 내보낼 격자 도형이 없으면 기존 범위 CSV를 보존하고 오류를 알립니다. `assign_grid.py`의 기본 입력은 의료시설 CSV이며, `--input`으로 다른 시설 파일을 명시할 수 있습니다.
