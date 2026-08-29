"""5단계: 설명과 README 발췌를 한국어로 번역해 data/ko.json에 캐시한다.

원문 해시를 키로 두므로 이미 번역된 항목은 다시 호출하지 않는다.
따라서 매일 드는 비용은 그날 새로 들어온 저장소 몇 개뿐이다.

ANTHROPIC_API_KEY가 없으면 아무 것도 하지 않고 통과한다(페이지가 영문으로 표시될 뿐).
번역 실패도 워크플로를 죽이지 않는다 — 실패한 항목만 영문으로 남는다.
수집 결과를 지키는 게 번역보다 우선이기 때문이다.

확장 지점: BATCH를 키우면 호출 수가 줄지만 한 번 실패할 때 손실이 커진다.
"""
import concurrent.futures as cf
import hashlib, json, os, sys, time, urllib.error, urllib.request
from common import DATA, save

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("TRANSLATE_MODEL", "claude-haiku-4-5-20251001")
BATCH = 8
WORKERS = 4        # 첫 회 229개를 12분에서 4분 수준으로 줄인다
MAX_NEW = int(os.environ.get("TRANSLATE_MAX", "400"))   # 폭주 방지 상한

SYSTEM = """너는 개발자 대상 기술 카탈로그의 번역가다. 영어 저장소 설명을 한국어로 옮긴다.

규칙:
- 제품명·저장소명·명령어·고유명사는 원문 그대로 둔다 (MCP, Claude Code, Playwright 등).
- 기술 용어는 한국 개발자가 실제 쓰는 표기를 쓴다.
- 원문의 홍보성 과장(best, revolutionary, 世界第一 등)은 덜어내고 사실만 남긴다.
- 원문에 없는 내용을 보태지 않는다. 의미를 바꾸지 않는다.
- 설명(desc)은 한 문장으로, README 발췌(summary)는 원문 길이에 맞춰 자연스러운 문단으로.
- summary가 빈 문자열이면 빈 문자열을 그대로 반환한다.

출력은 JSON 배열만. 설명·인사·코드블록 표시 금지.
형식: [{"i": 0, "desc": "...", "summary": "..."}, ...]"""


def call_api(payload, tries=4):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json",
                 "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code in (429, 500, 502, 503, 529) and i < tries - 1:
                time.sleep(5 * (i + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {body}")
        except Exception:
            if i < tries - 1:
                time.sleep(3)
                continue
            raise
    return None


def translate(items):
    """items: [{"i":n,"desc":..,"summary":..}] -> 같은 형식의 한국어"""
    res = call_api({
        "model": MODEL, "max_tokens": 8000, "system": SYSTEM,
        "messages": [{"role": "user",
                      "content": json.dumps(items, ensure_ascii=False)}],
    })
    text = "".join(b.get("text", "") for b in res.get("content", [])).strip()
    if text.startswith("```"):                      # 혹시 코드펜스가 붙어 오면 벗긴다
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def main():
    cat = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    repos = cat["repos"]
    ko = {}
    if (DATA / "ko.json").exists():
        ko = json.loads((DATA / "ko.json").read_text(encoding="utf-8"))

    if not API_KEY:
        print("ANTHROPIC_API_KEY 없음 - 번역 건너뜀 (페이지는 영문 표시)")
        # 캐시는 유지하되 사라진 저장소만 정리한다.
        names = {r["full_name"] for r in repos}
        save("ko.json", {k: v for k, v in ko.items() if k in names})
        return 0

    def sig(r):
        return hashlib.sha1(
            (r["desc"] + "\x1f" + r.get("summary", "")).encode()).hexdigest()[:16]

    todo = [r for r in repos if ko.get(r["full_name"], {}).get("h") != sig(r)]
    print(f"번역 대상 {len(todo)}개 / 전체 {len(repos)}개 (캐시 적중 {len(repos)-len(todo)})",
          flush=True)
    todo = todo[:MAX_NEW]

    chunks = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]

    def run(chunk):
        payload = [{"i": i, "desc": r["desc"], "summary": r.get("summary", "")}
                   for i, r in enumerate(chunk)]
        try:
            out = translate(payload)
            by_i = {o["i"]: o for o in out if isinstance(o, dict) and "i" in o}
            res = {}
            for i, r in enumerate(chunk):
                o = by_i.get(i)
                if o:
                    res[r["full_name"]] = {"h": sig(r),
                                           "desc": o.get("desc", "").strip(),
                                           "summary": o.get("summary", "").strip()}
            return res, len(chunk) - len(res)
        except Exception as ex:
            print(f"  배치 실패: {ex}", file=sys.stderr, flush=True)
            return {}, len(chunk)

    done = fail = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex_:
        for n, (res, f) in enumerate(ex_.map(run, chunks), 1):
            ko.update(res)
            done += len(res)
            fail += f
            print(f"  {n}/{len(chunks)} 배치 · 누적 {done}건", flush=True)

    names = {r["full_name"] for r in repos}
    ko = {k: v for k, v in ko.items() if k in names}     # 사라진 저장소 정리
    save("ko.json", ko)
    print(f"번역 완료 {done}건 · 실패 {fail}건 · 캐시 {len(ko)}건")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        # 번역이 죽어도 수집 결과는 지킨다.
        print(f"번역 단계 오류(무시하고 계속): {ex}", file=sys.stderr)
        sys.exit(0)
