#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apartments.json 에 동(법정동)별 초·중·고 학교 수를 붙인다 (API 재호출 없음).
   data/전국학교.csv (전국초중등학교 위치 표준데이터) 사용.
   서울+경기 전 지역, 동명 충돌 방지를 위해 (시도, 시군구정규화, 법정동) 기준 매칭."""
import os, csv, json, re
from collections import defaultdict

ROOT=os.path.join(os.path.dirname(__file__),"..")
SEOUL_GU={"종로구","중구","용산구","성동구","광진구","동대문구","중랑구","성북구","강북구","도봉구","노원구","은평구","서대문구","마포구","양천구","강서구","구로구","금천구","영등포구","동작구","관악구","서초구","강남구","송파구","강동구"}

# data/ 안에서 학교 CSV 자동 선택 (전국 우선)
def find_csv():
    cand=["전국학교.csv","schools_all.csv","schools.csv","schools_seoul.csv"]
    for c in cand:
        p=os.path.join(ROOT,"data",c)
        if os.path.exists(p): return p
    # 그 외 data/ 안의 아무 csv
    dd=os.path.join(ROOT,"data")
    for f in os.listdir(dd):
        if f.lower().endswith(".csv"): return os.path.join(dd,f)
    return None

def read_rows(p):
    for enc in ("cp949","utf-8-sig","euc-kr","utf-8"):
        try:
            rows=list(csv.DictReader(open(p,encoding=enc)))
            if rows and len(rows[0])>2: return rows,enc
        except Exception: pass
    return [],None

def level_of(s):           # 학교급 → elem/mid/high/None
    if not s: return None
    if "초등" in s: return "elem"
    if "중학" in s: return "mid"
    if "고등" in s: return "high"
    return None             # 특수/각종/유치원 등 제외

def parse_addr(jibun):     # 소재지지번주소 → (sido, gu_norm, dong)
    if not jibun: return None
    toks=jibun.split()
    if not toks: return None
    p=toks[0]
    if p.startswith("서울"): sido="서울"
    elif p.startswith("경기"): sido="경기"
    else: return None      # 서울·경기만
    citygu=[]; dong=None
    for t in toks[1:]:
        if t.endswith(("시","군","구")): citygu.append(t)
        elif t.endswith(("동","가","리")): dong=t; break
        elif t.endswith(("읍","면")): continue   # 읍/면은 건너뛰고 뒤의 리를 동으로
        elif re.match(r"^\d", t): break          # 번지 시작 → 동 없음
    if not dong: return None
    if sido=="서울":
        gu=next((c for c in citygu if c.endswith("구")), None)
        if not gu: return None
        gu_norm=gu
    else:
        si=next((c for c in citygu if c.endswith("시")), None)
        gu=next((c for c in citygu if c.endswith("구")), None)
        if not si: return None
        gu_norm=si[:-1]+(gu[:-1] if gu else "")   # 수원시 영통구 → 수원영통
    return (sido, gu_norm, dong)

def load_schools(p):
    rows,enc=read_rows(p)
    counts=defaultdict(lambda:[0,0,0])   # key -> [초,중,고]
    levels={"elem":0,"mid":0,"high":0}; matched=0
    for r in rows:
        lv=level_of(r.get("학교급구분") or r.get("학교종류명") or r.get("학교급") or "")
        if not lv: continue
        jibun=r.get("소재지지번주소") or r.get("지번주소") or ""
        key=parse_addr(jibun)
        if not key: continue
        idx={"elem":0,"mid":1,"high":2}[lv]
        counts[key][idx]+=1; levels[lv]+=1; matched+=1
    print(f"  학교CSV({os.path.basename(p)}, {enc}): 서울·경기 매칭 {matched}개 "
          f"(초 {levels['elem']}/중 {levels['mid']}/고 {levels['high']}), 고유 동 {len(counts)}곳")
    return counts

def apt_key(a):
    sido="서울" if a["gu"] in SEOUL_GU else "경기"
    dong=(a.get("dong") or "").split()[-1] if a.get("dong") else ""
    return (sido, a["gu"], dong)

def main():
    csvp=find_csv()
    if not csvp: print("학교 CSV 없음 (data/ 에 넣어주세요)"); return
    counts=load_schools(csvp)
    apt_path=os.path.join(ROOT,"web","data","apartments.json")
    d=json.load(open(apt_path,encoding="utf-8"))
    hit=0; hit_seoul=0; hit_gg=0
    for a in d.get("items",[]):
        e,m,h=counts.get(apt_key(a),[0,0,0])
        a["elem_school_count"]=e
        a["middle_school_count"]=m
        a["high_school_count"]=h
        if e or m or h:
            hit+=1
            if a["gu"] in SEOUL_GU: hit_seoul+=1
            else: hit_gg+=1
    json.dump(d, open(apt_path,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"학교 매칭 완료: 학교 보유 단지 {hit}개 / 전체 {len(d.get('items',[]))}개 "
          f"(서울 {hit_seoul} · 경기 {hit_gg})")

if __name__=="__main__": main()
