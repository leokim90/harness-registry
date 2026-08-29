# harness-registry

GitHub에 공개된 **Claude Code 하네스**(스킬·서브에이전트·플러그인·오케스트레이션)와
**MCP 서버**를 매일 수집해 한 페이지로 보여주는 레지스트리.

페이지: `https://leokim90.github.io/harness-registry/`

## 동작

```
scripts/fetch.py    GitHub 검색 API 26개 질의 → data/raw.json
scripts/curate.py   분류·중복 제거·카테고리별 상한 → data/catalog.json
scripts/readme.py   README 발췌 + 설치 명령 추출 → catalog.json 보강
scripts/diff.py     직전 스냅샷 대비 신규·급상승·사라짐 → data/deltas.json
                    회차 스냅샷은 data/history.jsonl에 누적
```

`.github/workflows/refresh.yml`이 매일 09:00 KST에 위 4단계를 돌리고,
`data/`를 커밋한 뒤 `index.html` + `data/`를 GitHub Pages로 배포한다.
수동 실행은 Actions 탭의 **Run workflow**.

`index.html`은 데이터를 내장하지 않고 `data/catalog.json`을 런타임에 읽는다.
따라서 데이터만 갱신되면 페이지는 자동으로 최신이 된다.

## 로컬 실행

```bash
export GH_TOKEN=ghp_...        # 없어도 되지만 느리다(검색 10회/분 제한)
python scripts/fetch.py --fresh
python scripts/curate.py
python scripts/readme.py
python scripts/diff.py
python -m http.server 8000     # http://localhost:8000
```

## 수집 범위 조정

- 질의 추가/삭제: `scripts/queries.json`
- 카테고리별 노출 개수: `scripts/curate.py`의 `CAP`
- 오탐 저장소 제외: 같은 파일의 `DENY_NAMES` / `DENY_WORDS`
- 급상승 판정 창: `scripts/diff.py`의 `WINDOW_DAYS`

## 주의

- README 발췌는 700자로 제한한다(인용 범위 유지). 늘리지 말 것.
- 첫 실행에는 비교 대상이 없어 신규·급상승이 비어 있는 게 정상이다.
- 질의 절반 이상이 실패하면 `fetch.py`가 종료 코드 1로 워크플로를 실패시킨다.
  반쪽 데이터가 커밋되는 것을 막기 위한 장치다.
