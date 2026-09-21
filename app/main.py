import asyncio
import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import __version__, r2
from .config import Settings
from .generator import run_generation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bsplay")

settings = Settings()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class R2Uploader:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.client = r2.make_client(settings)

    def url(self, filename: str) -> str:
        return r2.public_url(self.settings, filename)

    async def upload(self, filename: str, data: bytes) -> None:
        await asyncio.to_thread(
            r2.upload_bytes,
            self.client,
            self.settings.r2_bucket,
            r2.object_key(self.settings, filename),
            data,
        )


class Job:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.state = {
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "step": None,
            "playlists": [],
            "skipped": [],
            "error": None,
        }

    def snapshot(self) -> dict:
        out = dict(self.state)
        out["version"] = __version__
        out["r2_ready"] = settings.r2_ready
        out["generate_enabled"] = bool(settings.generate_token)
        return out

    def _set(self, **kwargs) -> None:
        self.state.update(kwargs)

    async def run(self) -> bool:
        if self.lock.locked():
            return False
        async with self.lock:
            self._set(
                status="running",
                started_at=now_iso(),
                finished_at=None,
                step="준비 중",
                playlists=[],
                skipped=[],
                error=None,
            )
            try:
                uploader = R2Uploader(settings)
                result = await run_generation(
                    settings,
                    uploader,
                    progress=lambda step: self._set(step=step),
                )
                self._set(status="success", step=None, finished_at=now_iso(), playlists=result["playlists"], skipped=result["skipped"])
                log.info("generation finished: %s playlists", len(result["playlists"]))
            except Exception as exc:
                log.exception("generation failed")
                self._set(status="error", step=None, finished_at=now_iso(), error=f"{type(exc).__name__}: {exc}")
        return True


job = Job()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_on_startup:
        if settings.r2_ready:
            log.info("RUN_ON_STARTUP: 자동 생성을 시작합니다")
            asyncio.create_task(job.run())
        else:
            log.warning("RUN_ON_STARTUP이 켜져 있지만 R2 시크릿이 불충분해 자동 생성을 건너뜁니다: %s", settings.missing_r2_keys)
    else:
        log.info("RUN_ON_STARTUP=false: 시작 시 자동 생성 없음")
    yield


