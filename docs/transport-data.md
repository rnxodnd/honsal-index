# 춘천 교통시설 위치 데이터

수집·검증일: 2026-10-30. 정제 코드: `src/data/prepare_transport.py`.

정제 CSV 3개와 이 설명서, 정제 코드는 GitHub에서 공유합니다. 팀원들은 Pull 후 정제 CSV를 바로 읽을 수 있으며 원본 다운로드나 재추출은 필요하지 않습니다.

## 프로그램에서 사용할 파일

| 파일 | 시설 수 | 내용 |
| --- | ---: | --- |
| `data/processed/chuncheon_bus_stops.csv` | 1,890 | 춘천시 제공 버스 승강장 위치 |
| `data/processed/chuncheon_rail_stations.csv` | 6 | 굴봉산·백양리·강촌·김유정·남춘천·춘천 |
| `data/processed/chuncheon_transport_facilities.csv` | 1,896 | 위 두 자료를 합친 파일 |

지도와 백엔드는 통합 파일 하나를 읽습니다. 세 파일을 모두 합치면 중복 집계됩니다. 인코딩은 UTF-8 BOM입니다.

공통 핵심 컬럼은 `facility_id`, `name`, `category`, `city`, `lat`, `lon`, `has_coordinates`, `data_date`, `source`, `source_file`, `source_url`입니다. `category`는 `bus_stop` 또는 `rail_station`입니다. 버스 관리번호는 `source_facility_id`, 모바일 정류장 번호는 `stop_no`로 보존했습니다. 식별자는 문자열로 읽어야 합니다.

`facility_id`는 프로젝트에서 생성한 식별자입니다. 버스는 원본 관리번호를, 철도역은 정규화한 역명을 사용하며 서로 다른 접두사를 붙였습니다. 철도 위치 원본에는 공식 역 ID가 없어 `source_facility_id`를 비워 두었습니다. `source_name`에는 괄호 부역명까지 원본 그대로 남겼습니다.

## 출처와 기준일

### 버스 정류장

- 제공기관: 강원특별자치도 춘천시.
- [공식 목록](https://www.data.go.kr/data/15045129/fileData.do), [공식 원본 다운로드](https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003616610&fileDetailSn=1).
- 원본: `data/raw/chuncheon_bus_stops_portal_20260326.csv`, CP949.
- CSV 내부 `데이터기준일`은 1,890행 모두 **2026-03-26**입니다. 포털 다운로드 메타데이터의 원래 파일명에는 `20250326`이 있으나, 행 내부 날짜를 사용했습니다.
- 원본 SHA-256: `cfeb76163160820257acb3ed04fa821dfb420416d9137f64db3dddc4ad05ca02`.

같은 이름을 가진 승강장도 원본 관리번호가 다르면 각각 보존했습니다. 이름만으로 중복 제거하지 않았습니다. 위치 원본에 노선·배차간격 정보가 없으므로 `line`, `operator`를 추정해서 채우지 않았습니다.

### 철도역

- 제공기관: 국가철도공단.
- [공식 목록](https://www.data.go.kr/data/15041483/fileData.do), [공식 원본 다운로드](https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000002647504&fileDetailSn=1).
- 원본: `data/raw/gyeongchun_station_locations_20241022.csv`, CP949, 경춘선 전체 25행.
- 위치 기준일: **2024-10-22**. 포털 페이지 수정일이나 다운로드일로 바꾸지 않았습니다.
- 원본 SHA-256: `ccc30ea151a6d70d0447ad64da73e7be179842a323f81b4f5f1921f7c3b5e132`.

[춘천시 경춘선 안내](https://www.chuncheon.go.kr/traffic/public-transport/subway/)의 역 목록을 참고해 춘천 6개 역을 선택했습니다. 괄호 부역명을 제거한 이름으로 비교하되 원본 이름을 따로 보존합니다. 원본 선명 `경춘`은 `line`에 그대로 남겼습니다.

### ITX-청춘 정차 정보

위치 원본에는 정차 정보가 없어 [코레일 공식 시간표](https://www.korail.com/com/userBoard.do?mode=list&schBcid=ticketTable)의 **2026-09-01 시행** 자료를 별도로 확인했습니다.

- [평일 XLSX](https://www.korail.com/file/cubedata/COMMON/jfile/202608/28/202608281a045c7905b490.xlsx): `ITX청춘 상행`, `ITX청춘 하행` 시트.
- [휴일 XLSX](https://www.korail.com/file/cubedata/COMMON/jfile/202608/28/202608281a045c7cc64640.xlsx): 같은 시트.
- 보관 원본: `data/raw/itx_gyeongchun_weekday_20260901.xlsx`, `data/raw/itx_gyeongchun_holiday_20260901.xlsx`.
- 평일 SHA-256: `5cee7c8d3409d02bcde2c412b6ab6bc5d5fa5335d07e9331187d89bed6473a70`. 휴일 SHA-256: `a6e95ad13a77fd6a39ee42eb869b7a2238bed6e4a1050514b27f871fd0d3527a`.
- `has_itx=True`: 강촌·남춘천·춘천. 강촌은 일부 열차 정차이며 모든 열차가 정차한다는 의미가 아닙니다.
- `has_itx=False`: 굴봉산·백양리·김유정. 버스 정류장은 해당 없음으로 빈 값입니다.
- 서비스 기준일과 출처는 `itx_schedule_effective_date`, `itx_source_url`에 별도로 기록했습니다.

시간표에는 통과시각도 있으므로 숫자가 있다는 이유만으로 정차로 판정하지 않았습니다. 도착·출발행을 확인했으며 춘천은 기종착역으로 처리했습니다. 전철과 ITX가 같은 역을 이용해도 시설은 하나입니다. ITX 이용 가능한 역만 표시하려면 철도역 중 `has_itx == True`를 선택합니다.

정차 여부는 검증한 시간표에 따른 고정 값입니다. 재실행 시 자동으로 최신 시간표를 조회하지 않으며, 서비스가 바뀌면 원본 시간표와 코드의 `ITX_STATIONS` 및 기준일을 함께 갱신해야 합니다.

## 검증 범위와 이용 시 주의

추출한 1,896개 시설 모두 위경도가 있고 시설 식별자는 중복되지 않습니다. 원본 위경도와 정제 결과의 일치를 확인했습니다. `has_coordinates`는 좌표 존재 여부이며 위치 정확도나 행정경계 내부 여부를 보증하는 값이 아닙니다. 버스의 `city`는 제공 자료의 관할 범위에 따라 부여했습니다. 행정동별 집계 전에는 경계 데이터와 공간 결합이 필요합니다.

버스 승강장 수와 철도역 수를 단순 합산한 값은 교통 편의 점수가 아닙니다. 후속 점수 계산에서 접근거리와 교통수단을 구분해야 합니다.

## 재실행

Python 3.12 가상환경을 활성화한 상태로 프로젝트 루트에서 실행합니다.

```bash
python src/data/prepare_transport.py
```

원본 CSV가 없는 PC에서는 아래처럼 검증한 버전의 원본을 다운로드할 수 있습니다.

```bash
python src/data/prepare_transport.py --download
```

다운로드 내용과 기존 원본은 SHA-256으로 확인합니다. 원본이 변경된 경우 자동으로 덮어쓰지 않고 중단하므로 출처·컬럼·기준일을 다시 확인해야 합니다. `data/raw/`의 원본 CSV·시간표는 Git에서 제외하며, 정제 CSV 3개는 `.gitignore` 예외로 공유합니다.
