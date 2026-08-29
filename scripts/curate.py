"""2단계: 후보를 분류·선별해 data/catalog.json을 만든다.

분류는 topic > 이름 > 설명 순으로 판정한다(topic이 가장 신뢰도가 높다).
DENY는 검색어에는 걸리지만 하네스/MCP가 아닌 범용 제품을 걷어내는 장치다.
확장 지점: CAP 값을 올리면 카테고리별 노출 개수가 늘어난다.
주의: 새 유행어가 생기면 classify()의 키워드부터 손봐야 한다.
"""
import datetime, json, re
from common import DATA, save

raw = json.loads((DATA / "raw.json").read_text(encoding="utf-8"))
now = datetime.datetime.now(datetime.timezone.utc)

# 검색어에는 걸리지만 하네스/MCP 서버가 아닌 것들: 범용 제품과 학습 자료.
DENY_WORDS = ["resume builder", "low-code", "低代码", "workflow automation platform",
              "web scraping", "ai client", "openai-compatible", "desktop all-in-one",
              "api gateway", "reverse proxy", "self-hosted knowledge",
              "面试", "从零", "study guide", "roadmap", "curriculum", "开源主仓库",
              "tutorial", "learn it. build it", "boilerplate", "starter template"]
DENY_NAMES = {
    "n8n-io/n8n", "amruthpillai/reactive-resume", "jeecgboot/JeecgBoot", "chatboxai/chatbox",
    "D4Vinci/Scrapling", "CherryHQ/cherry-studio", "router-for-me/CLIProxyAPI",
    "Wei-Shaw/sub2api", "diegosouzapw/OmniRoute", "farion1231/cc-switch",
    "google-gemini/gemini-cli", "bytedance/UI-TARS-desktop", "asgeirtj/system_prompts_leaks",
    "sansan0/TrendRadar", "koala73/worldmonitor", "rtk-ai/rtk", "headroomlabs-ai/headroom",
    "santifer/career-ops", "MadsLorentzen/ai-job-search", "luongnv89/claude-howto",
    # MCP를 지원할 뿐 MCP 서버가 아닌 범용 플랫폼
    "open-webui/open-webui", "netdata/netdata", "Kong/kong", "mudler/LocalAI",
    "siyuan-note/siyuan", "danny-avila/LibreChat", "lobehub/lobehub",
    "Snailclimb/JavaGuide", "Shubhamsaboo/awesome-llm-apps",
    "rohitg00/ai-engineering-from-scratch", "bojieli/ai-agent-book",
}
# 휴리스틱이 놓치지만 명백히 MCP 서버인 저장소(이름·설명에 mcp 단서가 없는 경우).
KEEP_MCP = {"upstash/context7"}
CAP = {"mcp": 60, "skills": 45, "harness": 40, "agents": 35, "plugins": 25,
       "awesome": 14, "awesome-mcp": 10}


def blob(r):
    return " ".join([r["full_name"], r["desc"], " ".join(r["topics"])]).lower()


def is_mcp_server(r):  # noqa: D401
    """MCP를 '지원'하는 제품과 MCP '서버'를 가른다.

    topic:mcp만 달아둔 범용 제품(open-webui, Kong 등)이 대량 유입되므로
    이름에 mcp가 있거나, topic이 mcp-server이거나, 설명이 스스로를
    MCP 서버라고 말하는 경우만 MCP로 인정한다.
    """
    if r["full_name"] in KEEP_MCP:
        return True
    tp = [t.lower() for t in r["topics"]]
    desc = r["desc"].lower()
    if "mcp" in r["name"].lower():
        return True
    tagged = "mcp-server" in tp or "mcp-servers" in tp
    if not tagged:
        return False
    # 태그만으로는 부족하다. 설명이 MCP를 언급하거나 프로토콜 토픽을 함께 달아야 인정.
    return (re.search(r"\bmcps?\b|model context protocol", desc) is not None
            or "model-context-protocol" in tp)


def classify(r):
    b, n = blob(r), r["name"].lower()
    tp = [t.lower() for t in r["topics"]]
    if n.startswith("awesome") or "awesome-" in n or "curated list" in b or "curated collection" in b:
        return "awesome-mcp" if "mcp" in b else "awesome"
    if is_mcp_server(r):
        return "mcp"
    if "harness" in b:
        return "harness"
    if "subagent" in b or "sub-agent" in b:
        return "agents"
    if "skill" in b:
        return "skills"
    if "plugin" in b or "marketplace" in b:
        return "plugins"
    if "orchestrat" in b or "multi-agent" in b or "agent framework" in b:
        return "harness"
    if "agent" in b:
        return "agents"
    return None


def relevant(r):
    b = blob(r)
    if r["full_name"] in DENY_NAMES or any(w in b for w in DENY_WORDS):
        return False
    return any(k in b for k in ["claude", "mcp", "skill", "subagent", "agent-skills",
                                "harness", "plugin", "model-context-protocol"])


rows = []
for r in raw.values():
    if not relevant(r):
        continue
    cat = classify(r)
    if not cat:
        continue
    days = (now - datetime.datetime.fromisoformat(r["pushed"].replace("Z", "+00:00"))).days
    r = {k: v for k, v in r.items() if k != "queries"}
    rows.append({**r, "cat": cat, "days_since_push": days,
                 "fresh": "active" if days <= 30 else ("ok" if days <= 120 else "stale"),
                 "zip": f"{r['url']}/archive/refs/heads/{r['branch']}.zip",
                 "clone": f"git clone {r['url']}.git"})

rows.sort(key=lambda r: -r["stars"])
final, cnt = [], {}
for r in rows:
    c = r["cat"]
    if cnt.get(c, 0) >= CAP.get(c, 20):
        continue
    cnt[c] = cnt.get(c, 0) + 1
    final.append(r)

save("catalog.json", {"generated": now.isoformat(timespec="seconds"),
                      "count": len(final), "repos": final})
print(f"선별 {len(final)}개 {cnt}")