app = FastAPI(title="bs-playlist-generator", version=__version__, lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/status")
async def status():
    return job.snapshot()


@app.post("/generate")
async def generate(request: Request):
    if not settings.generate_token:
        return JSONResponse(status_code=503, content={"detail": "GENERATE_TOKEN 시크릿이 설정되지 않았습니다."})
    auth = request.headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(token.encode("utf-8"), settings.generate_token.encode("utf-8")):
        return JSONResponse(status_code=401, content={"detail": "토큰이 올바르지 않습니다."})
    if not settings.r2_ready:
        return JSONResponse(status_code=503, content={"detail": "R2 설정 불충분: " + ", ".join(settings.missing_r2_keys)})
    if job.lock.locked():
        return JSONResponse(status_code=409, content={"detail": "이미 실행 중입니다. /status 에서 진행 상황을 확인하세요."})
    asyncio.create_task(job.run())
    return JSONResponse(status_code=202, content={"detail": "생성을 시작했습니다. /status 에서 진행 상황을 확인하세요."})


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BS 랭크 플레이리스트 생성기</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", "Malgun Gothic", sans-serif; background: #14161a; color: #e8e8e8; }
  .wrap { max-width: 720px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #9aa0a6; font-size: 13px; margin-bottom: 20px; }
  .card { background: #1e2127; border: 1px solid #2c313a; border-radius: 10px; padding: 16px; margin-bottom: 14px; }
  .row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge.idle { background: #333842; color: #c7cbd1; }
  .badge.running { background: #1c3a5e; color: #7db3ff; }
  .badge.success { background: #1d4027; color: #6fd88a; }
  .badge.error { background: #47201f; color: #ff8a80; }
  .time { color: #9aa0a6; font-size: 12px; margin-left: auto; }
  .step { margin-top: 10px; font-size: 14px; color: #cfd4da; min-height: 20px; }
  input[type=password] { flex: 1; min-width: 200px; background: #14161a; border: 1px solid #2c313a; color: #e8e8e8; border-radius: 8px; padding: 9px 12px; font-size: 14px; }
  button { background: #ffd91a; color: #191600; border: 0; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 700; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  .msg { font-size: 13px; margin-top: 10px; min-height: 18px; }
  .msg.ok { color: #6fd88a; } .msg.err { color: #ff8a80; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  td, th { padding: 7px 8px; border-bottom: 1px solid #2c313a; text-align: left; }
  th { color: #9aa0a6; font-weight: 600; font-size: 12px; }
  td.num { text-align: right; color: #9aa0a6; white-space: nowrap; }
  a { color: #7db3ff; text-decoration: none; } a:hover { text-decoration: underline; }
  .muted { color: #9aa0a6; font-size: 13px; }
  .skip { font-size: 13px; color: #9aa0a6; }
  .errorbox { background: #47201f; border: 1px solid #6e2f2d; color: #ff8a80; border-radius: 8px; padding: 10px 12px; font-size: 13px; white-space: pre-wrap; }
  .hint { font-size: 12px; color: #7c828a; margin-top: 8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Beat Saber 랭크 플레이리스트 생성기</h1>
  <div class="sub">ScoreSaber 랭크맵을 별 구간별로 수집해 Cloudflare R2에 업로드합니다 · 주기적 실행 없이 요청 시에만 동작</div>

  <div class="card">
    <div class="row">
      <span class="badge idle" id="badge">idle</span>
      <span id="steptext" class="muted"></span>
      <span class="time" id="times"></span>
    </div>
    <div class="step" id="step"></div>
    <div id="errorbox" style="display:none" class="errorbox"></div>
  </div>

  <div class="card">
    <div class="row">
      <input type="password" id="token" placeholder="GENERATE_TOKEN 입력" autocomplete="off">
      <button id="btn">플레이리스트 생성</button>
    </div>
    <div class="msg" id="msg"></div>
    <div class="hint">토큰은 이 브라우저에만 저장됩니다. 실행은 Coolify 재배포/재시작으로도 가능합니다.</div>
  </div>

  <div class="card" id="resultcard" style="display:none">
    <div class="row" style="margin-bottom:8px"><b style="font-size:14px">마지막 결과</b></div>
    <table>
      <thead><tr><th>플레이리스트</th><th style="text-align:right">맵 수</th><th>링크</th></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
    <div id="skipbox" class="skip" style="margin-top:10px"></div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
const savedToken = localStorage.getItem('bspg_token');
if (savedToken) $('token').value = savedToken;

$('btn').addEventListener('click', async () => {
  const token = $('token').value.trim();
  const msg = $('msg');
  msg.className = 'msg';
  if (!token) { msg.textContent = '토큰을 입력하세요.'; msg.classList.add('err'); return; }
  $('btn').disabled = true;
  msg.textContent = '요청 중...';
  try {
    const res = await fetch('/generate', { method: 'POST', headers: { 'Authorization': 'Bearer ' + token } });
    const body = await res.json();
    if (res.ok) {
      localStorage.setItem('bspg_token', token);
      msg.textContent = body.detail;
      msg.classList.add('ok');
    } else {
      msg.textContent = (body.detail || ('HTTP ' + res.status));
      msg.classList.add('err');
    }
  } catch (e) {
    msg.textContent = '요청 실패: ' + e;
    msg.classList.add('err');
  }
  $('btn').disabled = false;
});

const BADGE_KO = { idle: '대기 중', running: '실행 중', success: '완료', error: '오류' };

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function tick() {
  try {
    const s = await (await fetch('/status')).json();
    const b = $('badge');
    b.className = 'badge ' + s.status;
    b.textContent = BADGE_KO[s.status] || s.status;
    $('step').textContent = s.step || '';
    $('steptext').textContent = s.status === 'running' ? '자동 갱신 중' : '';
    $('times').textContent = (s.started_at ? '시작 ' + s.started_at + ' ' : '') + (s.finished_at ? '· 종료 ' + s.finished_at : '');
    const eb = $('errorbox');
    if (s.error) { eb.style.display = 'block'; eb.textContent = s.error; } else { eb.style.display = 'none'; }
    if (s.playlists && s.playlists.length) {
      $('resultcard').style.display = 'block';
      $('tbody').innerHTML = s.playlists.map(p =>
        '<tr><td>' + esc(p.title) + '</td><td class="num">' + p.songs + '</td><td><a href="' + esc(p.url) + '" target="_blank">열기</a></td></tr>'
      ).join('');
      $('skipbox').textContent = s.skipped && s.skipped.length ? '건너뜀: ' + s.skipped.map(x => x.title + ' (' + x.reason + ')').join(', ') : '';
    }
  } catch (e) { /* ignore */ }
}
tick();
setInterval(tick, 3000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE
