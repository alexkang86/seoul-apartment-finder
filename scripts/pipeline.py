#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울 아파트 후보 탐색 데이터 파이프라인 (국토부 실거래가 공개 API 기반)

하는 일:
  1) 서울 25개 자치구의 '아파트 매매' + '아파트 전월세' 실거래가를 최근 N개월치 수집
  2) 단지(아파트명+법정동)별로 집계:
       - 매매 평당가 / 전세 평당가 / 갭(매매-전세) / 전세가율
       - 건축연도, 전용면적(평형), 근사 방/욕실 수
       - 최근 가격 추세(%)
       - (선택) 동(법정동) 내 초등학교 수  ← school CSV 있으면 매칭
  3) web/data/apartments.json 으로 저장 → 웹 대시보드가 읽음

사용법:
  export MOLIT_SERVICE_KEY="발급받은_디코딩_서비스키"
  python3 scripts/pipeline.py --months 6
  (키 없으면 안내만 출력하고 종료 → 그동안 샘플 데이터로 대시보드 확인 가능)

API: 국토교통부_아파트 매매 실거래가 / 전월세 실거래가 (공공데이터포털 data.go.kr)
"""
import os, sys, json, time, argparse, datetime, math, csv, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

# 서울 25개 자치구 법정동 코드(앞 5자리, LAWD_CD)
SEOUL_LAWD = {
    "종로구":"11110","중구":"11140","용산구":"11170","성동구":"11200","광진구":"11215",
    "동대문구":"11230","중랑구":"11260","성북구":"11290","강북구":"11305","도봉구":"11320",
    "노원구":"11350","은평구":"11380","서대문구":"11410","마포구":"11440","양천구":"11470",
    "강서구":"11500","구로구":"11530","금천구":"11545","영등포구":"11560","동작구":"11590",
    "관악구":"11620","서초구":"11650","강남구":"11680","송파구":"11710","강동구":"11740",
}
# 경기 외곽 통근권(서울 인접) 주요 시·구 LAWD 코드
GG_LAWD = {
    "수원장안":"41111","수원권선":"41113","수원팔달":"41115","수원영통":"41117",
    "성남수정":"41131","성남중원":"41133","성남분당":"41135","의정부":"41150",
    "안양만안":"41171","안양동안":"41173","부천":"41190","광명":"41210",
    "안산상록":"41271","안산단원":"41273","고양덕양":"41281","고양일산동":"41285","고양일산서":"41287",
    "과천":"41290","구리":"41310","남양주":"41360","시흥":"41390","군포":"41410",
    "의왕":"41430","하남":"41450","용인처인":"41461","용인기흥":"41463","용인수지":"41465",
    "김포":"41570","광주":"41610",
    "화성만세":"41591","화성효행":"41593","화성병점":"41595","화성동탄":"41597",
}
ALL_LAWD = {**SEOUL_LAWD, **GG_LAWD}
TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_URL  = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

def months_back(n):
    out=[]; d=datetime.date.today().replace(day=1)
    for _ in range(n):
        out.append(f"{d.year}{d.month:02d}")
        d = (d.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    return out

def fetch(url, key, lawd, ymd, rows=1000):
    qs = urllib.parse.urlencode({
        "serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ymd,
        "numOfRows": rows, "pageNo": 1
    }, safe="%")  # key may already be URL-encoded
    req = urllib.request.Request(url + "?" + qs, headers={
        "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept":"application/xml,text/xml,*/*",
        "Referer":"https://www.data.go.kr/",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

def txt(node, tag):
    e = node.find(tag)
    return (e.text or "").strip() if e is not None and e.text else ""

def parse_items(xml):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    # 에러 메시지 체크
    head = root.find(".//resultCode")
    if head is not None and head.text not in (None,"00","000"):
        msg = txt(root, ".//resultMsg")
        if "SERVICE" in (msg or "") or "KEY" in (msg or "").upper():
            print(f"  ! API 응답: {msg}")
    return root.findall(".//item")

def to_int(s):
    s=(s or "").replace(",","").strip()
    try: return int(float(s))
    except: return None

def rooms_baths_from_area(m2):
    # 전용면적 기반 근사 (한국 아파트 일반적 평형)
    if m2 is None: return (None,None)
    if m2 < 50:  return (2,1)
    if m2 < 66:  return (3,1)   # 전용 59㎡ 대 → 방3/욕실1
    if m2 < 100: return (3,2)   # 전용 84㎡ 대 → 방3/욕실2
    return (4,2)

def load_schools(path):
    """전국 초·중등학교 위치 표준데이터 CSV → 서울 초등학교를 (구,법정동/행정동) 단위 카운트.
       파일 없으면 빈 dict 반환(스킵)."""
    counts = defaultdict(int)
    if not path or not os.path.exists(path):
        return counts
    try:
        with open(path, encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("학교명") or row.get("학교명_한글") or "")
                kind = (row.get("학교급구분") or row.get("학교종류명") or "")
                addr = (row.get("소재지도로명주소") or row.get("소재지지번주소") or row.get("도로명주소") or "")
                if "초등" in kind or name.endswith("초등학교"):
                    if "서울" in addr:
                        # 동 추출(간단): 주소에서 '○○동' 토큰
                        for tok in addr.replace("(", " ").split():
                            if tok.endswith("동") and len(tok) >= 2:
                                counts[tok] += 1
                                break
    except Exception as e:
        print("  ! 학교 CSV 파싱 경고:", e)
    return counts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=6, help="최근 N개월 수집")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs", "data", "apartments.json"))
    ap.add_argument("--schools", default=os.path.join(os.path.dirname(__file__), "..", "data", "schools_seoul.csv"))
    ap.add_argument("--gu", nargs="*", help="특정 구만 (예: 노원구 도봉구). 미지정시 서울 전체")
    ap.add_argument("--gg", action="store_true", help="경기 외곽 통근권 포함(서울+경기)")
    args = ap.parse_args()

    key = os.environ.get("MOLIT_SERVICE_KEY")
    if not key:
        print("="*60)
        print("MOLIT_SERVICE_KEY 환경변수가 없습니다.")
        print("실데이터 수집을 하려면:")
        print("  1) https://www.data.go.kr 회원가입")
        print("  2) '아파트 매매 실거래가' + '아파트 전월세' 오픈API 활용신청(무료, 즉시 승인)")
        print("  3) 발급된 '일반 인증키(Decoding)' 를 환경변수로:")
        print('     export MOLIT_SERVICE_KEY="여기에_키"')
        print("  4) python3 scripts/pipeline.py --months 6")
        print("지금은 샘플 데이터(web/data/apartments.json)로 대시보드를 확인하세요.")
        print("="*60)
        sys.exit(0)

    if args.gu: target = args.gu
    elif args.gg: target = list(ALL_LAWD.keys())
    else: target = list(SEOUL_LAWD.keys())
    ymds = months_back(args.months)
    schools = load_schools(args.schools)
    print(f"수집: {len(target)}개 구 × {len(ymds)}개월 (매매+전세)")

    # 집계 버킷: key = (구, 법정동, 아파트명, 전용면적반올림)  ← 평형별 분리
    def med(xs):
        s=sorted(xs); n=len(s)
        return None if n==0 else (s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2)
    trade = defaultdict(list)   # (ymd, ppp, price, area)
    rent  = defaultdict(list)
    meta  = {}                  # 건축연도
    def keyf(gu, dong, apt, area): return (gu, dong, apt, round(area))  # ㎡ 단위 평형 버킷

    for gu in target:
        lawd = ALL_LAWD[gu]
        for ymd in ymds:
            for url, bucket, is_trade in ((TRADE_URL, trade, True), (RENT_URL, rent, False)):
                try:
                    items = parse_items(fetch(url, key, lawd, ymd))
                except Exception as e:
                    print(f"  ! {gu} {ymd} 요청실패: {e}"); items=[]
                for it in items:
                    apt = txt(it,"aptNm") or txt(it,"아파트")
                    dong = txt(it,"umdNm") or txt(it,"법정동")
                    area = None
                    a = txt(it,"excluUseAr") or txt(it,"전용면적")
                    try: area=float(a)
                    except: pass
                    byear = to_int(txt(it,"buildYear") or txt(it,"건축년도"))
                    if not apt or not area or area<30: continue   # 30㎡ 미만(소형/오피스텔류) 제외
                    pyeong = area/3.305785
                    k = keyf(gu,dong,apt,area)
                    if is_trade:
                        price = to_int(txt(it,"dealAmount") or txt(it,"거래금액"))
                        if not price: continue
                        trade[k].append((ymd, price/pyeong, price, area))
                    else:
                        dep = to_int(txt(it,"deposit") or txt(it,"보증금액"))
                        monthly = to_int(txt(it,"monthlyRent") or txt(it,"월세금액")) or 0
                        if not dep or monthly>0: continue   # 순수 전세만
                        rent[k].append((ymd, dep/pyeong, dep, area))
                    if k not in meta: meta[k]={"built_year":byear}
                    if byear: meta[k]["built_year"]=byear
                time.sleep(0.12)
        print(f"  · {gu} 완료")

    results=[]
    for k, tlist in trade.items():
        gu,dong,apt,abk = k
        if len(tlist) < 1: continue
        trade_ppp = med([x[1] for x in tlist])          # 중앙값(이상치 강건)
        trade_price = med([x[2] for x in tlist])
        area_avg = med([x[3] for x in tlist])
        # 추세: 오래된달 vs 최신달 평당가(중앙값)
        by_m = defaultdict(list)
        for ymd,ppp,_,_ in tlist: by_m[ymd].append(ppp)
        ordered = sorted(by_m.items()); trend=None
        if len(ordered)>=2:
            old=med(ordered[0][1]); new=med(ordered[-1][1])
            if old: trend=round((new-old)/old*100,1)
        # 추정 현재가: 거래가 있는 '가장 최근 2개월'의 매매가 중앙값(오래된 1건이 현재가처럼 보이는 문제 완화)
        recent_months = {ym for ym,_ in ordered[-2:]}
        recent_prices = [x[2] for x in tlist if x[0] in recent_months]
        recent_price = med(recent_prices)
        last_ymd = max(x[0] for x in tlist)             # "YYYYMM"
        last_deal = f"{last_ymd[:4]}.{last_ymd[4:6]}"
        rl = rent.get(k, [])
        jeonse_ppp = med([x[1] for x in rl]) if rl else None
        jeonse_price = med([x[2] for x in rl]) if rl else None
        gap_ratio = round(jeonse_ppp/trade_ppp,3) if (jeonse_ppp and trade_ppp) else None
        # 전세가율 0.3~1.05 벗어나면 데이터 이상 → 갭 제외(매물은 유지)
        if gap_ratio is not None and (gap_ratio>1.05 or gap_ratio<0.3):
            gap_ratio=None; jeonse_ppp=None; jeonse_price=None
        gap_man = round(trade_price - jeonse_price) if (jeonse_price and trade_price) else None
        m = meta.get(k,{}); rooms,baths = rooms_baths_from_area(area_avg)
        elem = schools.get(dong, 0) if schools else None
        results.append({
            "name":apt,"gu":gu,"dong":dong,
            "built_year":m.get("built_year"),
            "area_m2":round(area_avg,1),"pyeong":round(area_avg/3.305785,1),
            "trade_price_man":round(trade_price),"trade_ppp_man":round(trade_ppp),
            "recent_price_man":round(recent_price) if recent_price else None,
            "recent_count":len(recent_prices),"last_deal":last_deal,
            "jeonse_price_man":round(jeonse_price) if jeonse_price else None,
            "jeonse_ppp_man":round(jeonse_ppp) if jeonse_ppp else None,
            "gap_ratio":gap_ratio,"gap_man":gap_man,
            "trend_pct":trend,"trade_count":len(tlist),
            "elem_school_count":elem,
            "rooms_est":rooms,"baths_est":baths,
        })
    results.sort(key=lambda r:(-(r["gap_ratio"] or 0), r["trade_price_man"]))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out,"w",encoding="utf-8") as f:
        json.dump({"updated":datetime.datetime.now().isoformat(timespec="minutes"),
                   "count":len(results),"items":results}, f, ensure_ascii=False, indent=1)
    print(f"\n완료: {len(results)}개 단지 → {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()
