# bs-playlist-generator

[jundoll/bs-ranked-playlist](https://github.com/jundoll/bs-ranked-playlist)의 구조를 참고해 만든
개인용 Beat Saber 랭크 플레이리스트 생성기입니다.

## 원본과의 차이

| 항목 | 원본 | 이 프로젝트 |
|---|---|---|
| 실행 | GitHub Actions, 매일 1회 | **요청 시에만** (Coolify Task 수동 실행). 주기 스케줄 없음 |
| 호스팅 | GitHub Releases | **Cloudflare R2** 버킷 |
| 정렬 | 각 플레이리스트를 랭크일 내림차순 | 각 플레이리스트를 **별 난이도 오름차순** |
| 같은 곡의 여러 난이도 | 리더보드 ID 기준 중복 제거라서 한 플레이리스트에 공존 | 동일하게 유지 |
| 커버 숫자 폰트 | (원본 서체) | **SB Aggro Bold** |

플레이리스트 구성은 원본과 동일: `ranked_star_00` ~ `ranked_star_14` (별 정수 구간별) + `ranked_star_qualified`.
`MAX_STAR`(기본 16)까지 자동 확장하며, 맵이 없는 별 구간과 현재 맵이 없는 qualified는
파일을 만들지 않고 건너뜁니다 (2026-09 기준 ScoreSaber에 qualified 상태 맵이 없음).

## 동작 구조

웹 서버 없이 **대기 전용 컨테이너 + Coolify Task** 구조입니다:

1. 컨테이너는 `sleep infinity`로 떠 있기만 함 (CPU 0, 메모리 수 MB)
2. Coolify Task가 `python -m app.run`을 컨테이너 안에서 실행하면:
   - ScoreSaber API에서 별 구간별(minStar=★-1, maxStar=★+1) 랭크 리더보드를 전부 수집
   - 리더보드 ID 기준 중복 제거 → `int(stars) == ★` 필터 → 별 오름차순 정렬
   - 원본 커버 이미지에서 숫자를 지우고 SB Aggro Bold로 통일된 크기·위치에 재렌더링
   - `.bplist` (JSON, syncURL 포함)을 R2에 업로드
3. 전체 실행 약 10~20분, 진행 로그는 태스크 실행 기록에 남음

## Coolify 배포

1. 이 저장소를 GitHub에 push (public이어야 Coolify의 Public GitHub 앱으로 배포 가능)
2. Coolify → Project **Home** → **+ New** → **GitHub Repository** (Public GitHub 앱) → 저장소 선택
3. 설정:
   - **Build Pack**: `Dockerfile`
   - 포트/헬스체크 불필요 (웹 서버 없음)
4. **Environment Variables** 탭에서 아래 시크릿 입력 (Secret으로 추가 권장)

### 필수 시크릿

| 이름 | 설명 | 얻는 곳 |
|---|---|---|
| `R2_ACCOUNT_ID` | Cloudflare 계정 ID (32자리 16진수) | Cloudflare 대시보드 우측 하단 **Account ID** |
| `R2_ACCESS_KEY_ID` | R2 API Token의 Access Key ID | R2 → **Manage API Tokens** → Create API token (Object Read & Write) |
| `R2_SECRET_ACCESS_KEY` | R2 API Token의 Secret Access Key | 위 토큰 생성 시 일회성 표시 |
| `R2_BUCKET` | 업로드 대상 버킷 이름 | R2에서 미리 생성 |
| `R2_PUBLIC_BASE_URL` | 플레이리스트 공개 URL 기준 | 아래 "R2 공개 설정" 참고 |

### R2 공개 설정 (Beat Saber가 URL로 받아가려면 필수)

R2 버킷의 **Settings** 탭에서 둘 중 하나를 활성화하고 그 주소를 `R2_PUBLIC_BASE_URL`로 입력:

- **Public Access → r2.dev subdomain** — 간단하지만 개발/테스트용, 속도 제한 있음
  → `https://pub-xxxxxxxxxxxxxxxx.r2.dev`
- **Custom Domain** — 버킷에 도메인 연결 (권장)
  → `https://playlists.내도메인.com`

`R2_KEY_PREFIX`(기본 `playlists/`)로 버킷 내 저장 경로를 바꿀 수 있고, 빈 문자열이면 루트에 저장됨.

### 실행(요청) 방법 — Coolify Task

배포된 앱의 **Tasks** 탭에서 Task를 하나 만듭니다:

- **Name**: 아무거나 (예: `generate`)
- **Schedule (cron)**: `0 0 31 2 *` — 2월 31일은 존재하지 않으므로 **절대 자동 실행되지 않는** 식
- **Command**: `python -m app.run`

이후 실행이 필요할 때마다 Task 목록의 **Run now(지금 실행)** 버튼을 누르면 됩니다.
실행 로그·결과는 Task의 실행 기록(Executions)에서 확인 가능하며, 절대 자동으로 돌지 않습니다.

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m app.run --out out --max-star 7   # R2 없이 로컬 파일로 테스트
.venv\Scripts\python -m app.run                          # 실제 실행 (R2 환경변수 필요)
```

## 크레딧

- [jundoll/bs-ranked-playlist](https://github.com/jundoll/bs-ranked-playlist) (MIT) — 플레이리스트 구성 로직과 커버 플레이트 디자인/템플릿 원형
- [ScoreSaber](https://scoresaber.com) — 랭크 데이터 (API)
- SB Aggro Bold © 산돌컴퍼니 — [눈누](https://noonnu.cc) 무료 배포본 사용 (`assets/FONT_LICENSE.md` 참고)
