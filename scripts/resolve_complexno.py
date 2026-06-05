#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apartments.json 각 단지에 NPay 부동산 단지번호(naver_complex_no)를 구워 넣는다.
   네이버 통합검색 HTML에서 가장 많이 나오는 fin.land complexNo = 그 단지.
   - data/complexno_cache.json 에 (검색어→번호) 캐시(영구 누적)
   - 스로틀 + 1회 처리량 상한(RESOLVE_LIMIT)으로 차단/타임아웃 방지
   - 캐시에 있으면 재조회 안 함 → 매일 새 단지만 점진 해소
   정적 호스팅이면 이 값으로 fin.land/complexes/{No} 직링크 가능(서버리스 불필요)."""
import os, re, json, time, urllib.parse, urllib.request
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
APT  = os.path.join(ROOT, "docs", "data", "apartments.json")
CACHE_PATH = os.path.join(ROOT, "data", "complexno_cache.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
LIMIT = int(os.environ.get("RESOLVE_LIMIT", "100000"))   # 1회 신규 조회 상한
DELAY = float(os.environ.get("RESOLVE_DELAY", "0.25"))    # 요청 간격(초)

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def fetch_complex_no(query):
    url = "https://search.naver.com/search.naver?query=" + urllib.parse.quote(query + " 아파트")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "ignore")
    except Exception:
        return None
    nos = re.findall(r"fin\.land\.naver\.com/complexes/(\d+)", html)
    if not nos: return None
    top, n = Counter(nos).most_common(1)[0]
    return top if n >= 2 else None   # 메인 패널(다회 등장)만 신뢰

def main():
    d = load(APT, {"items": []})
    cache = load(CACHE_PATH, {})
    items = d.get("items", [])
    done = newly = 0
    for a in items:
        q = ((a.get("dong") or "") + " " + a.get("name", "")).strip()
        if not q: continue
        if q not in cache and newly < LIMIT:
            cache[q] = fetch_complex_no(q); newly += 1
            time.sleep(DELAY)
            if newly % 200 == 0: print(f"  …신규 조회 {newly}건")
        a["naver_complex_no"] = cache.get(q)   # 캐시값(없으면 None) 베이킹
        if a["naver_complex_no"]: done += 1
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(d, open(APT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    resolved = sum(1 for v in cache.values() if v)
    print(f"complexNo 베이킹: 단지 {done}/{len(items)}개 번호 보유 "
          f"(이번 신규 조회 {newly}건, 캐시 {len(cache)}건 중 해소 {resolved}건)")

if __name__ == "__main__": main()
