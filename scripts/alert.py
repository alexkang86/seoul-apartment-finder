#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
조건에 맞는 단지를 매일 텔레그램으로 알림.
사용:
  1) config.json 에 기준(예산/면적/건축연도/전세가율/구) 설정
  2) export TG_BOT_TOKEN="..."  export TG_CHAT_ID="..."
     (텔레그램 @BotFather 로 봇 생성 → 토큰, @userinfobot 으로 chat id 확인)
  3) python3 scripts/alert.py
  4) cron 등록(매일 9시):  0 9 * * *  cd ~/Desktop/seoul-apartment-finder && /usr/bin/python3 scripts/alert.py
"""
import os, json, urllib.parse, urllib.request

ROOT=os.path.join(os.path.dirname(__file__),"..")
def load(p,default=None):
    p=os.path.join(ROOT,p)
    return json.load(open(p,encoding="utf-8")) if os.path.exists(p) else default

cfg = load("config.json", {}) or {}
data = load("web/data/apartments.json", {"items":[]})
items = data.get("items",[])

def ok(a):
    c=cfg
    if a["trade_price_man"] > c.get("price_max_man", 10**9): return False
    if a["trade_price_man"] < c.get("price_min_man", 0): return False
    if a.get("built_year") and a["built_year"] < c.get("year_min", 0): return False
    if (a.get("gap_ratio") or 0) < c.get("gap_ratio_min", 0): return False
    if c.get("up_only") and not ((a.get("trend_pct") or 0) > 0): return False
    if c.get("school_required") and not ((a.get("elem_school_count") or 0) >= 1): return False
    if (a.get("rooms_est") or 0) < c.get("rooms_min", 0): return False
    if (a.get("baths_est") or 0) < c.get("baths_min", 0): return False
    if c.get("gu") and a["gu"] not in c["gu"]: return False
    return True

matched = [a for a in items if ok(a)]
matched.sort(key=lambda a:-(a.get("gap_ratio") or 0))

def won(m): return f"{m/10000:.2f}억".replace(".00","") if m and m>=10000 else f"{m}만"
lines=[f"🏠 조건 충족 아파트 {len(matched)}곳 (전세가율 높은순)"]
for a in matched[:12]:
    lines.append(f"\n• {a['name']} ({a['gu']} {a['dong']}, {a.get('built_year','?')}년)\n"
                 f"  매매 {won(a['trade_price_man'])} / 전세 {won(a.get('jeonse_price_man'))} "
                 f"· 전세가율 {round((a.get('gap_ratio') or 0)*100)}% · 추세 {a.get('trend_pct','-')}%")
msg = "\n".join(lines) if matched else "오늘 조건에 맞는 단지가 없습니다."

tok=os.environ.get("TG_BOT_TOKEN"); chat=os.environ.get("TG_CHAT_ID")
if not tok or not chat:
    print("[알림 미발송] TG_BOT_TOKEN / TG_CHAT_ID 환경변수가 없습니다. 메시지 미리보기:\n")
    print(msg)
else:
    url=f"https://api.telegram.org/bot{tok}/sendMessage"
    data=urllib.parse.urlencode({"chat_id":chat,"text":msg}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url,data=data),timeout=20)
        print(f"텔레그램 발송 완료: {len(matched)}곳")
    except Exception as e:
        print("발송 실패:",e); print(msg)
