"""1단계: GitHub 검색 API로 후보 저장소를 모아 data/raw.json에 쌓는다.

질의별 결과를 full_name 기준으로 병합한다. 같은 저장소가 여러 질의에 걸리면
어떤 질의에 걸렸는지(queries)를 함께 남겨 분류 근거로 쓴다.
확장 지점: scripts/queries.json에 줄만 추가하면 수집 범위가 넓어진다.
주의: 토큰 없이 돌리면 검색 10회/분 제한에 걸린다(common.PAUSE가 흡수).
"""
import json, pathlib, sys, time
from common import DATA, PAUSE, ROOT, search

# 인자로 다른 질의 파일을 줄 수 있다(부분 수집·디버그용).
_qf = next((a for a in sys.argv[1:] if a.endswith(".json")), None)
_qp = pathlib.Path(_qf) if _qf else ROOT / "scripts" / "queries.json"
qs = json.loads(_qp.read_text(encoding="utf-8"))["queries"]
out = {}
if (DATA / "raw.json").exists() and "--fresh" not in sys.argv:
    out = json.loads((DATA / "raw.json").read_text(encoding="utf-8"))

ok = fail = 0
for hint, q, per in qs:
    try:
        d = search(q, per)
        items = d.get("items", [])
        ok += 1
        print(f"  {hint:14s} {q[:44]:44s} -> {len(items):3d} / {d.get('total_count')}")
        for it in items:
            fn = it["full_name"]
            e = out.setdefault(fn, {"queries": []})
            e.update({
                "full_name": fn, "name": it["name"], "owner": it["owner"]["login"],
                "desc": it.get("description") or "",
                "stars": it["stargazers_count"], "forks": it["forks_count"],
                "lang": it.get("language") or "", "topics": it.get("topics", []),
                "pushed": it["pushed_at"], "created": it["created_at"],
                "url": it["html_url"], "branch": it.get("default_branch", "main"),
                "license": (it.get("license") or {}).get("spdx_id") or "",
                "archived": it.get("archived", False),
                "homepage": it.get("homepage") or "",
            })
            if q not in e["queries"]:
                e["queries"].append(q)
    except Exception as ex:
        fail += 1
        print(f"  ERR {hint} {q}: {ex}", file=sys.stderr)
    time.sleep(PAUSE)

(DATA / "raw.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"질의 {ok}건 성공 / {fail}건 실패 · 후보 저장소 {len(out)}개")
# 질의가 절반 넘게 실패하면 데이터가 반쪽이므로 워크플로를 실패시킨다.
sys.exit(1 if fail > len(qs) / 2 else 0)
