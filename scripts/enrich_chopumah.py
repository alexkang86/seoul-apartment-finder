#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apartments.json 의 '초품아' 기준을 강화: 단지 800m 반경 내 초등학교 여부.
   - K-apt 기본정보(도로명/지번주소)를 카카오 지오코딩으로 단지 실좌표 변환(캐시)
   - 전국학교.csv 의 서울·경기 초등학교 좌표와 최단거리 계산
   - elem_800m(bool), elem_near_m(최단거리 m) 를 단지에 매칭해 굽는다.
   필요: data/.kakao_key, data/..기본정보..xlsx, data/전국학교.csv, openpyxl
   캐시: data/geo_cache.json {주소질의: [lat,lon] or null}
"""
import os, csv, json, math, time, urllib.request, urllib.parse, urllib.error
import importlib.util
ROOT=os.path.join(os.path.dirname(__file__),"..")
spec=importlib.util.spec_from_file_location("ef",os.path.join(ROOT,"scripts","enrich_far.py"))
ef=importlib.util.module_from_spec(spec); spec.loader.exec_module(ef)  # 헬퍼 재사용

APT=os.path.join(ROOT,"docs","data","apartments.json")
SCHOOL=os.path.join(ROOT,"data","전국학교.csv")
GEO=os.path.join(ROOT,"data","geo_cache.json")
SEOUL_GU=ef.SEOUL_GU
RADIUS=800  # m
DELAY=float(os.environ.get("GEO_DELAY","0.05"))

def load(p,d):
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return d

def kakao_key():
    k=os.environ.get("KAKAO_KEY")
    kp=os.path.join(ROOT,"data",".kakao_key")
    if not k and os.path.exists(kp): k=open(kp).read().strip()
    return k

def haversine_m(la1,lo1,la2,lo2):
    R=6371000.0; r=math.pi/180
    dla=(la2-la1)*r; dlo=(lo2-lo1)*r
    a=math.sin(dla/2)**2+math.cos(la1*r)*math.cos(la2*r)*math.sin(dlo/2)**2
    return 2*R*math.asin(math.sqrt(a))

def geocode(key, q, cache):
    if not q: return None
    if q in cache: return cache[q]
    u="https://dapi.kakao.com/v2/local/search/address.json?"+urllib.parse.urlencode({"query":q})
    res=None
    for _ in range(3):
        try:
            j=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"Authorization":"KakaoAK "+key}),timeout=15).read().decode("utf-8"))
            docs=j.get("documents",[])
            if docs: res=[round(float(docs[0]["y"]),6), round(float(docs[0]["x"]),6)]
            break
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(1); continue
            break
        except Exception: time.sleep(0.5)
    cache[q]=res; time.sleep(DELAY)
    return res

def load_elem_schools():
    pts=[]
    for enc in ("cp949","utf-8-sig","euc-kr","utf-8"):
        try:
            rows=list(csv.DictReader(open(SCHOOL,encoding=enc)))
            if rows and len(rows[0])>2: break
        except Exception: rows=[]
    for r in rows:
        kind=(r.get("학교급구분") or r.get("학교종류명") or "")
        if "초등" not in kind: continue
        addr=(r.get("소재지지번주소") or r.get("소재지도로명주소") or "")
        if not (addr.startswith("서울") or addr.startswith("경기")): continue
        try: la=float(r.get("위도")); lo=float(r.get("경도"))
        except: continue
        if la and lo: pts.append((la,lo))
    return pts

def build_grid(pts, cell=0.01):
    grid={}
    for la,lo in pts: grid.setdefault((round(la/cell),round(lo/cell)),[]).append((la,lo))
    return grid, cell

def nearest_m(la,lo,grid,cell):
    ci,cj=round(la/cell),round(lo/cell); best=9e9
    for i in (ci-1,ci,ci+1):
        for j in (cj-1,cj,cj+1):
            for sla,slo in grid.get((i,j),()):
                d=haversine_m(la,lo,sla,slo)
                if d<best: best=d
    return best if best<9e9 else None

def addr_queries(r):
    # 지오코딩 질의 후보: 도로명주소 → 시도+시군구+동리+번지
    road=ef.nfc(ef.col(r,["도로명주소","소재지도로명주소"]))
    jib =ef.nfc(ef.col(r,ef.ADDR_COLS))
    qs=[]
    if road: qs.append(re_clean(road))
    if jib:  qs.append(re_clean(jib))
    return [q for q in qs if q]

import re
def re_clean(addr):
    # 끝의 단지명/동호수 제거: 번지(숫자[-숫자]) 까지만 남김
    m=re.search(r"^(.*?\d+(?:-\d+)?)(?:\s|번지|$)", addr)
    return (m.group(1) if m else addr).strip()

def main():
    key=kakao_key()
    if not key: print("data/.kakao_key 없음"); return
    rows=ef.read_basic_xlsx()
    if not rows: print("기본정보 xlsx 없음"); return
    schools=load_elem_schools();
    if not schools: print("초등학교 좌표 없음(전국학교.csv 확인)"); return
    grid,cell=build_grid(schools)
    print(f"  서울·경기 초등학교 {len(schools)}개")
    cache=load(GEO,{})
    table={}  # (sido,gu,dong,name_norm) -> near_m
    done=0; geo_calls0=len(cache)
    for r in rows:
        sido=ef.nfc(ef.col(r,ef.SIDO_COLS)); sgg=ef.nfc(ef.col(r,ef.SGG_COLS)); dong=ef.nfc(ef.col(r,ef.DONG_COLS))
        nm=ef.col(r,ef.NAME_COLS)
        if not nm or not (sido.startswith("서울") or sido.startswith("경기")): continue
        coord=None
        for q in addr_queries(r):
            coord=geocode(key,q,cache)
            if coord: break
        if not coord: continue
        nm_m=nearest_m(coord[0],coord[1],grid,cell)
        if nm_m is None: continue
        if sido.startswith("서울"): gu=sgg
        else:
            parts=sgg.split(); si=next((t for t in parts if t.endswith("시")),""); gg=next((t for t in parts if t.endswith("구")),"")
            gu=(si[:-1] if si else "")+(gg[:-1] if gg else "")
        key2=("서울" if sido.startswith("서울") else "경기", gu, dong, ef.norm_name(nm))
        # 같은 키 여러 동 주소면 최소거리 유지
        if key2 not in table or nm_m<table[key2]: table[key2]=nm_m
        done+=1
        if done%500==0:
            print(f"  …지오코딩/계산 {done}건"); json.dump(cache,open(GEO,"w",encoding="utf-8"),ensure_ascii=False)
    json.dump(cache,open(GEO,"w",encoding="utf-8"),ensure_ascii=False)
    print(f"  단지 좌표·최단거리 산출 {len(table)}건 (신규 지오코딩 {len(cache)-geo_calls0}건)")

    d=load(APT,{"items":[]}); hit=within=0
    def apt_key(a):
        sido="서울" if a["gu"] in SEOUL_GU else "경기"
        dong=(a.get("dong") or "").split()[-1] if a.get("dong") else ""
        return (sido,a["gu"],dong,ef.norm_name(a.get("name","")))
    for a in d.get("items",[]):
        m=table.get(apt_key(a))
        if m is None:
            k=apt_key(a); cand=[v for kk,v in table.items() if kk[:3]==k[:3] and (k[3] in kk[3] or kk[3] in k[3]) and k[3]]
            m=min(cand) if cand else None
        if m is None: continue
        a["elem_near_m"]=round(m); a["elem_800m"]=bool(m<=RADIUS); hit+=1; within+=a["elem_800m"]
    json.dump(d,open(APT,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"초품아(800m) 매칭 완료: 거리 산출 {hit}개 / 800m내 {within}개 / 전체 {len(d.get('items',[]))}개")

if __name__=="__main__": main()
