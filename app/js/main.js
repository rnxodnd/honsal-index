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

  // 비교 칸: 기본 2칸, [＋ 비교 칸 추가]로 최대 10칸까지
  const MAX_SLOTS = 10;
  let slots = 2;
  const keyOf = result => `${result.location.lat},${result.location.lon}`;

  // 점수 높은 순 정렬 + 같은 점수는 같은 순위
  function ranked() {
    const sorted = [...snapshots].sort((a, b) => (b.total_score ?? -1) - (a.total_score ?? -1));
    let previous = null;
    let rank = 0;
    return sorted.map((snapshot, index) => {
      if (snapshot.total_score !== previous) rank = index + 1;
      previous = snapshot.total_score;
      return {snapshot, rank};
    });
  }

  function renderPodium(list) {
    const podium = $("comparePodium");
    podium.replaceChildren();
    const top = list.filter(item => item.rank <= 3);
    podium.hidden = !top.length;
    if (!top.length) return;
    podium.append(node("span", "BEST 3", "eyebrow podium-eyebrow"));
    const row = node("div", undefined, "podium-row");
    const medals = {1: "🥇", 2: "🥈", 3: "🥉"};
    top.forEach(({snapshot, rank}) => {
      const place = node("div", undefined, `podium-place podium-${rank}`);
      place.append(node("span", medals[rank], "podium-medal"));
      place.append(node("strong", `${rank}위`, "podium-rank"));
      place.append(node("h3", snapshot.location.name || "선택한 위치"));
      place.append(node("p", snapshot.grid.adm_nm || ""));
      place.append(node("strong", `${snapshot.total_score.toFixed(1)}점`, "podium-score"));
      row.append(place);
    });
    podium.append(row);
  }

  function renderCompare() {
    const list = ranked();
    renderPodium(list);
    $("compareCards").replaceChildren();
    for (let index = 0; index < Math.max(slots, list.length); index++) {
      const item = list[index];
      const snapshot = item?.snapshot;
      const card = node("div", undefined, "compare-card");
      card.append(node("span", item ? `${item.rank}위` : `비교 칸 ${index + 1}`, item ? "compare-rank" : "eyebrow"));
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
        const key = keyOf(snapshot);
        remove.addEventListener("click", () => {
          const at = snapshots.findIndex(entry => keyOf(entry) === key);
          if (at >= 0) snapshots.splice(at, 1);
          refreshCompare();
        });
        card.append(remove);
      } else {
        card.classList.add("is-empty");
        card.append(node("p", "지도에서 위치를 분석한 뒤 비교 목록에 추가하세요."));
      }
      $("compareCards").append(card);
    }
    $("addSlotBtn").disabled = slots >= MAX_SLOTS;
    $("addSlotBtn").textContent = slots >= MAX_SLOTS
      ? `최대 ${MAX_SLOTS}칸까지 비교할 수 있습니다`
      : `＋ 비교 칸 추가 (${slots}/${MAX_SLOTS})`;
    $("clearCompareBtn").disabled = !snapshots.length;
  }

  function refreshCompare() {
    $("compareCount").textContent = snapshots.length;
    const included = currentResult && snapshots.some(item => keyOf(item) === keyOf(currentResult));
    const full = snapshots.length >= slots;
    $("addCompareBtn").disabled = !currentResult || included || full;
    $("addCompareBtn").textContent = included
      ? "✓ 비교 목록에 추가됨"
      : full
        ? (slots < MAX_SLOTS ? `비교 칸 ${slots}개가 가득 찼습니다 · 지역 비교에서 칸 추가` : `최대 ${MAX_SLOTS}개까지 비교할 수 있습니다`)
        : `＋ 비교 목록에 추가 (${snapshots.length}/${slots})`;
    renderCompare();
  }

  $("addCompareBtn").addEventListener("click", () => {
    if (!currentResult || snapshots.length >= slots || snapshots.some(item => keyOf(item) === keyOf(currentResult))) return;
    snapshots.push(currentResult);
    refreshCompare();
  });
  $("addSlotBtn").addEventListener("click", () => {
    if (slots >= MAX_SLOTS) return;
    slots += 1;
    refreshCompare();
  });
  $("clearCompareBtn").addEventListener("click", () => {
    snapshots.length = 0;
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
  // 세로 줌 슬라이더: 위로 올릴수록 확대 (카카오 지도 레벨 1=가장 확대, 14=가장 축소)
  const syncZoomSlider = () => {
    const level = window.HonsalMap?.getLevel?.();
    if (level) $("zoomSlider").value = String(15 - level);
  };
  $("zoomSlider").addEventListener("input", event => {
    window.HonsalMap?.setLevel?.(15 - Number(event.target.value));
  });
  document.addEventListener("honsal:zoom", syncZoomSlider);
  document.addEventListener("honsal:ready", syncZoomSlider);
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
