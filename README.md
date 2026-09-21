# bs-playlist-generator

[jundoll/bs-ranked-playlist](https://github.com/jundoll/bs-ranked-playlist)의 구조를 참고해 만든
개인용 Beat Saber 랭크 플레이리스트 자동 생성기입니다.

## 원본과의 차이

| 항목 | 원본 | 이 프로젝트 |
|---|---|---|
| 실행 | GitHub Actions, 매일 1회 | **요청 시에만** (재배포/재시작 또는 웹 버튼). 주기 스케줄 없음 |
| 호스팅 | GitHub Releases | **Cloudflare R2** 버킷 |
| 정렬 | 각 플레이리스트를 랭크일 내림차순 | 각 플레이리스트를 **별 난이도 오름차순** |
| 같은 곡의 여러 난이도 | 리더보드 ID 기준 중복 제거라서 한 플레이리스트에 공존 | 동일하게 유지 |
| 커버 숫자 폰트 | (원본 서체) | **SB Aggro Bold** |

플레이리스트 구성은 원본과 동일: `ranked_star_00` ~ `ranked_star_14` (별 정수 구간별) + `ranked_star_qualified`.
`MAX_STAR`(기본 16)까지 자동 확장하며, 맵이 없는 별 구간과 현재 맵이 없는 qualified는
파일을 만들지 않고 건너뜁니다 (2026-09 기준 ScoreSaber에 qualified 상태 맵이 없음).

## 동작 흐름

1. ScoreSaber API에서 별 구간별(minStar=★-1, maxStar=★+1) 랭크 리더보드를 전부 수집
2. 리더보드 ID 기준 중복 제거 → `int(stars) == ★` 필터 → 별 오름차순 정렬
3. 원본 커버 이미지에서 숫자를 지우고 SB Aggro Bold로 같은 위치·크기에 재렌더링
4. `.bplist` (JSON, syncURL 포함)을 R2에 업로드

## 실행(요청) 방법

- **Coolify 재배포 / 재시작** — 컨테이너가 시작될 때 1회 자동 생성 (`RUN_ON_STARTUP=true` 기본)
- **웹 버튼** — 서비스 페이지(`/`)에서 토큰 입력 후 "플레이리스트 생성"
- **curl** — `curl -X POST -H "Authorization: Bearer <GENERATE_TOKEN>" http://<주소>/generate`

진행 상황은 `/status` (JSON) 또는 웹 페이지에서 실시간 확인 가능.

## Coolify 배포

1. 이 저장소를 GitHub에 push (public이어야 Coolify의 Public GitHub 앱으로 배포 가능)
2. Coolify → Project **Home** → **+ New** → **GitHub Repository** (Public GitHub 앱) → 저장소 선택
3. 설정:
   - **Build Pack**: `Dockerfile`
   - **Port**: `8000` (자동 감지됨)
   - **Health Check Path**: `/healthz` (선택이지만 권장)
   - **FQDN**: 외부에서 웹 버튼을 쓰려면 도메인 연결. 도메인이 없어도 재배포/재시작 트리거는 동작함
4. **Environment Variables** 탭에서 아래 시크릿 입력 (Secret으로 추가 권장):

### 필수 시크릿

| 이름 | 설명 | 얻는 곳 |
|---|---|---|
| `R2_ACCOUNT_ID` | Cloudflare 계정 ID (32자리 16진수) | Cloudflare 대시보드 우측 하단 **Account ID** |
| `R2_ACCESS_KEY_ID` | R2 API Token의 Access Key ID | R2 → **Manage API Tokens** → Create API token (Object Read & Write) |
| `R2_SECRET_ACCESS_KEY` | R2 API Token의 Secret Access Key | 위 토큰 생성 시 일회성 표시 |
| `R2_BUCKET` | 업로드 대상 버킷 이름 | R2에서 미리 생성 |
| `R2_PUBLIC_BASE_URL` | 플레이리스트 공개 URL 기준 | 아래 "R2 공개 설정" 참고 |
| `GENERATE_TOKEN` | `POST /generate`용 Bearer 토큰 (아무 긴 문자열) | 직접 생성 |

### R2 공개 설정 (Beat Saber가 URL로 받아가려면 필수)

R2 버킷의 **Settings** 탭에서 둘 중 하나를 활성화하고 그 주소를 `R2_PUBLIC_BASE_URL`로 입력:

- **Public Access → r2.dev subdomain** — 간단하지만 개발/테스트용, 속도 제한 있음
  → `https://pub-xxxxxxxxxxxxxxxx.r2.dev`
- **Custom Domain** — 버킷에 도메인 연결 (권장)
  → `https://playlists.내도메인.com`

`R2_KEY_PREFIX`(기본 `playlists/`)로 버킷 내 저장 경로를 바꿀 수 있고, 빈 문자열이면 루트에 저장됨.

### 선택 환경변수

`.env.example` 참고. `MAX_STAR`, `SORT_DESC`, `RUN_ON_STARTUP`, `REQUEST_DELAY` 등.

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m app.localrun --out out --max-star 7   # R2 없이 로컬 파일로 테스트
.venv\Scripts\python -m uvicorn app.main:app --port 8000      # 웹 서비스 (시크릿은 환경변수로)
```

## 엔드포인트

| 경로 | 설명 |
|---|---|
| `GET /` | 상태/실행 웹 페이지 |
| `GET /status` | 현재 상태·마지막 결과 JSON |
| `GET /healthz` | 헬스체크 |
| `POST /generate` | 생성 요청 (Bearer `GENERATE_TOKEN` 필요) |

## 크레딧

- [jundoll/bs-ranked-playlist](https://github.com/jundoll/bs-ranked-playlist) (MIT) — 플레이리스트 구성 로직과 커버 플레이트 디자인/템플릿 원형
- [ScoreSaber](https://scoresaber.com) — 랭크 데이터 (API)
- SB Aggro Bold © 산돌컴퍼니 — [눈누](https://noonnu.cc) 무료 배포본 사용 (`assets/FONT_LICENSE.md` 참고)
