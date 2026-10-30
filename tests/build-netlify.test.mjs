import assert from "node:assert/strict";
import {access, mkdir, mkdtemp, readFile, readdir, rm, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import test from "node:test";
import vm from "node:vm";
import {buildNetlify, validateApiBaseUrl} from "../scripts/build-netlify.mjs";

test("API 주소는 HTTPS origin으로 정규화하고 화면 주소와 구분한다", () => {
  assert.equal(validateApiBaseUrl(" https://API.example.com:443/ "), "https://api.example.com");
  assert.equal(validateApiBaseUrl("https://api.example.com:8443"), "https://api.example.com:8443");
  assert.equal(validateApiBaseUrl("https://api.example.com", ["https://ui.example.com"]), "https://api.example.com");
  assert.throws(() => validateApiBaseUrl("https://ui.example.com/", ["https://ui.example.com"]), /Netlify 화면 주소/);
});

test("누락·잘못된 프로토콜·경로·쿼리·계정 정보·스크립트 문자를 거부한다", () => {
  for (const value of [undefined, "", " ", "http://api.example.com", "not a URL",
    "https://api.example.com/api", "https://api.example.com/?x=1", "https://api.example.com/?",
    "https://api.example.com/#", "https://user:secret@api.example.com",
    "https://api.example.com\\api", 'https://api.example.com/";alert(1)',
    "https://api.exam\nple.com", "https://api.example.com/<script>"]) {
    assert.throws(() => validateApiBaseUrl(value), {name: "Error"});
  }
});

test("배포 사본에만 API 설정을 넣고 로컬 소스와 Python 파일은 보존한다", async () => {
  const root = await mkdtemp(join(tmpdir(), "honsal-netlify-"));
  try {
    const app = join(root, "app");
    for (const directory of ["css", "js", "data", "dist"]) await mkdir(join(app, directory), {recursive: true});
    const localConfig = 'window.HONSAL_API_BASE_URL = window.HONSAL_API_BASE_URL || "";\n';
    await writeFile(join(app, "index.html"), '<script src="js/runtime-config.js"></script>');
    await writeFile(join(app, "js", "runtime-config.js"), localConfig);
    await writeFile(join(app, "css", "style.css"), "body{color:green}");
    await writeFile(join(app, "data", "grid.csv"), "grid_id\nfixture\n");
    await writeFile(join(app, "facility_filters.py"), "not_a_public_asset = True\n");
    await writeFile(join(app, "dist", "old-file.js"), "old");
    const result = await buildNetlify({projectDir: root, env: {HONSAL_API_BASE_URL: "https://api.example.com/"}});
    assert.equal(result.outputDir, join(app, "dist"));
    assert.equal(result.apiBaseUrl, "https://api.example.com");
    assert.deepEqual((await readdir(result.outputDir)).sort(), ["css", "data", "index.html", "js"]);
    assert.equal(await readFile(join(app, "js", "runtime-config.js"), "utf8"), localConfig);
    const context = {window: {}};
    vm.runInNewContext(await readFile(join(result.outputDir, "js", "runtime-config.js"), "utf8"), context);
    assert.equal(context.window.HONSAL_API_BASE_URL, "https://api.example.com");
    assert.equal(await readFile(join(result.outputDir, "data", "grid.csv"), "utf8"), "grid_id\nfixture\n");
    await assert.rejects(access(join(result.outputDir, "facility_filters.py")));
    await assert.rejects(access(join(result.outputDir, "old-file.js")));
    await assert.rejects(buildNetlify({projectDir: root, env: {}}), /HONSAL_API_BASE_URL/);
    assert.equal(await readFile(join(result.outputDir, "data", "grid.csv"), "utf8"), "grid_id\nfixture\n");
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});
