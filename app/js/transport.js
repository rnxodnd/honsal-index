/* 춘천 버스 정류장·노선
   인증키 없이 저장된 공공데이터 파일을 읽습니다. */
(() => {
  "use strict";

  const $ = id => document.getElementById(id);

  let dataset = null;
  let loading = false;
  let errorMessage = "";

  let stops = new Map();
  let routes = new Map();
  let stopRoutes = new Map();

  let scopedStops = [];
  let scopedIds = new Set();
  let localNumbers = [];
  let overlays = [];

  let activeStop = null;
  let activeNumber = null;
  let activeRouteId = null;

  let grid = {
    phase: "idle",
    ids: [],
    message: ""
  };

  function element(tag, text = "", className = "") {
    const el = document.createElement(tag);
    el.textContent = text;
    el.className = className;
    return el;
  }

  function sortNumbers(values) {
    return [...new Set(values)].sort((a, b) => {
      return a.localeCompare(b, "ko", {
        numeric: true
      });
    });
  }

  function numbersForStop(id) {
    return sortNumbers(
      [...(stopRoutes.get(id) || [])].map(key => {
        return routes.get(key).number;
      })
    );
  }

  function makeNumber(number, handler) {
    const button = element(
      "button",
      number,
      "bus-number"
    );

    button.type = "button";

    button.setAttribute(
      "aria-label",
      number + "번 버스 노선 보기"
    );

    button.addEventListener("click", () => {
      handler(number);
    });

    return button;
  }

  function openRoute(number) {
    activeNumber = number;
    activeRouteId = null;

    $("routeSearch").value = "";
    $("routeScope").value = "local";

    window.HonsalUI.switchView("routes");

    renderRoutePicker();
    renderRouteDetail();

    $("routeDetailTitle").focus({
      preventScroll: true
    });
  }

  function clearMarkers() {
    overlays.forEach(item => {
      item.overlay.setMap(null);
    });

    overlays = [];
  }

  function renderMarkers() {
    clearMarkers();

    const map = window.HonsalMap?.getMap();

    if (!map || !$("showBusStops").checked) return;

    scopedStops.forEach(stop => {
      const button = element(
        "button",
        "버스",
        "bus-map-marker"
      );

      button.type = "button";
      button.title = stop.name;

      button.setAttribute(
        "aria-label",
        stop.name + " 정류장 경유 버스 보기"
      );

      button.setAttribute(
        "aria-pressed",
        String(activeStop === stop.id)
      );

      button.addEventListener("click", event => {
        event.stopPropagation();
        selectStop(stop.id);
      });

      const overlay = new kakao.maps.CustomOverlay({
        map,
        position: new kakao.maps.LatLng(
          stop.lat,
          stop.lng
        ),
        content: button,
        clickable: true,
        yAnchor: 1,
        zIndex: 5
      });

      overlays.push({
        overlay,
        button,
        id: stop.id
      });
    });
  }

  function selectStop(id) {
    // 정류장을 선택해도 3×3 기준점은 유지합니다.
    if (!scopedIds.has(id)) return;

    activeStop = id;

    const stop = stops.get(id);

    window.HonsalMap?.focusTransport(
      stop.lat,
      stop.lng
    );

    renderSelectedStop();

    overlays.forEach(item => {
      item.button.setAttribute(
        "aria-pressed",
        String(item.id === id)
      );
    });
  }

  function renderSelectedStop() {
    const panel = $("selectedBusStop");
    panel.replaceChildren();

    const stop = stops.get(activeStop);

    panel.hidden =
      !stop || !scopedIds.has(activeStop);

    if (panel.hidden) return;

    panel.append(element("strong", stop.name));

    panel.append(
      element(
        "p",
        "정류장 ID " + stop.id,
        "transport-note"
      )
    );

    const numbers = numbersForStop(stop.id);
    const list = element("div", "", "bus-number-list");

    numbers.forEach(number => {
      list.append(makeNumber(number, openRoute));
    });

    panel.append(list);

    if (!numbers.length) {
      panel.append(
        element(
          "p",
          "원본 노선정보 확인 중입니다.",
          "transport-note"
        )
      );
    }

    if (stop.revised) {
      panel.append(
        element(
          "p",
          "이름·좌표는 가장 최근 기준일의 정류장 정보를 사용합니다.",
          "transport-note"
        )
      );
    }
  }

  function renderLocalStops() {
    const target = $("localBusStops");
    target.replaceChildren();

    scopedStops.forEach(stop => {
      const button = element(
        "button",
        stop.name + " · " + stop.id,
        "bus-stop-button"
      );

      button.type = "button";

      button.addEventListener("click", () => {
        selectStop(stop.id);
      });

      target.append(button);
    });
  }

  function gridMessage() {
    if (grid.phase === "outside") {
      return "격자 데이터 제공 범위 밖입니다. 춘천의 다른 위치를 선택하세요.";
    }

    if (grid.phase === "error") {
      return "격자 데이터를 불러오지 못했습니다. 다시 불러오기를 눌러 주세요.";
    }

    if (grid.phase !== "ready") {
      return "선택 위치의 격자를 확인하고 있습니다.";
    }

    return "";
  }

  function refresh() {
    grid = window.HonsalGrid?.getState() || grid;

    scopedStops = [];
    scopedIds = new Set();
    localNumbers = [];

    let message = loading
      ? "교통 데이터를 불러오는 중입니다."
      : errorMessage;

    if (!message) {
      message = gridMessage();
    }

    if (dataset && !message) {
      const selectedGrids = new Set(grid.ids);

      scopedStops = [...stops.values()].filter(stop => {
        return selectedGrids.has(stop.gridId);
      });

      scopedStops.sort((a, b) => {
        return (
          a.name.localeCompare(b.name, "ko") ||
          a.id.localeCompare(b.id)
        );
      });

      scopedIds = new Set(
        scopedStops.map(stop => stop.id)
      );

      localNumbers = sortNumbers(
        scopedStops.flatMap(stop => {
          return numbersForStop(stop.id);
        })
      );

      message = scopedStops.length
        ? `정류장 ${scopedStops.length}곳 · 경유 버스 번호 ${localNumbers.length}개`
        : "선택한 생활권에 등록된 버스정류장이 없습니다.";

      if (grid.ids.length < 9) {
        message +=
          ` · 경계 지역: 제공된 ${grid.ids.length}/9칸 기준`;
      }
    }

    if (!scopedIds.has(activeStop)) {
      activeStop = null;
    }

    $("transportStatus").textContent = message;

    $("transportFilterStatus").textContent =
      scopedStops.length
        ? $("showBusStops").checked
          ? "생활권 정류장 표시 중"
          : "지도 정류장 표시 꺼짐"
        : message;

    $("transportRetry").hidden =
      !(errorMessage || grid.phase === "error");

    $("transportRetry").disabled = loading;

    $("busNumbers").replaceChildren(
      ...localNumbers.map(number => {
        return makeNumber(number, openRoute);
      })
    );

    renderLocalStops();
    renderMarkers();
    renderSelectedStop();
    renderRoutePicker();
    renderRouteDetail();
  }

  function renderRoutePicker() {
    const all = $("routeScope").value === "all";

    const query = $("routeSearch")
      .value.trim()
      .toLocaleLowerCase();

    const available = all
      ? sortNumbers(
          [...routes.values()].map(route => route.number)
        )
      : localNumbers;

    const numbers = available.filter(number => {
      return number.toLocaleLowerCase().includes(query);
    });

    const target = $("routeNumbers");
    target.replaceChildren();

    numbers.forEach(number => {
      const button = makeNumber(number, value => {
        activeNumber = value;
        activeRouteId = null;

        renderRoutePicker();
        renderRouteDetail();

        $("routeDetailTitle").focus({
          preventScroll: true
        });
      });

      button.setAttribute(
        "aria-pressed",
        String(number === activeNumber)
      );

      target.append(button);
    });

    $("routePickerStatus").textContent =
      loading
        ? "버스 데이터 로딩 중…"
        : errorMessage ||
          (
            !all && grid.phase !== "ready"
              ? gridMessage()
              : numbers.length
                ? `버스 번호 ${numbers.length}개 · 원본 자료 기준`
                : "조건에 맞는 버스 번호가 없습니다."
          );
  }

  function renderRouteDetail() {
    const list = $("routeStopList");
    const variant = $("routeVariant");

    list.replaceChildren();
    variant.replaceChildren();

    variant.hidden = true;
    $("routeVariantLabel").hidden = true;

    const candidates = [...routes.values()].filter(route => {
      return route.number === activeNumber;
    });

    if (!candidates.length) {
      $("routeDetailTitle").textContent =
        "버스 번호를 선택하세요.";

      $("routeDetailNote").textContent =
        "실시간 도착 정보와 도로를 따라가는 경로는 제공하지 않습니다.";

      return;
    }

    candidates.sort((a, b) => {
      return a.id.localeCompare(b.id);
    });

    const route =
      candidates.find(item => item.id === activeRouteId) ||
      candidates[0];

    activeRouteId = route.id;

    candidates.forEach(item => {
      const first = item.stops[0].name;
      const last = item.stops[item.stops.length - 1].name;

      const option = element(
        "option",
        `${first} → ${last} · 노선 ID ${item.id}`
      );

      option.value = item.id;
      variant.append(option);
    });

    variant.value = route.id;
    variant.hidden = candidates.length === 1;

    $("routeVariantLabel").hidden =
      candidates.length === 1;

    $("routeDetailTitle").textContent =
      route.number + "번 버스";

    const inScope = route.stops.some(stop => {
      return scopedIds.has(stop.id);
    });

    $("routeDetailNote").textContent =
      `정차 순서 ${route.stops.length}개 · 기준일 ${route.dates.join(", ")} · 노선 ID ${route.id}` +
      (
        inScope
          ? " · 초록색은 현재 생활권 안 정류장입니다."
          : " · 현재 생활권을 경유하지 않거나 격자 범위 확인 전입니다."
      );

    route.stops.forEach(visit => {
      const inside = scopedIds.has(visit.id);

      const item = element(
        "li",
        visit.name,
        inside ? "in-scope" : ""
      );

      item.value = visit.order;

      item.append(
        element(
          "small",
          `정류장 ID ${visit.id} · ${
            inside
              ? "3×3 생활권 안"
              : "생활권 밖 또는 범위 확인 전"
          }`
        )
      );

      if (inside) {
        const button = element(
          "button",
          "지도에서 보기",
          "detail-small-button"
        );

        button.type = "button";

        button.addEventListener("click", () => {
          window.HonsalUI.switchView("explore");

          $("showBusStops").checked = true;

          renderMarkers();
          window.HonsalMap.relayout();
          selectStop(visit.id);

          $("transportFilterStatus").textContent =
            "생활권 정류장 표시 중";

          $("transportCard").scrollIntoView({
            block: "nearest"
          });
        });

        item.append(button);
      }

      list.append(item);
    });
  }

  function validate(data) {
    if (
      data.version !== 1 ||
      !Array.isArray(data.stops) ||
      !Array.isArray(data.routes) ||
      !data.meta
    ) {
      throw new Error(
        "교통 데이터 형식이 올바르지 않습니다."
      );
    }

    const ids = new Set();

    for (const stop of data.stops) {
      if (
        !stop.id ||
        ids.has(stop.id) ||
        !stop.name ||
        !Number.isFinite(stop.lat) ||
        !Number.isFinite(stop.lng) ||
        Math.abs(stop.lat) > 90 ||
        Math.abs(stop.lng) > 180
      ) {
        throw new Error("정류장 데이터 오류");
      }

      ids.add(stop.id);
    }

    const routeIds = new Set();

    for (const route of data.routes) {
      if (
        !route.id ||
        routeIds.has(route.id) ||
        !route.number ||
        !Array.isArray(route.stops) ||
        !route.stops.length ||
        !Array.isArray(route.dates)
      ) {
        throw new Error("노선 데이터 오류");
      }

      routeIds.add(route.id);

      let order = -Infinity;

      for (const visit of route.stops) {
        if (
          !ids.has(visit.id) ||
          !visit.name ||
          !Number.isFinite(visit.order) ||
          visit.order <= order
        ) {
          throw new Error("노선 정류장 순서 오류");
        }

        order = visit.order;
      }
    }

    return data;
  }

  function indexGrids() {
    if (
      !dataset ||
      !["ready", "outside"].includes(
        window.HonsalGrid?.getState().phase
      )
    ) {
      return;
    }

    stops.forEach(stop => {
      if (!stop.gridId) {
        stop.gridId = window.HonsalGrid.getGridId(
          stop.lat,
          stop.lng
        );
      }
    });
  }

  async function load() {
    if (loading) return;

    loading = true;
    errorMessage = "";
    refresh();

    const controller = new AbortController();

    const timer = setTimeout(() => {
      controller.abort();
    }, 15000);

    try {
      const response = await fetch(
        "./data/chuncheon_bus.json",
        { signal: controller.signal }
      );

      if (!response.ok) {
        throw new Error(
          `교통 데이터 요청 실패 (HTTP ${response.status})`
        );
      }

      dataset = validate(await response.json());

      stops = new Map(
        dataset.stops.map(stop => {
          return [stop.id, { ...stop }];
        })
      );

      routes = new Map(
        dataset.routes.map(route => {
          return [route.id, route];
        })
      );

      stopRoutes = new Map();

      routes.forEach(route => {
        route.stops.forEach(stop => {
          if (!stopRoutes.has(stop.id)) {
            stopRoutes.set(stop.id, new Set());
          }

          stopRoutes.get(stop.id).add(route.id);
        });
      });

      indexGrids();

      $("transportSource").textContent =
        `춘천시 공공데이터 · 기준일 ${dataset.meta.dates.join(", ")} · 저장된 자료이며 실시간 정보가 아닙니다.`;

      const withheld =
        dataset.meta.withheldRoutes || [];

      $("transportDataWarning").hidden =
        !withheld.length;

      $("transportDataWarning").textContent =
        withheld.length
          ? `원본에서 노선번호가 서로 다른 노선 ID ${withheld.length}건은 표시를 보류했습니다. 경유 버스 목록에 일부 누락이 있을 수 있습니다.`
          : "";
    } catch (error) {
      dataset = null;

      stops.clear();
      routes.clear();
      stopRoutes.clear();

      errorMessage =
        error.name === "AbortError"
          ? "교통 데이터 요청 시간이 초과되었습니다."
          : error.message +
            " · app/data/chuncheon_bus.json 파일을 확인하세요.";
    } finally {
      clearTimeout(timer);
      loading = false;
      refresh();
    }
  }

  document.addEventListener("honsal:grid", () => {
    indexGrids();
    refresh();
  });

  document.addEventListener("honsal:ready", () => {
    indexGrids();
    refresh();
  });

  $("showBusStops").addEventListener(
    "change",
    refresh
  );

  $("transportRetry").addEventListener("click", () => {
    if (
      window.HonsalGrid?.getState().phase === "error"
    ) {
      window.HonsalGrid.retry();
    }

    if (!dataset) load();
  });

  $("routeSearch").addEventListener(
    "input",
    renderRoutePicker
  );

  $("routeScope").addEventListener(
    "change",
    renderRoutePicker
  );

  $("routeVariant").addEventListener("change", () => {
    activeRouteId = $("routeVariant").value;
    renderRouteDetail();
  });

  load();
})();