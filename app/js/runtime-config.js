(() => {
  // 테스트 브랜치의 app/을 기존 Netlify 사이트에 직접 업로드할 때 사용합니다.
  // 2026-10-31 임시 터널: 서버·터널이 켜져 있어야 하며 주소 변경 시 갱신합니다.
  const testSiteOrigin = "https://unique-dusk-66f82f.netlify.app";
  const testApiBaseUrl = "https://sender-sweet-contains-searched.trycloudflare.com";
  const defaultApiBaseUrl = window.location.origin === testSiteOrigin ? testApiBaseUrl : "";

  // 명시한 API 주소를 우선하며 로컬 Python 서버는 같은 출처의 API를 사용합니다.
  // Netlify 빌드 시에는 환경변수로 생성한 설정이 배포 사본의 이 파일을 대체합니다.
  window.HONSAL_API_BASE_URL = window.HONSAL_API_BASE_URL || defaultApiBaseUrl;
})();
