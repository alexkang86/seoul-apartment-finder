#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대시보드 정적 서버 + NPay 부동산 단지 직링크 프록시.
   GET /go?q=<동 단지명>
     → 네이버 통합검색에서 그 단지의 fin.land complexNo 추출
     → https://fin.land.naver.com/complexes/<No> 로 302 리다이렉트 (정확한 NPay 단지 페이지)
   결과는 캐시(파일)에 저장해 재조회를 줄임. 실패 시 fin.land 검색으로 폴백."""
import http.server, socketserver, functools, os, re, json, urllib.parse, urllib.request
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
WEB  = os.path.join(ROOT, "docs")
CACHE_PATH = os.path.join(ROOT, "data", "complexno_cache.json")
PORT = int(os.environ.get("PORT", "8000"))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

try: CACHE = json.load(open(CACHE_PATH, encoding="utf-8"))
except Exception: CACHE = {}

def save_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        json.dump(CACHE, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception: pass

def resolve_complex_no(query):
    """통합검색 HTML에서 가장 많이 나오는 fin.land complexNo = 메인 단지."""
    if query in CACHE: return CACHE[query]
    url = "https://search.naver.com/search.naver?query=" + urllib.parse.quote(query + " 아파트")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko"})
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", "ignore")
    except Exception:
        return None
    nos = re.findall(r"fin\.land\.naver\.com/complexes/(\d+)", html)
    if not nos:
        CACHE[query] = None; save_cache(); return None
    cnt = Counter(nos)
    top, n = cnt.most_common(1)[0]
    no = top if n >= 2 else None   # 2회 미만이면 메인 단지 확신 못함 → 폴백
    CACHE[query] = no; save_cache()
    return no

def data_status():
    p = os.path.join(WEB, "data", "apartments.json")
    upd = None
    try: upd = json.load(open(p, encoding="utf-8")).get("updated")
    except Exception: pass
    refreshing = os.path.exists(os.path.join(ROOT, "data", ".refreshing"))
    return {"updated": upd, "refreshing": refreshing}

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/status"):
            body = json.dumps(data_status()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/go"):
            qs = urllib.parse.urlparse(self.path).query
            q = urllib.parse.parse_qs(qs).get("q", [""])[0]
            no = resolve_complex_no(q) if q else None
            if no:
                target = "https://fin.land.naver.com/complexes/%s" % no
            else:  # 폴백: NPay 부동산 검색(지역 이동)
                target = "https://fin.land.naver.com/search?query=" + urllib.parse.quote(q)
            self.send_response(302); self.send_header("Location", target); self.end_headers()
            return
        return super().do_GET()
    def log_message(self, *a): pass  # 조용히

def main():
    handler = functools.partial(Handler, directory=WEB)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print("🏠 아파트 탐색기 서버 실행 → http://localhost:%d" % PORT)
        print("   (단지 클릭 시 NPay 부동산 해당 단지로 바로 이동)")
        httpd.serve_forever()

if __name__ == "__main__": main()
