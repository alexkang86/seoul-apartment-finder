#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apartments.json 각 단지에 NPay 단지번호(naver_complex_no) + 건물유형(building_type)을 구워 넣는다.
   네이버 통합검색 HTML에서:
     - 가장 많이 나오는 fin.land complexNo = 그 단지
     - "단지명","category":"주상복합/아파트/오피스텔/…" 구조화 필드로 유형 판별
   캐시(data/complexno_cache.json) 형식: {검색어: {"no": 번호, "type": 유형}}
   - 스로틀 + 1회 처리량 상한(RESOLVE_LIMIT). 번호 OR 유형이 빈 항목을 채움(점진 해소).
   유형 미상은 아파트로 간주(오제외 방지). 주상복합/오피스텔 등만 비-아파트로 표시·필터."""
import os, re, json, time, urllib.parse, urllib.request
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
APT  = os.path.join(ROOT, "docs", "data", "apartments.json")
CACHE_PATH = os.path.join(ROOT, "data", "complexno_cache.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
LIMIT = int(os.environ.get("RESOLVE_LIMIT", "100000"))
DELAY = float(os.environ.get("RESOLVE_DELAY", "0.25"))
TYPES = ("주상복합","오피스텔","도시형생활주택","아파트","연립주택","연립","단독")

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def fetch(query, name):
    url = "https://search.naver.com/search.naver?query=" + urllib.parse.quote(query + " 아파트")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "ignore")
    except Exception:
        return None, None
    nos = re.findall(r"fin\.land\.naver\.com/complexes/(\d+)", html)
    no = None
    if nos:
        top, n = Counter(nos).most_common(1)[0]
        if n >= 2: no = top
    # 유형: "단지명…","category":"유형"  (없으면 패널 텍스트 폴백)
    typ = None
    m = re.search(r'"'+re.escape(name)+r'[^"]*"\s*,\s*"category"\s*:\s*"([^"]+)"', html)
    if m and m.group(1) in TYPES: typ = m.group(1)
    if not typ:
        t = re.sub(r"<[^>]+>", " ", html); t = re.sub(r"\s+", " ", t)
        m = re.search(re.escape(name)+r"[^가-힣]{0,3}(주상복합|오피스텔|도시형생활주택|아파트)[^가-힣]{0,3}[\d,]+\s*세대", t)
        if m: typ = m.group(1)
    return no, typ

def norm(v):  # 구형(문자열/None) → dict 로 마이그레이션
    if isinstance(v, dict): return v
    return {"no": v, "type": None}

def main():
    d = load(APT, {"items": []})
    cache = {k: norm(v) for k, v in load(CACHE_PATH, {}).items()}
    items = d.get("items", [])
    newly = 0
    for a in items:
        q = ((a.get("dong") or "") + " " + a.get("name", "")).strip()
        if not q: continue
        c = cache.get(q)
        need = (c is None) or (c.get("no") is None) or (c.get("type") is None)
        if need and newly < LIMIT:
            no, typ = fetch(q, a.get("name", ""))
            old = cache.get(q, {})
            cache[q] = {"no": no or old.get("no"), "type": typ or old.get("type")}
            newly += 1; time.sleep(DELAY)
            if newly % 200 == 0: print(f"  …조회 {newly}건")
        c = cache.get(q, {})
        a["naver_complex_no"] = c.get("no")
        a["building_type"] = c.get("type")  # None=미상(아파트로 간주)
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(d, open(APT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    has_no = sum(1 for a in items if a.get("naver_complex_no"))
    nonapt = sum(1 for a in items if a.get("building_type") and a["building_type"] != "아파트")
    print(f"베이킹 완료: 번호 {has_no}/{len(items)} · 비아파트(주상복합 등) {nonapt}개 표시 "
          f"(이번 조회 {newly}건, 캐시 {len(cache)}건)")

if __name__ == "__main__": main()
