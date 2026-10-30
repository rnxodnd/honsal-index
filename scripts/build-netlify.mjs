import {copyFile, cp, mkdir, rm, writeFile} from "node:fs/promises";
import {dirname, join, resolve} from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";

const PROJECT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function validateApiBaseUrl(value, siteUrls = []) {
  const input = typeof value === "string" ? value.trim() : "";
  if (!input) {
    throw new Error("Netlify 환경변수 HONSAL_API_BASE_URL에 실행 중인 HTTPS 백엔드 주소를 설정하세요.");
  }
  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    throw new Error("HONSAL_API_BASE_URL은 https://호스트 형식이어야 합니다.");
  }
  if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password
      || parsed.pathname !== "/" || input.includes("?") || input.includes("#")
      || /[\s\\<>"']/.test(input)) {
    throw new Error("HONSAL_API_BASE_URL에는 경로·쿼리·계정 정보 없는 HTTPS 백엔드 주소만 입력하세요. /api는 붙이지 않습니다.");
  }
  for (const site of siteUrls.filter(Boolean)) {
    let origin;
    try { origin = new URL(site).origin; } catch { continue; }
    if (origin === parsed.origin) {
      throw new Error("HONSAL_API_BASE_URL에는 Netlify 화면 주소가 아니라 Python 백엔드의 HTTPS 주소를 입력하세요.");
    }
  }
  return parsed.origin;
}

export async function buildNetlify({projectDir = PROJECT_DIR, env = process.env} = {}) {
  // 잘못된 설정은 기존 산출물이나 로컬 소스를 변경하기 전에 중단합니다.
  const apiBaseUrl = validateApiBaseUrl(env.HONSAL_API_BASE_URL, [env.URL, env.DEPLOY_PRIME_URL]);
  const appDir = join(projectDir, "app");
  const outputDir = join(appDir, "dist");
  await rm(outputDir, {recursive: true, force: true});
  await mkdir(outputDir, {recursive: true});
  await copyFile(join(appDir, "index.html"), join(outputDir, "index.html"));
  // 백엔드 코드·설정·가상환경을 정적 배포물에 포함하지 않습니다.
  for (const directory of ["css", "js", "data"]) {
    await cp(join(appDir, directory), join(outputDir, directory), {recursive: true});
  }
  const serialized = JSON.stringify(apiBaseUrl)
    .replace(/</g, "\\u003c").replace(/>/g, "\\u003e")
    .replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
  await writeFile(join(outputDir, "js", "runtime-config.js"),
    `// 공개 API 주소입니다. 비밀번호나 비밀 키를 넣지 않습니다.\nwindow.HONSAL_API_BASE_URL = ${serialized};\n`, "utf8");
  return {outputDir, apiBaseUrl};
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  try {
    const {outputDir} = await buildNetlify();
    console.log(`Netlify UI build ready: ${outputDir}`);
  } catch (error) {
    console.error(`Netlify UI build failed: ${error.message}`);
    process.exitCode = 1;
  }
}
