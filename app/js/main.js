(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const snapshots = [];
  let currentResult = null;

  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  function renderCompare() {
    $("compareCards").replaceChildren();
    for (let index = 0; index < 2; index++) {
      const snapshot = snapshots[index];
      const card = node("div", undefined, "compare-card");
      card.append(node("span", `비교 지역 ${index + 1}`, "eyebrow"));
      card.append(node("h3", snapshot?.location.name || (snapshot ? "선택한 위치" : "지역을 추가해 주세요")));
      if (snapshot) {
        card.append(node("strong", `${snapshot.total_score.toFixed(1)}점`, "compare-score"));
        card.append(node("p", `${snapshot.grid.adm_nm} · 선택 시설 ${snapshot.facilities.length.toLocaleString("ko-KR")}곳`));
        card.append(node("p", snapshot.types.map(type => type.subtype).join(", ")));
        const scores = node("dl", undefined, "compare-category-scores");
        snapshot.categories.forEach(category => {
          scores.append(node("dt", category.label), node("dd", category.score === null ? "미선택" : `${category.score.toFixed(1)}점`));
        });
        card.append(scores);
        const remove = node("button", "목록에서 제거", "remove-compare");
        remove.type = "button";
        remove.addEventListener("click", () => { snapshots.splice(index, 1); refreshCompare(); });
        card.append(remove);
      } else {
        card.append(node("p", "시설을 선택하고 분석을 완료한 뒤 비교 목록에 추가하세요."));
      }
      $("compareCards").append(card);
    }
  }

  function refreshCompare() {
    $("compareCount").textContent = snapshots.length;
    const included = currentResult && snapshots.some(item => item.grid.grid_id === currentResult.grid.grid_id);
    $("addCompareBtn").disabled = !currentResult || included || snapshots.length >= 2;
    $("addCompareBtn").textContent = included ? "✓ 비교 목록에 추가됨" : snapshots.length >= 2 ? "최대 2개까지 비교할 수 있습니다." : "＋ 비교 목록에 추가";
    renderCompare();
  }

  $("addCompareBtn").addEventListener("click", () => {
    if (!currentResult || snapshots.length >= 2 || snapshots.some(item => item.grid.grid_id === currentResult.grid.grid_id)) return;
    snapshots.push(currentResult);
    refreshCompare();
  });
  document.addEventListener("honsal:analysis", event => {
    currentResult = event.detail.status === "success" ? event.detail.result : null;
    refreshCompare();
  });
  document.addEventListener("honsal:filters-changed", () => {
    snapshots.length = 0;
    currentResult = null;
    refreshCompare();
  });

  function selectRegion(location) {
    $("regionName").textContent = location.name || "선택한 위치";
    $("regionDescription").textContent = location.description || "";
    $("regionType").textContent = location.kind === "지역" ? "선택한 지역" : "선택한 위치";
    $("datasetRegionName").textContent = location.name || "선택한 위치";
  }
  document.addEventListener("honsal:selection", event => selectRegion(event.detail));

  $("searchForm").addEventListener("submit", event => {
    event.preventDefault();
    const query = $("addressInput").value.trim();
    if (query) window.HonsalMap?.search(query);
  });
  $("resetMapBtn").addEventListener("click", () => window.HonsalMap?.wholeGangwon());
  $("zoomIn").addEventListener("click", () => window.HonsalMap?.zoom(-1));
  $("zoomOut").addEventListener("click", () => window.HonsalMap?.zoom(1));
  document.querySelectorAll("[data-region]").forEach(button => {
    button.addEventListener("click", () => window.HonsalMap?.goToRegion(button.dataset.region));
  });

  function switchView(view) {
    if (!["explore", "compare", "routes"].includes(view)) return;
    $("explore").hidden = view !== "explore";
    $("compareView").hidden = view !== "compare";
    $("localDataSection").hidden = view !== "explore";
    $("routesView").hidden = view !== "routes";
    document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
    window.scrollTo({top: 0, behavior: "smooth"});
    if (view === "compare") renderCompare();
    if (view === "explore") window.setTimeout(() => window.HonsalMap?.relayout(), 100);
  }
  window.HonsalUI = {switchView};
  document.querySelector(".brand")?.addEventListener("click", event => {
    event.preventDefault();
    switchView("explore");
  });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
  $("backToMap").addEventListener("click", () => switchView("explore"));

  function updateGridStatus() {
    const message = $("gridStatus").textContent.trim();
    $("gridToggleLabel").title = message || "선택 위치 주변의 500m 격자를 표시합니다.";
    $("gridStatus").hidden = !/실패|오류|초과|찾을 수 없|범위 밖/.test(message);
  }
  new MutationObserver(updateGridStatus).observe($("gridStatus"), {childList: true, characterData: true, subtree: true});
  updateGridStatus();
  refreshCompare();
  if (window.HonsalMap?.getSelected) selectRegion(window.HonsalMap.getSelected());
})();
