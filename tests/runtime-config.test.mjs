import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../app/js/runtime-config.js", import.meta.url), "utf8");
const testSite = "https://unique-dusk-66f82f.netlify.app";

function apiBaseFor(origin, override) {
  const window = {location: {origin}};
  if (override !== undefined) window.HONSAL_API_BASE_URL = override;
  vm.runInNewContext(source, {window});
  return window.HONSAL_API_BASE_URL;
}

test("수동 업로드한 기존 Netlify 화면은 공개 테스트 API에 연결한다", () => {
  assert.equal(apiBaseFor(testSite), "https://villages-don-clips-archived.trycloudflare.com");
});

test("로컬 서버와 다른 사이트는 임시 API로 연결하지 않는다", () => {
  for (const origin of ["http://127.0.0.1:5500", "http://localhost:5500", "http://[::1]:5500",
    "https://another-site.netlify.app", "http://unique-dusk-66f82f.netlify.app",
    "https://unique-dusk-66f82f.netlify.app.example.com", "null"]) {
    assert.equal(apiBaseFor(origin), "", origin);
  }
});

test("별도로 설정한 API 주소는 기본값보다 우선한다", () => {
  for (const origin of [testSite, "http://127.0.0.1:5500", "https://another-site.netlify.app"]) {
    assert.equal(apiBaseFor(origin, "https://custom-api.example.com"), "https://custom-api.example.com");
  }
});
