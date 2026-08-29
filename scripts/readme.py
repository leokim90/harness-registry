"""3단계: 각 저장소 README를 받아 요약 발췌와 설치 명령을 catalog.json에 채운다.

raw.githubusercontent.com을 쓰므로 API rate limit과 무관하다.
확장 지점: INSTALL_PATTERNS에 줄을 추가하면 새 설치 방식을 잡아낸다.
주의: README는 저작물이다. 인용 범위를 넘지 않도록 SUMMARY_LIMIT을 키우지 말 것.
"""
import concurrent.futures as cf
import html, json, re, urllib.request
from common import DATA, save

SUMMARY_LIMIT = 700
INSTALL_PATTERNS = [
    r"^\s*(claude plugin marketplace add .+)$", r"^\s*(claude mcp add .+)$",
    r"^\s*(npx [^\n]*)$", r"^\s*(uvx [^\n]*)$", r"^\s*(pip install [^\n]*)$",
    r"^\s*(npm install [^\n]*)$", r"^\s*(brew install [^\n]*)$",
    r"^\s*(git clone [^\n]*)$", r"^\s*(/plugin [^\n]*)$",
]
CANDIDATES = ["README.md", "readme.md", "README.MD", "docs/README.md"]


def fetch_readme(r):
    for br in dict.fromkeys([r["branch"], "main", "master"]):
        for fn in CANDIDATES:
            try:
                req = urllib.request.Request(
                    f"https://raw.githubusercontent.com/{r['full_name']}/{br}/{fn}",
                    headers={"User-Agent": "harness-registry"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return resp.read(120000).decode("utf-8", "ignore")
            except Exception:
                continue
    return ""


def summarize(md):
    t = html.unescape(md)
    t = re.sub(r"```.*?```", "", t, flags=re.S)      # 코드블록 제거
    t = re.sub(r"<[^>]+>", "", t)                     # HTML 태그 제거
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)        # 이미지 제거
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)    # 링크는 텍스트만 남김
    keep = []
    for line in (l.strip() for l in t.split("\n")):
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if set(line) <= set("=-|* ") or line.startswith("|") or line.count("|") >= 3:
            continue                                   # 표·언어 네비게이션 줄
        if "badge" in line.lower() or "shields.io" in line.lower():
            continue
        if len(line) < 25 and not keep:
            continue                                   # 도입부의 짧은 링크 줄
        keep.append(line)
    return " ".join(keep)[:SUMMARY_LIMIT]


def installs(md):
    out = []
    for pat in INSTALL_PATTERNS:
        for m in re.finditer(pat, md, flags=re.M):
            c = re.sub(r"\s+", " ", m.group(1)).strip().rstrip("\\").strip()
            if 6 < len(c) < 160 and c.lower() not in [x.lower() for x in out]:
                out.append(c)
    return out[:5]


def enrich(r):
    md = fetch_readme(r)
    r["summary"] = summarize(md) if md else ""
    r["install"] = installs(md) if md else []
    return r


cat = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
with cf.ThreadPoolExecutor(max_workers=14) as ex:
    cat["repos"] = list(ex.map(enrich, cat["repos"]))
save("catalog.json", cat)
print(f"README 확보 {sum(1 for r in cat['repos'] if r['summary'])}/{len(cat['repos'])} · "
      f"설치 명령 {sum(1 for r in cat['repos'] if r['install'])}건")
