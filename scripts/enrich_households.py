#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apartments.json 에 단지별 '세대수'를 붙인다 (API 재호출 없음).

데이터: data/ 에 아래 중 하나의 CSV 를 넣어두면 자동 인식 (로그인 없이 data.go.kr 에서 다운로드)
  · 한국부동산원_공동주택 단지 식별정보 기본정보  (data.go.kr/data/15106861)
  · 국토교통부_공동주택 단지 기본 정보            (data.go.kr/data/15073271)
파일명에 '공동주택'·'단지' 또는 'household'/'apt'가 들어가면 우선 인식.

매칭: (시도, 시군구정규화, 법정동, 단지명정규화) — enrich_schools.py 와 동일한 주소 정규화.
세대수 열/단지명 열/주소 열 이름은 데이터셋마다 달라서 후보를 모두 시도한다.
"""
import os, csv, json, re
from collections import defaultdict

ROOT=os.path.join(os.path.dirname(__file__),"..")
SEOUL_GU={"종로구","중구","용산구","성동구","광진구","동대문구","중랑구","성북구","강북구","도봉구","노원구","은평구","서대문구","마포구","양천구","강서구","구로구","금천구","영등포구","동작구","관악구","서초구","강남구","송파구","강동구"}

NAME_COLS=["단지명","kaptName","아파트명","공동주택명"]
HH_COLS=["세대수","세대수(세대)","총세대수","hhldCnt","kaptdaCnt"]
FAR_COLS=["용적률","용적율","vlRat","용적률(%)"]   # 면적정보 데이터셋에 포함
ADDR_COLS=["법정동주소","지번주소","주소","소재지지번주소","도로명주소","소재지도로명주소","kaptAddr"]

def find_csv():
    dd=os.path.join(ROOT,"data")
    cands=sorted(f for f in os.listdir(dd) if f.lower().endswith(".csv"))
    pref=[f for f in cands if any(k in f for k in ("공동주택","단지","household","apt","아파트"))
          and "학교" not in f and "subway" not in f.lower() and "school" not in f.lower()]
    return os.path.join(dd,pref[0]) if pref else None

def read_rows(p):
    for enc in ("cp949","utf-8-sig","euc-kr","utf-8"):
        try:
            rows=list(csv.DictReader(open(p,encoding=enc)))
            if rows and len(rows[0])>2: return rows,enc
        except Exception: pass
    return [],None

def col(row,cands):
    for c in cands:
        if c in row and (row[c] or "").strip(): return row[c].strip()
    return ""

def parse_addr(jibun):     # → (sido, gu_norm, dong)
    if not jibun: return None
    toks=jibun.split()
    if not toks: return None
    p=toks[0]
    if p.startswith("서울"): sido="서울"
    elif p.startswith("경기"): sido="경기"
    else: return None
    citygu=[]; dong=None
    for t in toks[1:]:
        if t.endswith(("시","군","구")): citygu.append(t)
        elif t.endswith(("동","가","리")): dong=t; break
        elif t.endswith(("읍","면")): continue
        elif re.match(r"^\d", t): break
    if not dong: return None
    if sido=="서울":
        gu=next((c for c in citygu if c.endswith("구")), None)
        if not gu: return None
        gu_norm=gu
    else:
        si=next((c for c in citygu if c.endswith("시")), None)
        gu=next((c for c in citygu if c.endswith("구")), None)
        if not si: return None
        gu_norm=si[:-1]+(gu[:-1] if gu else "")
    return (sido, gu_norm, dong)

def norm_name(s):
    s=re.sub(r"\(.*?\)","",s or "")
    return re.sub(r"\s+","",s).replace("아파트","")

def to_int(s):
    s=re.sub(r"[^\d]","",s or "")
    return int(s) if s else None

def to_num(s):
    m=re.search(r"\d+(\.\d+)?", (s or "").replace(",",""))
    return float(m.group()) if m else None

def load_hh(p):
    rows,enc=read_rows(p)
    # (sido,gu,dong) -> {name_norm: {"hh":int, "far":float}}
    table=defaultdict(dict)
    n=0
    for r in rows:
        hh=to_int(col(r,HH_COLS)); far=to_num(col(r,FAR_COLS)); nm=col(r,NAME_COLS); addr=col(r,ADDR_COLS)
        if not nm or (hh is None and far is None): continue
        key=parse_addr(addr)
        if not key: continue
        cur=table[key].setdefault(norm_name(nm),{})
        if hh and hh>cur.get("hh",0): cur["hh"]=hh
        if far and not cur.get("far"): cur["far"]=round(far)
        n+=1
    print(f"  단지정보CSV({os.path.basename(p)}, {enc}): 서울·경기 {n}건, 고유 동 {len(table)}곳")
    return table

def apt_key(a):
    sido="서울" if a["gu"] in SEOUL_GU else "경기"
    dong=(a.get("dong") or "").split()[-1] if a.get("dong") else ""
    return (sido, a["gu"], dong)

def main():
    csvp=find_csv()
    if not csvp:
        print("세대수 CSV 없음 → data/ 에 '공동주택 단지 기본정보' CSV를 넣어주세요 "
              "(data.go.kr/data/15106861 또는 15073271, 로그인 없이 다운로드)")
        return
    table=load_hh(csvp)
    apt_path=os.path.join(ROOT,"docs","data","apartments.json")
    d=json.load(open(apt_path,encoding="utf-8"))
    hh_hit=far_hit=0
    for a in d.get("items",[]):
        bucket=table.get(apt_key(a))
        if not bucket: continue
        nn=norm_name(a.get("name",""))
        rec=bucket.get(nn)
        if rec is None:  # 부분일치(포함관계)
            cands=[v for k,v in bucket.items() if nn and (nn in k or k in nn)]
            rec=max(cands,key=lambda x:x.get("hh",0)) if cands else None
        if not rec: continue
        if rec.get("hh"): a["households"]=rec["hh"]; hh_hit+=1
        if rec.get("far"): a["far"]=rec["far"]; far_hit+=1
    json.dump(d, open(apt_path,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"매칭 완료: 세대수 {hh_hit}개 · 용적률 {far_hit}개 / 전체 {len(d.get('items',[]))}개 단지")

if __name__=="__main__": main()
