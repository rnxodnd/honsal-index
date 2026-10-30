(() => {
  "use strict";

  const input = document.getElementById("addressInput");
  const form = document.getElementById("searchForm");

  const regionName = document.getElementById("regionName");
  const regionDescription =
    document.getElementById("regionDescription");
  const regionType = document.getElementById("regionType");

  const cityButtons = [
    ...document.querySelectorAll("[data-region]")
  ];

  const explore = document.getElementById("explore");
  const compareView = document.getElementById("compareView");
  const localDataSection =
    document.getElementById("localDataSection");

  const compareCards = document.getElementById("compareCards");
  const compareCount = document.getElementById("compareCount");
  const compareButton = document.getElementById("addCompareBtn");

  const compareNames = [];

  let selected = {
    name: "춘천시",
    description: "춘천시 주변 지도를 살펴보고 있습니다.",
    kind: "지역"
  };

  // 기존 화면 예시입니다. 실제 시설·통계가 아닙니다.
  const datasetByRegion = {
    "춘천시": {
      facilities: [
        {
          name: "편의점 데이터 예시",
          type: "편의점",
          address: "실제 주소 데이터 연결 예정"
        },
        {
          name: "마트 데이터 예시",
          type: "마트",
          address: "실제 주소 데이터 연결 예정"
        }
      ],
      leisure: [
        {
          name: "공원 데이터 예시",
          type: "공원",
          address: "실제 시설 정보 연결 예정"
        },
        {
          name: "문화시설 데이터 예시",
          type: "문화시설",
          address: "실제 시설 정보 연결 예정"
        }
      ]
    },

    "원주시": {
      facilities: [
        {
          name: "생활 편의시설 예시",
          type: "편의시설",
          address: "실제 주소 데이터 연결 예정"
        }
      ],
      leisure: [
        {
          name: "도서관 데이터 예시",
          type: "도서관",
          address: "실제 시설 정보 연결 예정"
        }
      ]
    },

    "강릉시": {
      facilities: [
        {
          name: "마트 데이터 예시",
          type: "마트",
          address: "실제 주소 데이터 연결 예정"
        }
      ],
      leisure: [
        {
          name: "여가시설 데이터 예시",
          type: "여가시설",
          address: "실제 시설 정보 연결 예정"
        }
      ]
    }
  };

  function findDatasetKey(name, description = "") {
    const text = name + " " + description;

    if (text.includes("춘천")) return "춘천시";
    if (text.includes("원주")) return "원주시";
    if (text.includes("강릉")) return "강릉시";

    return null;
  }

  function refreshCityButtons(name) {
    const cityMap = {
      "춘천시": "chuncheon",
      "원주시": "wonju",
      "강릉시": "gangneung"
    };

    const key = cityMap[name];

    cityButtons.forEach(button => {
      button.classList.toggle(
        "active",
        button.dataset.region === key
      );
    });
  }

  function createPoiCard(item) {
    const card = document.createElement("article");
    card.className = "poi-card";

    const top = document.createElement("div");
    top.className = "poi-top";

    const title = document.createElement("strong");
    title.className = "poi-title";
    title.textContent = item.name;

    const type = document.createElement("span");
    type.className = "poi-type";
    type.textContent = item.type;

    top.append(title, type);

    const address = document.createElement("div");
    address.className = "poi-address";
    address.textContent = item.address || "주소 정보 없음";

    card.append(top, address);

    if (item.distance || item.time) {
      const meta = document.createElement("div");
      meta.className = "poi-meta";

      if (item.distance) {
        const distance = document.createElement("span");
        distance.textContent = "📍 " + item.distance;
        meta.append(distance);
      }

      if (item.time) {
        const time = document.createElement("span");
        time.textContent = "⏱ " + item.time;
        meta.append(time);
      }

      card.append(meta);
    }

    return card;
  }

  function renderPoiList(targetId, items, emptyMessage) {
    const target = document.getElementById(targetId);
    target.replaceChildren();

    if (!items || items.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-dataset";
      empty.textContent = emptyMessage;
      target.append(empty);
      return;
    }

    items.forEach(item => {
      target.append(createPoiCard(item));
    });
  }

  function renderInsights(items) {
    const target = document.getElementById("insightBullets");
    target.replaceChildren();

    items.forEach(text => {
      const li = document.createElement("li");
      li.textContent = text;
      target.append(li);
    });
  }

  function renderLocalDataset(name, description = "") {
    const key = findDatasetKey(name, description);
    const dataset = key ? datasetByRegion[key] : null;

    document.getElementById("datasetRegionName").textContent =
      name;

    const facilityCount =
      document.getElementById("facilityCount");
    const leisureCount =
      document.getElementById("leisureCount");
    const infraCount =
      document.getElementById("infraCount");
    const statusText =
      document.getElementById("datasetStatusText");
    const facilityBadge =
      document.getElementById("facilityBadge");
    const leisureBadge =
      document.getElementById("leisureBadge");

    if (!dataset) {
      facilityCount.textContent = "—";
      leisureCount.textContent = "—";
      infraCount.textContent = "—";
      statusText.textContent = "연동 전";

      facilityBadge.textContent = "데이터 없음";
      leisureBadge.textContent = "데이터 없음";

      renderPoiList(
        "facilityList",
        [],
        "이 위치의 편의시설 데이터가 아직 연결되지 않았습니다."
      );

      renderPoiList(
        "leisureList",
        [],
        "이 위치의 여가시설 데이터가 아직 연결되지 않았습니다."
      );

      renderInsights([
        "현재 검색 위치의 실제 시설 데이터가 연결되지 않았습니다.",
        "시설명·주소·좌표가 포함된 데이터셋을 연결하면 이곳에 표시할 수 있습니다."
      ]);

      document.getElementById("datasetSummary").textContent =
        "현재 위치에 연결된 실제 시설 데이터가 없습니다. " +
        "이는 주변에 시설이 없다는 뜻이 아닙니다.";

      return;
    }

    facilityCount.textContent = "—";
    leisureCount.textContent = "—";
    infraCount.textContent = "—";
    statusText.textContent = "데모";

    facilityBadge.textContent = "화면 예시";
    leisureBadge.textContent = "화면 예시";

    renderPoiList(
      "facilityList",
      dataset.facilities,
      "편의시설 데이터가 없습니다."
    );

    renderPoiList(
      "leisureList",
      dataset.leisure,
      "여가시설 데이터가 없습니다."
    );

    renderInsights([
      "현재 표시된 시설 목록은 화면 디자인을 검토하기 위한 예시입니다.",
      "실제 데이터셋이 연결되면 시설 종류, 위치 및 접근 거리를 분석할 예정입니다.",
      "혼살지수 점수는 검증된 분석 데이터가 연결된 이후 표시됩니다."
    ]);

    document.getElementById("datasetSummary").textContent =
      key + "의 생활 환경 데이터 표시 예시입니다. " +
      "실제 주변 시설 개수와 이동 거리는 아직 계산되지 않았습니다. " +
      "향후 선택 위치의 좌표를 기준으로 데이터셋을 조회하도록 연결할 수 있습니다.";
  }

  function selectRegion(location) {
    selected = { ...location };

    regionName.textContent = location.name;
    regionDescription.textContent =
      location.description || "지역 정보 확인 중";

    regionType.textContent =
      location.kind === "지역"
        ? "선택한 지역"
        : "검색한 " + location.kind;

    refreshCityButtons(location.name);
    refreshCompare();

    renderLocalDataset(
      location.name,
      location.description
    );
  }

  document.addEventListener(
    "honsal:selection",
    event => selectRegion(event.detail)
  );

  form.addEventListener("submit", event => {
    event.preventDefault();

    const keyword = input.value.trim();
    if (!keyword) return;

    window.HonsalMap.search(keyword);
  });

  cityButtons.forEach(button => {
    button.addEventListener("click", () => {
      const success = window.HonsalMap.goToRegion(
        button.dataset.region
      );

      if (!success) {
        document.getElementById("searchMessage").textContent =
          "지도가 아직 준비되지 않았습니다.";
      }
    });
  });

  document.getElementById("resetMapBtn")
    .addEventListener("click", () => {
      window.HonsalMap.wholeGangwon();
    });

  document.getElementById("zoomIn")
    .addEventListener("click", () => {
      window.HonsalMap.zoom(-1);
    });

  document.getElementById("zoomOut")
    .addEventListener("click", () => {
      window.HonsalMap.zoom(1);
    });

  function renderCompare() {
    compareCards.replaceChildren();

    [compareNames[0], compareNames[1]].forEach((name, index) => {
      const card = document.createElement("div");
      card.className = "compare-card";

      const label = document.createElement("span");
      label.className = "eyebrow";
      label.textContent = "비교 지역 " + (index + 1);

      const title = document.createElement("h3");
      title.textContent = name || "지역을 추가해 주세요";

      const description = document.createElement("p");
      description.textContent = name
        ? "선택한 지역입니다. 실제 점수 비교는 데이터 연동 후 제공됩니다."
        : "지도에서 지역을 선택하고 비교 목록에 추가하세요.";

      card.append(label, title, description);

      if (name) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "remove-compare";
        remove.textContent = "목록에서 제거";

        remove.addEventListener("click", () => {
          const idx = compareNames.indexOf(name);

          if (idx !== -1) {
            compareNames.splice(idx, 1);
          }

          refreshCompare();
        });

        card.append(remove);
      }

      compareCards.append(card);
    });
  }

  function refreshCompare() {
    compareCount.textContent = String(compareNames.length);

    compareButton.textContent =
      compareNames.includes(selected.name)
        ? "✓ 비교 목록에 추가됨"
        : "＋ 비교 목록에 추가";

    renderCompare();
  }

  compareButton.addEventListener("click", () => {
    if (compareNames.includes(selected.name)) return;

    if (compareNames.length >= 2) {
      compareButton.textContent =
        "최대 2개까지 비교할 수 있습니다.";
      return;
    }

    compareNames.push(selected.name);
    refreshCompare();
  });

  function switchView(view) {
    if (!["explore", "compare", "routes"].includes(view)) {
      return;
    }

    const isCompare = view === "compare";

    explore.hidden = view !== "explore";
    compareView.hidden = !isCompare;
    localDataSection.hidden = view !== "explore";

    document.getElementById("routesView").hidden =
      view !== "routes";

    document.querySelectorAll("[data-view]").forEach(button => {
      button.classList.toggle(
        "active",
        button.dataset.view === view
      );
    });

    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });

    if (isCompare) {
      renderCompare();
    } else if (view === "explore") {
      window.setTimeout(() => {
        window.HonsalMap.relayout();
      }, 100);
    }
  }

  window.HonsalUI = { switchView };

  document.querySelector(".brand")
    ?.addEventListener("click", event => {
      event.preventDefault();
      switchView("explore");
    });

  document.querySelectorAll("[data-view]").forEach(button => {
    button.addEventListener("click", () => {
      switchView(button.dataset.view);
    });
  });

  document.getElementById("backToMap")
    .addEventListener("click", () => {
      switchView("explore");
    });

  const interests = document.querySelectorAll(
    'input[name="interest"]'
  );

  interests.forEach(checkbox => {
    checkbox.addEventListener("change", () => {
      const selectedInterests = [...interests]
        .filter(item => item.checked)
        .map(item => item.value);

      document.getElementById("searchMessage").textContent =
        selectedInterests.length
          ? "선택한 관심 요소: " +
            selectedInterests.join(", ") +
            " (추천 점수 미반영)"
          : "관심 요소를 선택할 수 있습니다.";
    });
  });

  refreshCompare();

  if (window.HonsalMap?.getSelected) {
    selectRegion(window.HonsalMap.getSelected());
  } else {
    selectRegion(selected);
  }
})();

/* 병원·약국 메뉴 */
(() => {
  "use strict";

  const panel = document.querySelector(".filter-panel");

  if (!panel || document.getElementById("medicalFilterGroup")) {
    return;
  }

  function make(tag, text = "", className = "") {
    const element = document.createElement(tag);
    element.textContent = text;
    element.className = className;
    return element;
  }

  const medical = make("details", "", "facility-group");
  medical.id = "medicalFilterGroup";
  medical.open = true;

  const summary = make("summary", "병원·약국");
  const summaryCount = make("span", "데이터 확인 중");
  summary.append(summaryCount);

  const note = make(
    "p",
    "의료 데이터를 불러오는 중입니다.",
    "microcopy"
  );

  note.style.padding = "0 14px";
  note.setAttribute("role", "status");

  const options = make("div", "", "facility-options");

  const selection = make(
    "p",
    "선택한 의료시설 없음",
    "facility-filter-status"
  );

  selection.style.margin = "10px";
  selection.setAttribute("role", "status");
  selection.setAttribute("aria-live", "polite");

  const retry = make(
    "button",
    "다시 불러오기",
    "filter-reset"
  );

  retry.type = "button";
  retry.style.margin = "0 10px 10px";
  retry.hidden = true;

  medical.append(
    summary,
    note,
    options,
    selection,
    retry
  );

  const transport = document.getElementById("transportFilters");

  if (transport) {
    transport.before(medical);
  } else {
    panel.append(medical);
  }

  function getSelected() {
    return [...options.querySelectorAll("input:checked")]
      .map(input => input.value);
  }

  function updateSelection() {
    const selected = getSelected();

    selection.textContent = selected.length
      ? `의료시설 ${selected.length}개 유형 선택 · 지도 필터 미적용`
      : "선택한 의료시설 없음 · 지도 필터 미적용";

    document.dispatchEvent(
      new CustomEvent("honsal:medical-filters", {
        detail: {
          selected,
          applied: false
        }
      })
    );
  }

  document.getElementById("clearFacilityFilters")
    ?.addEventListener("click", () => {
      options.querySelectorAll("input").forEach(input => {
        input.checked = false;
      });

      updateSelection();
    });

  window.HonsalMedicalFilters = {
    getSelected
  };

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = "";
    let quoted = false;

    text = text.replace(/^\uFEFF/, "");

    for (let i = 0; i < text.length; i++) {
      const c = text[i];

      if (c === '"') {
        if (quoted && text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          quoted = !quoted;
        }
      } else if (c === "," && !quoted) {
        row.push(field);
        field = "";
      } else if ((c === "\n" || c === "\r") && !quoted) {
        if (c === "\r" && text[i + 1] === "\n") i++;

        row.push(field);

        if (row.some(value => value.trim())) {
          rows.push(row);
        }

        row = [];
        field = "";
      } else {
        field += c;
      }
    }

    if (quoted) {
      throw new Error("CSV 따옴표 형식 오류");
    }

    row.push(field);

    if (row.some(value => value.trim())) {
      rows.push(row);
    }

    const header =
      rows.shift()?.map(value => value.trim()) || [];

    const idIndex = header.indexOf("facility_id");
    const typeIndex = header.indexOf("facility_type");

    if (idIndex < 0 || typeIndex < 0) {
      throw new Error("필수 컬럼이 없습니다.");
    }

    const seen = new Set();
    const counts = new Map();

    for (const values of rows) {
      if (values.length !== header.length) {
        throw new Error("CSV 열 개수 오류");
      }

      const id = values[idIndex].trim();
      const type = values[typeIndex].trim();

      if (!id || !type) {
        throw new Error(
          "시설 ID 또는 시설 분류가 비어 있습니다."
        );
      }

      if (seen.has(id)) continue;

      seen.add(id);
      counts.set(type, (counts.get(type) || 0) + 1);
    }

    if (!seen.size) {
      throw new Error("시설 데이터가 없습니다.");
    }

    return {
      counts,
      total: seen.size
    };
  }

  async function load() {
    retry.disabled = true;
    summaryCount.textContent = "데이터 확인 중";
    note.textContent = "의료 데이터를 불러오는 중입니다.";

    const controller = new AbortController();

    const timer = setTimeout(() => {
      controller.abort();
    }, 15000);

    try {
      const response = await fetch(
        "./data/chuncheon_medical_facilities.csv",
        { signal: controller.signal }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const { counts, total } = parseCSV(
        await response.text()
      );

      options.replaceChildren();

      const order = [
        "종합병원",
        "병원",
        "의원",
        "치과의원",
        "한방병원",
        "한의원",
        "요양병원",
        "정신병원",
        "보건소",
        "보건지소",
        "보건진료소",
        "약국"
      ];

      const types = [...counts.keys()].sort((a, b) => {
        const rank = value =>
          order.includes(value)
            ? order.indexOf(value)
            : order.length;

        return rank(a) - rank(b) ||
          a.localeCompare(b, "ko");
      });

      types.forEach(type => {
        const label = make("label");
        const input = document.createElement("input");

        input.type = "checkbox";
        input.name = "medicalInterest";
        input.value = type;
        input.addEventListener("change", updateSelection);

        label.append(
          input,
          make("span", `${type} (${counts.get(type)}곳)`)
        );

        options.append(label);
      });

      summaryCount.textContent = `${counts.size}개 유형`;

      note.textContent =
        `첨부 CSV 전체 ${total}곳 기준입니다. ` +
        "괄호의 숫자는 선택 위치 주변 시설 수가 아닙니다. " +
        "현재는 유형 선택만 가능하며 지도 필터는 아직 적용되지 않습니다.";

      retry.hidden = true;
      updateSelection();
    } catch (error) {
      summaryCount.textContent = "데이터 로드 실패";

      const reason = error.name === "AbortError"
        ? "요청 시간 초과"
        : error.message;

      note.textContent =
        reason +
        " · app/data/chuncheon_medical_facilities.csv " +
        "파일과 Live Server 실행을 확인하세요.";

      retry.hidden = false;
    } finally {
      clearTimeout(timer);
      retry.disabled = false;
    }
  }

  retry.addEventListener("click", load);
  load();
})();

/* 생활 분석 항목 정리·시설 메뉴 글꼴 통일 */
(() => {
  "use strict";

  function applyChanges() {
    const factorsCard = document.querySelector(".factors-card");

    if (factorsCard) {
      const factorList = factorsCard.querySelector(".factor-list");

      if (factorList) {
        [...factorList.children].forEach(row => {
          const name = row.querySelector("span")?.textContent.trim();

          if (name === "안전" || name === "주거 부담") {
            row.remove();
          }
        });

        const countLabel = factorsCard.querySelector(
          ".section-row .small-muted"
        );

        if (countLabel) {
          countLabel.textContent =
            `${factorList.children.length}개 지표`;
        }
      }
    }

    const styleId = "honsal-facility-font-unify";
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;

    style.textContent = `
      .filter-panel .facility-group {
        font-family: "Noto Sans KR", sans-serif;
      }

      .filter-panel .facility-group > summary {
        font-family: inherit;
        font-size: 14px;
        font-weight: 700;
        line-height: 1.5;
      }

      .filter-panel .facility-group > summary > span {
        display: inline-block;
        margin-left: 8px;
        font-family: inherit;
        font-size: 12px;
        font-weight: 400;
        color: #75867d;
      }

      .filter-panel .facility-group .facility-options {
        display: grid;
        gap: 3px;
        padding: 8px;
      }

      .filter-panel .facility-group .facility-options > label {
        display: flex;
        align-items: flex-start;
        gap: 9px;
        box-sizing: border-box;
        min-height: 38px;
        margin: 0;
        padding: 9px 7px;
        border-radius: 7px;
        color: #42564c;
        font-family: inherit;
        font-size: 13px;
        font-weight: 400;
        line-height: 1.5;
        cursor: pointer;
      }

      .filter-panel .facility-group .facility-options > label:hover {
        background: #f1f7f3;
      }

      .filter-panel .facility-group .facility-options > label > span {
        font-family: inherit;
        font-size: inherit;
        font-weight: inherit;
        line-height: inherit;
        color: inherit;
      }

      .filter-panel .facility-group .facility-options input[type="checkbox"] {
        flex: 0 0 auto;
        width: 15px;
        height: 15px;
        margin: 2px 0 0;
        accent-color: #147955;
      }
    `;

    document.head.append(style);
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      applyChanges,
      { once: true }
    );
  } else {
    applyChanges();
  }
})();