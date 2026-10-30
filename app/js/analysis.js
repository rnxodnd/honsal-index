(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const API_BASE = String(window.HONSAL_API_BASE_URL || "").replace(/\/$/, "");
  const categories = {
    daily_life: {label: "편의시설", options: "convenienceOptions", list: "facilityList", count: "facilityCount", badge: "facilityBadge"},
    healthcare: {label: "의료시설", options: "medicalOptions", list: "healthcareList", count: "infraCount", badge: "healthcareBadge"},
    transport: {label: "교통시설", options: "transportOptions", list: "transportList", count: "transportCount", badge: "transportBadge"},
    leisure_community: {label: "여가시설", options: "leisureOptions", list: "leisureList", count: "leisureCount", badge: "leisureBadge"}
  };
  let options = null;
  let optionsLoading = true;
  let optionsError = null;
  let controller = null;
  let timer = null;
  let generation = 0;
  let lastResult = null;
  let state = "loading";

  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  function selectedTypes(key) {
    return Array.from($(categories[key].options).querySelectorAll("input:checked"), input => input.value);
  }
  function getSelection() {
    return Object.fromEntries(Object.keys(categories).map(key => [key, selectedTypes(key)]));
  }
  function selectionCount(selected) {
    return Object.values(selected).reduce((total, values) => total + values.length, 0);
  }
  function emitState(status, result = null) {
    state = status;
    document.dispatchEvent(new CustomEvent("honsal:analysis", {detail: {status, result}}));
  }

  function clearResults(message, status = "idle") {
    lastResult = null;
    $("analysisScore").textContent = "—";
    document.querySelector(".score-circle").classList.remove("is-ready");
    $("analysisState").textContent = status === "error" ? "분석 오류" : status === "loading" ? "분석 중" : "시설 선택 대기";
    $("analysisTitle").textContent = status === "error" ? "분석 결과를 확인할 수 없습니다" : status === "loading" ? "선택한 시설 분석 중" : "시설을 선택해 주세요";
    $("analysisDescription").textContent = "점수는 격자 중심에서 시설까지의 직선거리로 계산합니다.";
    $("analysisStatus").textContent = message;
    $("analysisStatus").classList.toggle("is-error", status === "error");
    $("localDataSection").setAttribute("aria-busy", String(status === "loading"));
    $("dataSourceBadge").textContent = status === "error" ? "자료 확인 필요" : status === "loading" ? "계산 중" : "시설 선택 대기";
    Object.entries(categories).forEach(([key, config]) => {
      $(config.count).textContent = "—";
      $(config.badge).textContent = "—";
      $(config.list).replaceChildren(node("p", message, "empty-dataset"));
      const row = document.querySelector(`#categoryScores [data-category="${key}"]`);
      row.querySelector("em").textContent = "—";
      row.querySelector("small").textContent = "결과 대기";
      row.querySelector("i").style.width = "0%";
    });
    $("insightBullets").replaceChildren(node("li", message));
    $("datasetSummary").textContent = message;
    window.HonsalMap?.clearAnalysis?.();
    emitState(status);
  }

  function renderFacility(facility) {
    // 이름·분류·좌표가 같아도 시설 ID가 다르면 각각의 카드로 표시합니다.
    const card = node("article", undefined, "poi-card");
    card.dataset.facilityId = facility.facility_id;
    const top = node("div", undefined, "poi-top");
    const name = node("div", undefined, "poi-name");
    name.append(node("small", "상호명", "business-name-label"), node("strong", facility.name, "poi-title"));
    top.append(name, node("span", facility.subtype, "poi-type"));
    card.append(top, node("div", facility.address || "주소 정보 없음", "poi-address"));
    const meta = node("div", undefined, "poi-meta");
    meta.append(node("span", `격자 중심 직선거리 ${Math.round(facility.distance_m).toLocaleString("ko-KR")}m`));
    card.append(meta);
    card.append(node("small", facility.phone ? `전화번호 ${facility.phone}` : "전화번호 정보 없음", "facility-phone"));
    if (facility.in_city_boundary === false) card.append(node("small", "춘천 행정경계 밖의 인근 시설", "facility-boundary-note"));
    return card;
  }

  function renderResult(result, selected) {
    lastResult = result;
    $("analysisScore").textContent = result.total_score === null ? "—" : result.total_score.toFixed(1);
    document.querySelector(".score-circle").classList.add("is-ready");
    $("analysisState").textContent = "분석 완료";
    $("analysisTitle").textContent = "선택한 시설 기준 혼살지수";
    $("analysisDescription").textContent = `주변 3×3 격자 · 선택 시설 ${result.facilities.length.toLocaleString("ko-KR")}곳`;
    $("analysisStatus").textContent = "위치나 시설 선택을 바꾸면 자동으로 다시 계산합니다.";
    $("analysisStatus").classList.remove("is-error");
    $("localDataSection").setAttribute("aria-busy", "false");
    $("datasetRegionName").textContent = result.location.name || "선택한 위치";
    $("dataSourceBadge").textContent = `선택 시설 총 ${result.facilities.length.toLocaleString("ko-KR")}곳`;

    Object.entries(categories).forEach(([key, config]) => {
      const facilities = result.facilities.filter(facility => facility.category === key);
      const isSelected = selected[key].length > 0;
      $(config.count).textContent = isSelected ? facilities.length.toLocaleString("ko-KR") : "미선택";
      $(config.badge).textContent = isSelected ? `${facilities.length.toLocaleString("ko-KR")}곳` : "미선택";
      const list = $(config.list);
      list.replaceChildren();
      if (!facilities.length) {
        list.append(node("p", isSelected ? "주변 3×3 격자 안에 선택한 종류의 시설이 없습니다." : `${config.label} 유형을 선택하면 해당 시설을 모두 표시합니다.`, "empty-dataset"));
      } else {
        const fragment = document.createDocumentFragment();
        facilities.forEach(facility => fragment.append(renderFacility(facility)));
        list.append(fragment);
      }
    });
    result.categories.forEach(category => {
      const row = document.querySelector(`#categoryScores [data-category="${category.key}"]`);
      if (!row) return;
      row.querySelector("em").textContent = category.score === null ? "—" : category.score.toFixed(1);
      row.querySelector("small").textContent = category.score === null ? "미선택" : `적용 비중 ${(category.weight * 100).toFixed(1)}%`;
      row.querySelector("i").style.width = `${category.score ?? 0}%`;
    });
    const insights = result.types.map(type => node("li", `${type.subtype}: ${type.count_3x3}곳 · 유형 점수 ${type.score.toFixed(1)}점`));
    insights.push(...result.notices.map(notice => node("li", notice)));
    $("insightBullets").replaceChildren(...insights);
    $("datasetSummary").replaceChildren(
      node("p", `${result.grid.adm_nm || "춘천시"} · ${result.grid.grid_id}`),
      node("p", `선택한 ${selectionCount(selected)}개 시설 유형의 ${result.facilities.length.toLocaleString("ko-KR")}곳을 모두 표시했습니다. 시설 수는 주변 3×3 격자의 개수이며, 750m보다 먼 모서리의 시설도 목록에 포함될 수 있습니다.`),
      node("p", "같은 상호명·유형·좌표의 서로 다른 시설은 각각 표시합니다. 점수는 유형별 가장 가까운 시설의 거리로 계산하며, 시설 수를 점수로 합산하지 않습니다.")
    );
    try { window.HonsalMap?.renderAnalysis?.(result); }
    catch (error) { console.warn("시설 지도 표시를 완료하지 못했습니다.", error); }
    emitState("success", result);
  }

  async function analyze(id, selected) {
    if (id !== generation) return;
    const location = window.HonsalMap?.getSelected?.() || options.default_location;
    const lon = location.lng ?? location.lon;
    const lat = location.lat;
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      clearResults("분석할 위치를 선택해 주세요.", "error");
      return;
    }
    controller = new AbortController();
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST", headers: {"Content-Type": "application/json"}, credentials: "omit",
        body: JSON.stringify({lon, lat, name: location.name || "선택한 위치", selected}),
        signal: controller.signal
      });
      const result = await response.json();
      if (id !== generation) return;
      if (!response.ok) throw new Error(result.error?.message || "분석 요청에 실패했습니다.");
      renderResult(result, selected);
    } catch (error) {
      if (error.name === "AbortError" || id !== generation) return;
      clearResults(error instanceof TypeError ? "분석 서버에 연결할 수 없습니다. 서버 실행 상태를 확인한 뒤 다시 분석해 주세요." : error.message, "error");
    } finally {
      if (id === generation) controller = null;
    }
  }

  function schedule(reason = "location") {
    generation += 1;
    clearTimeout(timer);
    controller?.abort();
    controller = null;
    if (reason === "selection") document.dispatchEvent(new CustomEvent("honsal:filters-changed"));
    const selected = getSelection();
    const count = selectionCount(selected);
    $("facilityFilterStatus").textContent = count
      ? Object.entries(selected).filter(([,values]) => values.length).map(([key,values]) => `${categories[key].label} ${values.length}종`).join(" · ")
      : "분석할 시설을 하나 이상 선택하세요.";
    if (!options) {
      clearResults(optionsLoading ? "시설 목록을 불러오는 중입니다." : optionsError,
        optionsLoading ? "loading" : "error");
      return;
    }
    if (!count) {
      clearResults("분석할 시설을 하나 이상 선택하세요.");
      return;
    }
    clearResults("선택한 시설의 거리와 개수를 계산하고 있습니다.", "loading");
    const id = generation;
    timer = setTimeout(() => analyze(id, selected), 300);
  }

  function renderOptions(data) {
    Object.values(categories).forEach(category => $(category.options).replaceChildren());
    data.categories.forEach(category => {
      const config = categories[category.key];
      if (!config) return;
      category.subtypes.forEach(subtype => {
        const label = node("label", undefined, "facility-option");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = "analysisFacility";
        input.value = subtype.name;
        input.dataset.category = category.key;
        input.addEventListener("change", () => schedule("selection"));
        label.append(input, node("span", `${subtype.name} (${subtype.facility_count.toLocaleString("ko-KR")})`));
        $(config.options).append(label);
      });
    });
  }

  async function loadOptions() {
    optionsLoading = true;
    optionsError = null;
    $("analysisRetry").disabled = true;
    clearResults("시설 목록을 불러오는 중입니다.", "loading");
    try {
      const response = await fetch(`${API_BASE}/api/options`, {credentials: "omit"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.message || "시설 목록을 불러오지 못했습니다.");
      options = data;
      optionsLoading = false;
      renderOptions(data);
      schedule("initial");
    } catch (error) {
      optionsLoading = false;
      optionsError = "시설 목록을 불러오지 못했습니다. API 서버를 확인하고 다시 분석 버튼을 눌러주세요.";
      clearResults(optionsError, "error");
    } finally {
      $("analysisRetry").disabled = false;
    }
  }

  window.HonsalFacilityFilters = {getSelected: () => [
    ...selectedTypes("daily_life").map(category => ({group: "편의시설", category})),
    ...selectedTypes("leisure_community").map(category => ({group: "여가시설", category}))
  ]};
  window.HonsalMedicalFilters = {getSelected: () => selectedTypes("healthcare")};
  window.HonsalTransportFilters = {getSelected: () => selectedTypes("transport")};
  window.HonsalAnalysis = {getResult: () => lastResult, getState: () => state};

  $("clearFacilityFilters").addEventListener("click", () => {
    document.querySelectorAll('input[name="analysisFacility"]').forEach(input => { input.checked = false; });
    schedule("selection");
  });
  $("analysisRetry").addEventListener("click", () => options ? schedule("retry") : loadOptions());
  document.addEventListener("honsal:selection", () => schedule("location"));
  document.addEventListener("honsal:ready", () => {
    if (lastResult) window.HonsalMap?.renderAnalysis?.(lastResult);
  });
  loadOptions();
})();
