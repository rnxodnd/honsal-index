
// 시작하기 버튼
const startButton = document.getElementById("startBtn");

// 지도 영역
const mapSection = document.getElementById("map");

// 지역 이름과 설명
const regionName = document.getElementById("regionName");
const regionDescription = document.getElementById(
  "regionDescription"
);

// 지역별 화면 표시 내용
const regionDetails = {
  chuncheon: {
    name: "춘천시",
    description: "춘천시의 생활 편의 정보를 확인할 수 있습니다."
  },

  wonju: {
    name: "원주시",
    description: "원주시의 생활 편의 정보를 확인할 수 있습니다."
  },

  gangneung: {
    name: "강릉시",
    description: "강릉시의 생활 편의 정보를 확인할 수 있습니다."
  }
};

// 시작하기 버튼 클릭
startButton.addEventListener("click", function () {
  mapSection.scrollIntoView({
    behavior: "smooth"
  });
});

// 지역 선택 버튼 전체 가져오기
const regionButtons = document.querySelectorAll(".region-btn");

// 각 버튼에 클릭 기능 추가
regionButtons.forEach(function (button) {

  button.addEventListener("click", function () {

    // 선택한 지역 키
    const selectedRegion = button.dataset.region;

    const detail = regionDetails[selectedRegion];

    if (!detail) {
      return;
    }

    // 지역 이름 변경
    regionName.textContent = detail.name;

    // 지역 설명 변경
    regionDescription.textContent = detail.description;

    // 모든 버튼 스타일 초기화
    regionButtons.forEach(function (btn) {
      btn.classList.remove("btn-success");
      btn.classList.add("btn-outline-success");
    });

    // 선택한 버튼 강조
    button.classList.remove("btn-outline-success");
    button.classList.add("btn-success");

    // 지도 중심 이동
    window.HonsalMap.moveToRegion(selectedRegion);

  });

});
