(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const put = (id, value) => {
    $(id).textContent = value;
  };

  const REGIONS = {
    chuncheon: {
      name: "춘천시",
      lat: 37.8813,
      lng: 127.7298
    },
    wonju: {
      name: "원주시",
      lat: 37.3422,
      lng: 127.9202
    },
    gangneung: {
      name: "강릉시",
      lat: 37.7519,
      lng: 128.8761
    }
  };

  let map;
  let marker;
  let info;
  let geocoder;
  let places;

  let ready = false;
  let searchId = 0;
  let selectionId = 0;
  let nearbyId = 0;
  let analysisResult = null;
  let analysisMarkers = [];
  let analysisLabels = [];
  let analysisInfo = null;

  let selected = {
    ...REGIONS.chuncheon,
    kind: "지역",
    description: "주소 확인 중…"
  };

  function node(tag, value = "", className = "") {
    const el = document.createElement(tag);
    el.textContent = value;
    el.className = className;
    return el;
  }

  function removeAnalysisLayers() {
    analysisMarkers.forEach(item => item.setMap(null));
    analysisMarkers = [];
    analysisLabels.forEach(item => item.setMap(null));
    analysisLabels = [];
    if (analysisInfo) analysisInfo.close();
    analysisInfo = null;
  }

  function clearAnalysis() {
    analysisResult = null;
    removeAnalysisLayers();
    if (ready) {
      put("mapStatus", "지도에서 위치를 선택하면 주소와 주변 장소를 확인할 수 있습니다.");
    }
  }

  function facilityBubble(facilities) {
    const content = node("section", "", "analysis-facility-info");
    content.setAttribute("aria-label", "선택 시설 상세 정보");
    content.dataset.facilityCount = String(facilities.length);
    content.style.cssText = "box-sizing:border-box;width:280px;max-height:320px;overflow-y:auto;padding:14px;color:#30463e;font-size:12px;line-height:1.5;white-space:normal;overflow-wrap:anywhere;";
    content.append(node("strong", facilities.length > 1
      ? `같은 위치의 시설 ${facilities.length}곳`
      : "선택 시설 정보"));

    facilities.forEach(facility => {
      // 같은 상호명·유형·좌표라도 별도 시설은 하나씩 표시합니다.
      const item = node("article", "", "analysis-facility-item");
      item.dataset.facilityId = String(facility.facility_id);
      item.style.cssText = "margin-top:10px;padding-top:10px;border-top:1px solid #dfe7e2;";
      const heading = node("strong", `상호명: ${facility.name}`);
      heading.style.display = "block";
      item.append(heading, node("div", facility.subtype));
      item.append(node("div", facility.address || "주소 정보 없음"));
      if (Number.isFinite(facility.distance_m)) {
        item.append(node("div", `격자 중심 직선거리 ${facility.distance_m.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}m`));
      }
      item.append(phoneElement(facility.phone));
      if (facility.in_city_boundary === false) {
        item.append(node("div", "춘천 행정경계 밖의 인근 시설"));
      }
      content.append(item);
    });
    return content;
  }

  function paintAnalysis() {
    if (!ready || !analysisResult) return false;
    removeAnalysisLayers();
    const facilities = analysisResult.facilities;
    if (facilities.some(facility => !Number.isFinite(facility.lat)
      || !Number.isFinite(facility.lon))) {
      put("mapStatus", "시설 좌표를 확인할 수 없어 마커를 표시하지 못했습니다. 아래 시설 목록을 확인하세요.");
      return false;
    }

    // 좌표가 겹치면 하나의 클릭 지점에 모든 원본 행을 보관합니다.
    // 이름이나 시설 종류를 기준으로 시설 자체를 합치거나 버리지 않습니다.
    const locations = new Map();
    facilities.forEach(facility => {
      const key = `${facility.lat},${facility.lon}`;
      if (!locations.has(key)) locations.set(key, []);
      locations.get(key).push(facility);
    });

    try {
      locations.forEach(group => {
        const first = group[0];
        const facilityMarker = new kakao.maps.Marker({
          map,
          position: new kakao.maps.LatLng(first.lat, first.lon),
          title: group.length > 1
            ? `같은 위치의 시설 ${group.length}곳: ${group.map(item => item.name).join(", ")}`
            : `${first.name} · ${first.subtype}`,
          zIndex: 4
        });
        kakao.maps.event.addListener(facilityMarker, "click", () => {
          if (analysisInfo) analysisInfo.close();
          if (info) info.close();
          analysisInfo = new kakao.maps.InfoWindow({
            content: facilityBubble(group),
            removable: true,
            zIndex: 6
          });
          analysisInfo.open(map, facilityMarker);
        });
        analysisMarkers.push(facilityMarker);
        if (group.length > 1) {
          const count = node("span", String(group.length), "analysis-marker-count");
          count.style.cssText = "display:block;min-width:20px;height:20px;padding:0 4px;box-sizing:border-box;border:2px solid #fff;border-radius:10px;background:#117c56;color:#fff;font:600 11px/16px sans-serif;text-align:center;pointer-events:none;";
          count.setAttribute("aria-label", `같은 위치의 시설 ${group.length}곳`);
          analysisLabels.push(new kakao.maps.CustomOverlay({
            map,
            position: new kakao.maps.LatLng(first.lat, first.lon),
            content: count,
            xAnchor: 0.5,
            yAnchor: 2.6,
            zIndex: 5
          }));
        }
      });
      put("mapStatus", `주변 3×3 격자의 선택 시설 ${facilities.length.toLocaleString("ko-KR")}곳 · 같은 좌표의 시설은 마커를 눌러 모두 확인할 수 있습니다.`);
      return true;
    } catch (error) {
      removeAnalysisLayers();
      console.error(error);
      put("mapStatus", "시설 마커를 불러오지 못했습니다. 아래 시설 목록은 계속 확인할 수 있습니다.");
      return false;
    }
  }

  function renderAnalysis(result) {
    clearAnalysis();
    if (!result || !Array.isArray(result.facilities)) return false;
    analysisResult = result;
    return paintAnalysis();
  }

  function request(start, done) {
    let finished = false;

    const timer = setTimeout(() => {
      finish([], "TIMEOUT");
    }, 12000);

    function finish(...args) {
      if (finished) return;

      finished = true;
      clearTimeout(timer);
      done(...args);
    }

    try {
      start(finish);
    } catch (error) {
      console.error(error);
      finish([], "ERROR");
    }
  }

  function notify() {
    document.dispatchEvent(
      new CustomEvent("honsal:selection", {
        detail: { ...selected }
      })
    );
  }

  function clearResults() {
    $("searchResults").replaceChildren();
    $("searchResults").hidden = true;
  }

  function phoneElement(phone) {
    const value = String(phone || "").trim();
    const number = value.replace(/[^0-9+]/g, "");

    const el = node(
      number ? "a" : "span",
      value || "전화번호 미등록"
    );

    if (number) el.href = "tel:" + number;

    return el;
  }

  function detailsLink(url) {
    try {
      const parsed = new URL(url);

      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        parsed.hostname !== "place.map.kakao.com"
      ) {
        return null;
      }

      parsed.protocol = "https:";

      const link = node("a", "카카오맵 상세 보기 ↗");
      link.href = parsed.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      return link;
    } catch {
      return null;
    }
  }

  function fromPlace(item) {
    const address =
      item.road_address_name || item.address_name || "";

    return {
      name: item.place_name,
      description: address || "주소 정보 없음",
      address,
      kind: "장소",
      lat: Number(item.y),
      lng: Number(item.x),
      phone: item.phone,
      url: item.place_url
    };
  }

  function addressBubble(address) {
    const bubble = node(
      "div",
      address,
      "address-map-bubble"
    );

    bubble.title = address;

    bubble.style.cssText = `
      box-sizing: border-box;
      width: 190px;
      min-height: 0;
      padding: 7px 10px;
      background: #fff;
      color: #30463e;
      font-size: 12px;
      line-height: 1.5;
      white-space: normal;
      overflow-wrap: anywhere;
    `;

    return bubble;
  }

  function selectPoint(location, move = true) {
    if (
      !ready ||
      !Number.isFinite(location.lat) ||
      !Number.isFinite(location.lng)
    ) {
      return false;
    }

    searchId++;
    const token = ++selectionId;

    if (location.lat !== selected.lat || location.lng !== selected.lng) {
      clearAnalysis();
    }
    selected = { ...location };
    clearResults();

    const position = new kakao.maps.LatLng(
      location.lat,
      location.lng
    );

    marker.setPosition(position);

    if (move) {
      map.setCenter(position);
      map.setLevel(5);
    }

    info.close();

    info.setContent(
      addressBubble(location.address || "주소 확인 중…")
    );

    info.open(map, marker);

    put(
      "mapStatus",
      "지도에서 위치를 선택하면 주소와 주변 장소를 확인할 수 있습니다."
    );

    put(
      "searchMessage",
      "선택 위치의 정보를 확인하고 있습니다."
    );

    put(
      "detailCoordinates",
      `위도 ${location.lat.toFixed(6)} · 경도 ${location.lng.toFixed(6)}`
    );

    put("detailRoadAddress", "주소 확인 중…");
    put("detailJibunAddress", "주소 확인 중…");

    $("selectedPlaceInfo").hidden =
      location.kind !== "장소";

    put(
      "selectedPlaceName",
      location.kind === "장소" ? location.name : ""
    );

    $("selectedPlacePhone").replaceChildren(
      phoneElement(location.phone)
    );

    $("selectedPlaceLink").replaceChildren();

    const link = detailsLink(location.url);

    if (link) {
      $("selectedPlaceLink").append(link);
    }

    notify();
    searchNearby();

    request(
      done => {
        geocoder.coord2Address(
          location.lng,
          location.lat,
          done
        );
      },
      (items, status) => {
        if (token !== selectionId) return;

        let address = location.address || "";

        if (
          status === kakao.maps.services.Status.OK &&
          items[0]
        ) {
          const road =
            items[0].road_address?.address_name;

          const jibun =
            items[0].address?.address_name;

          put(
            "detailRoadAddress",
            road || "이 좌표에 제공되는 도로명주소가 없습니다."
          );

          put(
            "detailJibunAddress",
            jibun || "이 좌표에 제공되는 지번주소가 없습니다."
          );

          address = road || jibun || address;

          info.setContent(
            addressBubble(
              address || "이 위치의 주소 정보가 없습니다."
            )
          );
        } else {
          const message =
            status === kakao.maps.services.Status.ZERO_RESULT
              ? "이 위치의 주소 정보가 없습니다."
              : "주소 조회 실패 · 위치를 다시 선택해 주세요.";

          put("detailRoadAddress", message);
          put("detailJibunAddress", message);

          info.setContent(
            addressBubble(address || message)
          );
        }

        selected.description =
          address || "주소 정보 없음";

        if (selected.kind === "위치" && address) {
          selected.name = address;
        }

        put(
          "searchMessage",
          address
            ? "선택 위치: " + address
            : "선택 위치의 주소를 확인할 수 없습니다."
        );

        notify();
      }
    );

    return true;
  }

  function searchNearby() {
    if (!ready) return;

    const token = ++nearbyId;
    const category = $("nearbyCategory");

    $("nearbyResults").replaceChildren();
    $("nearbyResults").setAttribute("aria-busy", "true");

    put(
      "nearbyMessage",
      "주변 " +
        category.options[category.selectedIndex].text +
        " 검색 중…"
    );

    request(
      done => {
        places.categorySearch(
          category.value,
          done,
          {
            location: new kakao.maps.LatLng(
              selected.lat,
              selected.lng
            ),
            radius: 1000,
            size: 15,
            page: 1,
            sort: kakao.maps.services.SortBy.DISTANCE
          }
        );
      },
      (items, status) => {
        if (token !== nearbyId) return;

        $("nearbyResults").setAttribute(
          "aria-busy",
          "false"
        );

        if (
          status !== kakao.maps.services.Status.OK ||
          !items.length
        ) {
          put(
            "nearbyMessage",
            status === kakao.maps.services.Status.ZERO_RESULT
              ? "선택 위치 반경 1km에서 검색된 장소가 없습니다."
              : "검색에 실패했습니다. 다시 검색을 눌러 주세요."
          );
          return;
        }

        put(
          "nearbyMessage",
          `카카오 검색 결과 ${items.length}개 표시 · 거리순 최대 15개`
        );

        items.forEach(item => {
          const card = node(
            "article",
            "",
            "nearby-place"
          );

          const button = node(
            "button",
            item.place_name,
            "nearby-place-title"
          );

          button.type = "button";

          button.addEventListener("click", () => {
            selectPoint(fromPlace(item));
          });

          const address = node(
            "p",
            item.road_address_name ||
              item.address_name ||
              "주소 정보 없음"
          );

          const actions = node(
            "div",
            "",
            "nearby-actions"
          );

          actions.append(phoneElement(item.phone));

          const link = detailsLink(item.place_url);

          if (link) actions.append(link);

          card.append(button, address, actions);
          $("nearbyResults").append(card);
        });
      }
    );
  }

  function renderSearch(items, kind) {
    clearResults();

    items.slice(0, 8).forEach(item => {
      const location =
        kind === "주소"
          ? {
              name: item.address_name,
              description: item.address_name,
              address: item.address_name,
              kind,
              lat: Number(item.y),
              lng: Number(item.x)
            }
          : fromPlace(item);

      const button = node(
        "button",
        "",
        "result-item"
      );

      button.type = "button";

      button.append(
        node("strong", location.name),
        node("small", location.description)
      );

      button.addEventListener("click", () => {
        selectPoint(location);
      });

      $("searchResults").append(button);
    });

    $("searchResults").hidden = false;

    put(
      "searchMessage",
      "최대 8개 결과를 표시합니다. 위치를 선택하세요."
    );
  }

  function search(keyword) {
    if (!ready) {
      put(
        "searchMessage",
        "지도가 아직 준비되지 않았습니다."
      );
      return;
    }

    keyword = String(keyword || "").trim();
    if (!keyword) return;

    const token = ++searchId;

    clearResults();
    put("searchMessage", "검색 중…");

    request(
      done => geocoder.addressSearch(keyword, done),
      (items, status) => {
        if (token !== searchId) return;

        if (
          status === kakao.maps.services.Status.OK &&
          items.length
        ) {
          renderSearch(items, "주소");
          return;
        }

        if (
          status !== kakao.maps.services.Status.ZERO_RESULT
        ) {
          put(
            "searchMessage",
            "주소 검색에 실패했습니다. 다시 시도해 주세요."
          );
          return;
        }

        request(
          done => places.keywordSearch(keyword, done),
          (results, state) => {
            if (token !== searchId) return;

            if (
              state === kakao.maps.services.Status.OK &&
              results.length
            ) {
              renderSearch(results, "장소");
            } else {
              put(
                "searchMessage",
                state === kakao.maps.services.Status.ZERO_RESULT
                  ? "검색 결과가 없습니다."
                  : "장소 검색에 실패했습니다."
              );
            }
          }
        );
      }
    );
  }

  function goToRegion(key) {
    if (!REGIONS[key]) return false;

    return selectPoint({
      ...REGIONS[key],
      kind: "지역",
      description: "주소 확인 중…"
    });
  }

  window.HonsalMap = {
    search,
    goToRegion,
    renderAnalysis,
    clearAnalysis,

    getAnalysisFacilityCount() {
      return analysisResult ? analysisResult.facilities.length : 0;
    },

    getMap() {
      return ready ? map : null;
    },

    // 정류장을 눌러도 분석 기준점과 격자는 바꾸지 않습니다.
    focusTransport(lat, lng) {
      if (
        !ready ||
        !Number.isFinite(lat) ||
        !Number.isFinite(lng)
      ) {
        return;
      }

      info.close();
      map.panTo(new kakao.maps.LatLng(lat, lng));
    },

    wholeGangwon() {
      if (!ready) return;

      searchId++;
      clearResults();
      info.close();

      map.setCenter(
        new kakao.maps.LatLng(37.75, 128.1)
      );

      map.setLevel(11);

      put(
        "mapStatus",
        "전체 보기 · 선택 위치와 격자 기준은 유지됩니다."
      );
    },

    zoom(delta) {
      if (!ready) return;

      map.setLevel(
        Math.max(
          1,
          Math.min(14, map.getLevel() + delta)
        )
      );
    },

    relayout() {
      if (!ready) return;

      const center = map.getCenter();
      map.relayout();
      map.setCenter(center);
    },

    isReady() {
      return ready;
    },

    getSelected() {
      return { ...selected };
    }
  };

  function chooseCoordinates(point) {
    const lat = point.getLat();
    const lng = point.getLng();

    selectPoint(
      {
        name: `선택 지점 (${lat.toFixed(6)}, ${lng.toFixed(6)})`,
        kind: "위치",
        lat,
        lng,
        description: "주소 확인 중…"
      },
      false
    );
  }

  $("nearbyCategory").addEventListener(
    "change",
    searchNearby
  );

  $("nearbyRetry").addEventListener(
    "click",
    searchNearby
  );

  $("useMapCenter").addEventListener("click", () => {
    if (ready) chooseCoordinates(map.getCenter());
  });

  window.addEventListener("resize", () => {
    window.HonsalMap.relayout();
  });

  if (!window.kakao?.maps) {
    put(
      "mapStatus",
      "지도 연결 실패: JavaScript 키와 등록 도메인을 확인하세요."
    );
    return;
  }

  kakao.maps.load(() => {
    try {
      if (!kakao.maps.services) {
        throw new Error("services 라이브러리 없음");
      }

      const center = new kakao.maps.LatLng(
        selected.lat,
        selected.lng
      );

      map = new kakao.maps.Map($("map"), {
        center,
        level: 5
      });

      marker = new kakao.maps.Marker({
        map,
        position: center
      });

      info = new kakao.maps.InfoWindow({
        zIndex: 2
      });

      geocoder = new kakao.maps.services.Geocoder();
      places = new kakao.maps.services.Places();

      kakao.maps.event.addListener(
        marker,
        "click",
        () => info.open(map, marker)
      );

      kakao.maps.event.addListener(
        map,
        "click",
        event => chooseCoordinates(event.latLng)
      );

      ready = true;

      window.HonsalGrid?.attach(map);
      goToRegion("chuncheon");

      // SDK 준비 전에 받은 API 응답도 지도에 표시합니다.
      if (analysisResult) paintAnalysis();

      document.dispatchEvent(
        new CustomEvent("honsal:ready")
      );
    } catch (error) {
      ready = false;
      console.error(error);

      put(
        "mapStatus",
        "지도 초기화 실패: 브라우저 콘솔을 확인하세요."
      );
    }
  });
})();