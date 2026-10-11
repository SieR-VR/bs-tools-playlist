# Repository Guidance

## Commands

- Create the documented environment with `python -m venv .venv` and install pinned dependencies with `.venv\Scripts\pip install -r requirements.txt`.
- Run the generator with `.venv\Scripts\python -m app.run --out out --max-star 7` for a local-file run; omit `--out` only when all required R2 variables are configured.
- Run playlist expansion with `.venv\Scripts\python -m app.expand <path-or-url>`; use `--upload` only with complete R2 configuration. `-o` controls the output file.
- There is no test, lint, formatter, typecheck, or CI configuration in this repository. At minimum, compile source with `.venv\Scripts\python -m compileall app` and exercise CLI help before submitting changes.

## Runtime And Architecture

- This is a batch job, not a web service. The Docker image intentionally runs `sleep infinity`; Coolify Tasks or Execute Command must invoke `python -m app.run`.
- `app.run` is the main generation entrypoint: it fetches ScoreSaber ranked data, generates one `.bplist` JSON playlist per star value with embedded cover images, then writes locally or uploads to Cloudflare R2. `app.expand` is the separate all-ranked-difficulties workflow.
- ScoreSaber access is paginated and rate-limited; preserve `REQUEST_DELAY`, retry, timeout, and User-Agent behavior when changing API code.
- `assets/templates/` and `assets/SBAggroB.woff` are runtime inputs. Generation converts the WOFF to `assets/SBAggroB.ttf` on demand; the TTF is generated and ignored, so do not commit it.

## Configuration And Files

- R2 mode requires `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, and `R2_PUBLIC_BASE_URL`. Keep these secrets out of the repository; `.env.example` lists optional tuning variables and defaults.
- `R2_KEY_PREFIX` is normalized to a trailing slash and defaults to `playlists/`; changing it changes both object keys and playlist `syncURL` values.
- Generated outputs belong in ignored `out/` (or another ignored directory). Do not commit `.env`, `.venv/`, `__pycache__/`, generated `.pyc`, or generated font/output artifacts.
