"""4단계: 직전 스냅샷과 비교해 신규·급상승·사라짐을 뽑고 history를 남긴다.

history.jsonl 한 줄 = 한 회차 스냅샷({ts, repos:{full_name: stars}}).
급상승은 7일 이상 지난 스냅샷 중 가장 최근 것을 기준으로 증가량을 계산한다.
확장 지점: WINDOW_DAYS를 바꾸면 급상승 판정 창이 바뀐다.
주의: 첫 실행에는 비교 대상이 없으므로 신규/급상승은 비어 있는 게 정상이다.
"""
import datetime, json
from common import DATA, save

WINDOW_DAYS = 7
MIN_SPAN_DAYS = 2      # 이보다 짧은 간격은 급상승으로 치지 않는다(노이즈)
MIN_DELTA = 5          # 스타 증가량 하한
KEEP_SNAPSHOTS = 180
SURGE_TOP = 12

cat = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
repos = cat["repos"]
now = datetime.datetime.now(datetime.timezone.utc)

hist_path = DATA / "history.jsonl"
history = []
if hist_path.exists():
    for line in hist_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            history.append(json.loads(line))

prev = history[-1] if history else None
# 7일 이상 지난 스냅샷을 우선 쓰고, 없으면 가장 오래된 것을 쓰되
# 간격이 MIN_SPAN_DAYS에 못 미치면 급상승 계산 자체를 포기한다.
# (같은 날 두 번 돌린 회차를 기준으로 삼으면 +1 스타가 1위로 올라온다.)
baseline = None
for snap in reversed(history):
    if (now - datetime.datetime.fromisoformat(snap["ts"])).days >= WINDOW_DAYS:
        baseline = snap
        break
if baseline is None and history:
    oldest = history[0]
    if (now - datetime.datetime.fromisoformat(oldest["ts"])).days >= MIN_SPAN_DAYS:
        baseline = oldest

cur_names = {r["full_name"] for r in repos}
new = [] if prev is None else sorted(
    [r for r in repos if r["full_name"] not in prev["repos"]],
    key=lambda r: -r["stars"])[:20]
gone = [] if prev is None else sorted(
    [{"full_name": k, "stars": v} for k, v in prev["repos"].items() if k not in cur_names],
    key=lambda r: -r["stars"])[:20]

surging = []
if baseline:
    base_ts = datetime.datetime.fromisoformat(baseline["ts"])
    span = max((now - base_ts).days, 1)
    for r in repos:
        was = baseline["repos"].get(r["full_name"])
        if was is None or was < 50:
            continue
        delta = r["stars"] - was
        if delta < MIN_DELTA:
            continue
        surging.append({"full_name": r["full_name"], "delta": delta,
                        "pct": round(delta / was * 100, 1), "span_days": span})
    surging.sort(key=lambda x: (-x["pct"], -x["delta"]))
    surging = surging[:SURGE_TOP]

save("deltas.json", {"generated": cat["generated"], "window_days": WINDOW_DAYS,
                     "new": [r["full_name"] for r in new],
                     "gone": gone, "surging": surging,
                     "has_baseline": baseline is not None})

history.append({"ts": now.isoformat(timespec="seconds"),
                "repos": {r["full_name"]: r["stars"] for r in repos}})
history = history[-KEEP_SNAPSHOTS:]
hist_path.write_text("\n".join(json.dumps(h, ensure_ascii=False) for h in history) + "\n",
                     encoding="utf-8")
print(f"신규 {len(new)} · 급상승 {len(surging)} · 사라짐 {len(gone)} · 스냅샷 {len(history)}회차")
