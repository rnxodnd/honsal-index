(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const say = (id, value) => {
    $(id).textContent = value;
  };

  const DEFINITION =
    "+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 " +
    "+x_0=1000000 +y_0=2000000 +ellps=GRS80 +units=m +no_defs";

  let map;
  let selected;
  let loading = false;
  let loaded = false;
  let grids = new Map();
  let polygons = [];
  let selectedIds = [];
  let lastPosition = "";
  let phase = "idle";
  // 가운데 격자 거주 표시: true / false / null(확인 전·범위 밖)
  let centerPopulated = null;

  function state() {
    return {
      phase,
      ids: [...selectedIds],
      centerPopulated,
      message: $("gridStatus").textContent
    };
  }

  function publish() {
    document.dispatchEvent(
      new CustomEvent("honsal:grid", {
        detail: state()
      })
    );
  }

  function parseCSV(source) {
    const rows = [];
    let row = [];
    let field = "";
    let quoted = false;

    source = source.replace(/^\uFEFF/, "");

    for (let i = 0; i < source.length; i++) {
      const c = source[i];

      if (c === '"') {
        if (quoted && source[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          quoted = !quoted;
        }
      } else if (c === "," && !quoted) {
        row.push(field);
        field = "";
      } else if ((c === "\n" || c === "\r") && !quoted) {
        if (c === "\r" && source[i + 1] === "\n") i++;

        row.push(field);
        if (row.some(value => value.trim())) rows.push(row);

        row = [];
        field = "";
      } else {
        field += c;
      }
    }

    if (quoted) {
      throw new Error("CSV 따옴표가 닫히지 않았습니다.");
    }

    row.push(field);
    if (row.some(value => value.trim())) rows.push(row);

    const header = rows.shift()?.map(value => value.trim());

    if (!header || new Set(header).size !== header.length) {
      throw new Error("CSV 헤더 오류");
    }

    const coords = ["center_lat", "center_lon"];

    for (const p of ["sw", "se", "ne", "nw"]) {
      coords.push(p + "_lat", p + "_lon");
    }

    const required = [
      "grid_id",
      "adm_nm",
      "is_populated",
      ...coords
    ];

    for (const key of required) {
      if (!header.includes(key)) {
        throw new Error("필수 컬럼 없음: " + key);
      }
    }

    const result = new Map();

    for (const values of rows) {
      if (values.length !== header.length) {
        throw new Error("CSV 열 개수 불일치");
      }

      const g = Object.fromEntries(
        header.map((key, i) => [key, values[i].trim()])
      );

      const match = /^G500_(\d+)_(\d+)$/.exec(g.grid_id);

      if (
        !match ||
        Number(match[1]) % 500 ||
        Number(match[2]) % 500 ||
        result.has(g.grid_id)
      ) {
        throw new Error(
          "잘못되거나 중복된 격자 ID: " + g.grid_id
        );
      }

      if (!["0", "1"].includes(g.is_populated)) {
        throw new Error("거주 여부 값 오류");
      }

      for (const key of coords) {
        const n = Number(g[key]);
        const limit = key.endsWith("_lat") ? 90 : 180;

        if (
          !g[key] ||
          !Number.isFinite(n) ||
          Math.abs(n) > limit
        ) {
          throw new Error("좌표 오류: " + g.grid_id);
        }

        g[key] = n;
      }

      result.set(g.grid_id, g);
    }

    if (!result.size) {
      throw new Error("CSV에 격자가 없습니다.");
    }

    return result;
  }

  // 지도와 교통 필터가 같은 격자 계산을 사용합니다.
  function gridId(lat, lng) {
    const [x, y] = proj4(
      "EPSG:4326",
      "EPSG:5179",
      [lng, lat]
    );

    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error("좌표 변환 실패");
    }

    const gridX = Math.floor(x / 500) * 500;
    const gridY = Math.floor(y / 500) * 500;

    return `G500_${gridX}_${gridY}`;
  }

  function neighbors(id) {
    const [, x, y] = id.split("_").map(Number);
    const ids = [];

    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        ids.push(
          `G500_${x + dx * 500}_${y + dy * 500}`
        );
      }
    }

    return ids;
  }

  function clear() {
    polygons.forEach(polygon => polygon.setMap(null));
    polygons = [];
    selectedIds = [];
  }

  function render() {
    if (!loaded || !map || !selected) return;

    clear();
    centerPopulated = null;
    $("gridFit").disabled = true;

    say("gridAdmin", "—");
    say("gridPopulation", "—");
    say("gridMatched", "—");

    try {
      const id = gridId(selected.lat, selected.lng);
      say("gridId", id);

      const center = grids.get(id);

      if (!center) {
        phase = "outside";
        say(
          "gridStatus",
          "선택 위치는 CSV의 격자 데이터 제공 범위 밖입니다."
        );
        return;
      }

      selectedIds = neighbors(id).filter(
        key => grids.has(key)
      );

      centerPopulated = center.is_populated === "1";
      say("gridAdmin", center.adm_nm || "정보 없음");

      say(
        "gridPopulation",
        center.is_populated === "1"
          ? "거주 표시 있음"
          : "거주 표시 없음"
      );

      say("gridMatched", `${selectedIds.length} / 9개`);

      say(
        "gridStatus",
        selectedIds.length === 9
          ? "선택 격자와 주변 8개 격자를 찾았습니다."
          : "데이터 경계입니다. CSV에 있는 격자만 표시합니다."
      );

      selectedIds.forEach(key => {
        const g = grids.get(key);

        const path = ["sw", "se", "ne", "nw"].map(p => {
          return new kakao.maps.LatLng(
            g[p + "_lat"],
            g[p + "_lon"]
          );
        });

        const polygon = new kakao.maps.Polygon({
          path,
          strokeWeight: key === id ? 3 : 1,
          strokeColor: key === id ? "#d97706" : "#64748b",
          strokeOpacity: 1,
          fillColor:
            g.is_populated === "1" ? "#3b82f6" : "#cbd5e1",
          fillOpacity: 0.25,
          zIndex: key === id ? 2 : 1,
          clickable: false
        });

        polygon.setMap(
          $("gridVisible").checked ? map : null
        );

        polygons.push(polygon);
      });

      phase = "ready";
      $("gridFit").disabled = false;
    } catch (error) {
      clear();
      phase = "error";
      say("gridStatus", "격자 표시 실패: " + error.message);
    } finally {
      publish();
    }
  }

  async function load() {
    if (loading) return;

    loading = true;
    loaded = false;
    clear();

    $("gridReload").disabled = true;
    $("gridFit").disabled = true;

    for (const id of [
      "gridId",
      "gridAdmin",
      "gridPopulation",
      "gridMatched",
      "gridTotal"
    ]) {
      say(id, "—");
    }

    phase = "loading";
    say("gridStatus", "격자 데이터를 불러오는 중입니다…");
    publish();

    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
    }, 15000);

    try {
      if (typeof window.proj4 !== "function") {
        throw new Error(
          "좌표 변환 라이브러리 로드 실패. 인터넷 연결 후 새로고침하세요."
        );
      }

      proj4.defs("EPSG:5179", DEFINITION);

      const response = await fetch(
        "./data/grid_500m_bounds.csv",
        { signal: controller.signal }
      );

      if (!response.ok) {
        throw new Error(
          "CSV 요청 실패 (HTTP " + response.status + ")"
        );
      }

      grids = parseCSV(await response.text());
      loaded = true;

      say(
        "gridTotal",
        grids.size.toLocaleString("ko-KR") + "개"
      );

      render();
    } catch (error) {
      phase = "error";

      say(
        "gridStatus",
        error.name === "AbortError"
          ? "격자 파일 요청 시간이 초과되었습니다. 다시 불러오기를 눌러 주세요."
          : error.message +
            " · app/data/grid_500m_bounds.csv 경로와 Live Server 실행을 확인하세요."
      );
    } finally {
      clearTimeout(timer);
      loading = false;
      $("gridReload").disabled = false;
      publish();
    }
  }

  window.HonsalGrid = {
    attach(kakaoMap) {
      if (map) return;

      map = kakaoMap;
      selected = window.HonsalMap.getSelected();

      document.addEventListener(
        "honsal:selection",
        event => {
          selected = event.detail;

          const key = selected.lat + "," + selected.lng;

          if (lastPosition === key) return;

          lastPosition = key;
          render();
        }
      );

      $("gridVisible").addEventListener("change", () => {
        polygons.forEach(polygon => {
          polygon.setMap(
            $("gridVisible").checked ? map : null
          );
        });
      });

      $("gridReload").addEventListener("click", load);

      $("gridFit").addEventListener("click", () => {
        if (!selectedIds.length) return;

        $("gridVisible").checked = true;
        polygons.forEach(polygon => polygon.setMap(map));

        const bounds = new kakao.maps.LatLngBounds();

        selectedIds.forEach(id => {
          const g = grids.get(id);

          ["sw", "se", "ne", "nw"].forEach(p => {
            bounds.extend(
              new kakao.maps.LatLng(
                g[p + "_lat"],
                g[p + "_lon"]
              )
            );
          });
        });

        map.setBounds(bounds);
      });

      load();
    },

    getState: state,

    getGridId(lat, lng) {
      if (!loaded) return null;
      return gridId(lat, lng);
    },

    retry: load,

    getSelectedIds() {
      return [...selectedIds];
    }
  };
})();