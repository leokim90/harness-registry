"""수집 스크립트 공통 유틸. 외부 의존성 없음(표준 라이브러리만)."""
import json, os, pathlib, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
# 토큰이 있으면 검색 30회/분, 없으면 10회/분. 여유를 둬서 대기 간격을 정한다.
# GH_PAUSE로 덮어쓸 수 있다(부분 수집·디버그용, 낮추면 2차 rate limit 위험).
PAUSE = float(os.environ.get("GH_PAUSE") or (2.5 if TOKEN else 12.0))


def headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "harness-registry"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 2차 rate limit은 잠시 쉬면 풀린다.
            if e.code in (403, 429) and i < tries - 1:
                time.sleep(30)
                continue
            raise
        except Exception:
            if i < tries - 1:
                time.sleep(5)
                continue
            raise


def search(q, per_page=100, sort="stars"):
    url = ("https://api.github.com/search/repositories?q="
           f"{urllib.parse.quote(q)}&sort={sort}&order=desc&per_page={min(per_page,100)}")
    return get_json(url)


def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / name).write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
