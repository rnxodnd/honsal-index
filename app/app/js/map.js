
// 1. 지역별 위치
const regions = {
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

// 2. 지도 관련 변수
let map = null;
let marker = null;
let infoWindow = null;
let geocoder = null;
let places = null;

// 3. HTML 요소 가져오기
const mapStatus = document.getElementById("mapStatus");
const searchForm = document.getElementById("searchForm");
const addressInput = document.getElementById("addressInput");
const searchMessage = document.getElementById("searchMessage");

// 4. 안내 문구 변경
function showMessage(message) {
  searchMessage.textContent = message;
}

// 5. 검색 결과 위치 표시
function showLocation(lat, lng, name) {
  if (!map) {
    showMessage("지도가 아직 준비되지 않았습니다.");
    return;
  }

  const position = new kakao.maps.LatLng(lat, lng);

  // 지도 이동
  map.setCenter(position);
  map.setLevel(5);

  // 기존 마커 이동
  marker.setPosition(position);

  // 기존 정보창 닫기
  if (infoWindow) {
    infoWindow.close();
  }

  // 검색 결과를 안전하게 텍스트로 표시
  const infoContent = document.createElement("div");
  infoContent.style.padding = "10px";
  infoContent.style.minWidth = "140px";
  infoContent.style.textAlign = "center";
  infoContent.textContent = name;

  infoWindow = new kakao.maps.InfoWindow({
    content: infoContent
  });

  infoWindow.open(map, marker);

  // 오른쪽 지역 정보 카드 변경
  const regionName = document.getElementById("regionName");
  const regionDescription =
    document.getElementById("regionDescription");

  if (regionName) {
    regionName.textContent = name;
  }

  if (regionDescription) {
    regionDescription.textContent =
      "검색된 위치를 지도에 표시했습니다. 혼살지수는 데이터 연동 후 제공됩니다.";
  }
}

// 6. 기존 지역 선택 버튼 기능
function moveToRegion(regionKey) {
  const region = regions[regionKey];

  if (!region || !map) {
    return false;
  }

  showLocation(region.lat, region.lng, region.name);
  showMessage(region.name + "으로 이동했습니다.");
  return true;
}

// 기존 main.js에서 사용
window.HonsalMap = {
  moveToRegion: moveToRegion
};

// 7. 주소 검색 함수
function searchAddress(keyword) {

  showMessage("검색 중입니다...");

  // 주소 먼저 검색
  geocoder.addressSearch(keyword, function (result, status) {

    if (status === kakao.maps.services.Status.OK) {

      const place = result[0];

      showLocation(
        Number(place.y),
        Number(place.x),
        place.address_name
      );

      showMessage("주소 검색이 완료되었습니다.");
      return;
    }

    // 주소 검색 결과가 없으면 장소명 검색
    if (status === kakao.maps.services.Status.ZERO_RESULT) {
      searchPlace(keyword);
    } else {
      showMessage("주소 검색 중 오류가 발생했습니다.");
    }

  });
}

// 8. 장소명 검색 함수
function searchPlace(keyword) {

  places.keywordSearch(keyword, function (result, status) {

    if (status === kakao.maps.services.Status.OK) {

      // 첫 번째 검색 결과 사용
      const place = result[0];

      showLocation(
        Number(place.y),
        Number(place.x),
        place.place_name
      );

      showMessage(
        "검색 결과: " + place.place_name
      );

    } else if (
      status === kakao.maps.services.Status.ZERO_RESULT
    ) {
      showMessage("검색 결과가 없습니다. 주소나 장소명을 확인하세요.");
    } else {
      showMessage("장소 검색 중 오류가 발생했습니다.");
    }

  });
}

// 9. 검색 버튼 및 Enter 키
searchForm.addEventListener("submit", function (event) {

  event.preventDefault();

  const keyword = addressInput.value.trim();

  if (!keyword) {
    showMessage("주소나 장소명을 입력해 주세요.");
    return;
  }

  if (!map || !geocoder || !places) {
    showMessage("지도가 아직 준비되지 않았습니다.");
    return;
  }

  searchAddress(keyword);
});

// 10. 카카오맵 SDK 초기화
if (
  typeof kakao === "undefined" ||
  !kakao.maps
) {

  mapStatus.textContent =
    "카카오맵 SDK를 불러오지 못했습니다.";

} else {

  kakao.maps.load(function () {

    if (!kakao.maps.services) {
      mapStatus.textContent =
        "검색 라이브러리가 없습니다. libraries=services를 확인하세요.";
      return;
    }

    const center = new kakao.maps.LatLng(
      regions.chuncheon.lat,
      regions.chuncheon.lng
    );

    // 지도 생성
    map = new kakao.maps.Map(
      document.getElementById("map"),
      {
        center: center,
        level: 9
      }
    );

    // 마커 생성
    marker = new kakao.maps.Marker({
      position: center,
      map: map
    });

    // 검색 서비스 준비
    geocoder = new kakao.maps.services.Geocoder();
    places = new kakao.maps.services.Places();

    // 마커 클릭 이벤트
    kakao.maps.event.addListener(
      marker,
      "click",
      function () {
        if (infoWindow) {
          infoWindow.open(map, marker);
        }
      }
    );

    // 최초 지역 표시
    moveToRegion("chuncheon");

    mapStatus.textContent =
      "지도가 준비되었습니다. 주소나 장소를 검색해 보세요.";
  });

}
