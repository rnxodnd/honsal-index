(() => {
  "use strict";

  // 주변 3×3 격자의 실거래가: 유형별 가장 최근 거래 + 최근 3개월 중간값
  // 데이터: app/data/trades.json (src/data/geocode_trades.py 로 생성)
  const $ = id => document.getElementById(id);
  const ORDER = ["sh_rent", "offi_rent", "rh_rent", "apt_rent", "offi_trade", "apt_trade"];

  let data = null;
  let loadError = null;
  let gridIds = [];
  let gridPhase = "idle";
  let renderToken = 0;

  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  // 만원 → "1억 2,000만원"
  function won(manwon) {
    if (manwon === null || manwon === undefined) return "—";
    const eok = Math.floor(manwon / 10000);
    const rest = manwon % 10000;
    if (!eok) return `${rest.toLocaleString("ko-KR")}만원`;
    return rest ? `${eok}억 ${rest.toLocaleString("ko-KR")}만원` : `${eok}억원`;
  }

  function median(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
  }

  function priceText(kind, row) {
    if (kind === "trade") return `매매 ${won(row[1])}`;
    return row[2] > 0 ? `월세 ${won(row[1])} / ${row[2].toLocaleString("ko-KR")}만원` : `전세 ${won(row[1])}`;
  }

  function areaText(area) {
    return area ? `${area}㎡ (약 ${(area / 3.3058).toFixed(1)}평)` : "면적 정보 없음";
  }

  function recentSummary(kind, rows) {
    const recent = new Set(data.meta.recent_months);
    const inRecent = rows.filter(row => recent.has(row[0].slice(0, 7)));
    if (kind === "trade") {
      if (!inRecent.length) return ["최근 3개월 거래 없음"];
      return [`최근 3개월 중간값 매매 ${won(median(inRecent.map(r => r[1])))} (${inRecent.length}건)`];
    }
    const jeonse = inRecent.filter(r => !r[2]);
    const wolse = inRecent.filter(r => r[2] > 0);
    const lines = [];
    if (wolse.length) {
      lines.push(`최근 3개월 중간값 월세 ${won(median(wolse.map(r => r[1])))} / ${median(wolse.map(r => r[2])).toLocaleString("ko-KR")}만원 (${wolse.length}건)`);
    }
    if (jeonse.length) {
      lines.push(`최근 3개월 중간값 전세 ${won(median(jeonse.map(r => r[1])))} (${jeonse.length}건)`);
    }
    return lines.length ? lines : ["최근 3개월 거래 없음"];
  }

  function card(typeKey, rows, scopeLabel) {
    const type = data.meta.types[typeKey];
    rows = [...rows].sort((a, b) => b[0].localeCompare(a[0]));
    const latest = rows[0];
    const article = node("article", undefined, "poi-card");
    const top = node("div", undefined, "poi-top");
    const name = node("div", undefined, "poi-name");
    name.append(node("small", "가장 최근 거래", "business-name-label"), node("strong", priceText(type.kind, latest), "poi-title"));
    top.append(name, node("span", type.label, "poi-type"));
    article.append(top);
    article.append(node("div", `${latest[0]} · ${latest[4] || "건물명 없음"} · ${areaText(latest[3])}`, "poi-address"));
    const meta = node("div", undefined, "poi-meta");
    recentSummary(type.kind, rows).forEach(line => meta.append(node("span", line)));
    article.append(meta);
    article.append(node("small", `${scopeLabel} · 1년간 ${rows.length.toLocaleString("ko-KR")}건`, "facility-phone"));
    return article;
  }

  // 선택 위치의 법정동 이름 후보 (카카오 JS SDK)
  function legalDongNames(location) {
    return new Promise(resolve => {
      const services = window.kakao?.maps?.services;
      if (!services || !location || !Number.isFinite(location.lat)) return resolve([]);
      new services.Geocoder().coord2RegionCode(location.lng, location.lat, (result, status) => {
        if (status !== services.Status.OK) return resolve([]);
        const b = result.find(r => r.region_type === "B");
        if (!b) return resolve([]);
        const three = b.region_3depth_name || "";
        const four = b.region_4depth_name || "";
        resolve([[three, four].filter(Boolean).join(" "), four, three].filter(Boolean));
      });
    });
  }

  function message(text) {
    $("tradeBadge").textContent = "—";
    $("tradeList").replaceChildren(node("p", text, "empty-dataset"));
  }

  async function render() {
    const token = ++renderToken;
    if (loadError) return message(loadError);
    if (!data) return message("실거래가 데이터를 불러오는 중입니다.");
    if (gridPhase !== "ready" || !gridIds.length) return message("지도에서 위치를 선택하면 주변 3×3 격자의 실거래가를 표시합니다.");

    // 1) 격자 단위: 9개 격자의 거래를 유형별로 합친다.
    const merged = {};
    gridIds.forEach(id => {
      Object.entries(data.grids[id] || {}).forEach(([type, rows]) => {
        (merged[type] ||= []).push(...rows);
      });
    });

    // 2) 법정동 단위: 지번이 없는 거래(주로 단독·다가구)
    const location = window.HonsalMap?.getSelected?.();
    const names = await legalDongNames(location);
    if (token !== renderToken) return;
    const dongName = names.find(n => data.dongs[n]);
    const dongRows = dongName ? data.dongs[dongName] : {};

    const cards = [];
    let total = 0;
    ORDER.forEach(type => {
      if (merged[type]?.length) {
        cards.push(card(type, merged[type], "주변 3×3 격자"));
        total += merged[type].length;
      }
      if (dongRows[type]?.length) {
        cards.push(card(type, dongRows[type], `${dongName} 전체 (동 단위 참고값)`));
        total += dongRows[type].length;
      }
    });

    $("tradeBadge").textContent = total ? `${total.toLocaleString("ko-KR")}건` : "거래 없음";
    const list = $("tradeList");
    list.replaceChildren(...cards);
    if (!cards.length) list.append(node("p", "최근 1년간 주변 3×3 격자에서 확인된 거래가 없습니다.", "empty-dataset"));

    const recent = data.meta.recent_months;
    $("tradeNote").textContent =
      `최근 3개월: ${recent[0]} ~ ${recent[recent.length - 1]} · 단위 만원 · 출처 ${data.meta.source}. ` +
      "실거래는 계약 후 30일 안에 신고하므로 최근 달은 거래가 덜 집계됐을 수 있습니다. 해제된 매매는 제외했습니다.";
  }

  async function load() {
    try {
      const response = await fetch("./data/trades.json");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
    } catch (error) {
      loadError = `실거래가 데이터를 불러오지 못했습니다 (${error.message}). app/data/trades.json 생성 여부를 확인하세요.`;
    }
    render();
  }

  document.addEventListener("honsal:grid", event => {
    gridPhase = event.detail.phase;
    gridIds = event.detail.ids || [];
    render();
  });

  const initial = window.HonsalGrid?.getState?.();
  if (initial) {
    gridPhase = initial.phase;
    gridIds = initial.ids || [];
  }
  load();
})();
