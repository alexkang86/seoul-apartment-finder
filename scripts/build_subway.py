#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수도권 전철 역/노선 + GTX(A·B·C) → docs/data/subway.json 으로 굽는다.
   지도 레이어(노선 실선 + 역점 + GTX) & 카드 '가까운 GTX역 거리'에 사용.

   입력
     data/subway_stations.csv  : 수도권 전철 589역 좌표(점, 전 노선) → 역 점(dot)
     data/subway_lines.json    : 1~9호선·분당·신분당의 '노선 순서대로' 역 좌표 → 실선 노선
   GTX
     운영 구간은 실선, 예정(공사중·계획) 구간은 점선으로 그리도록 세그먼트별 open 플래그 출력.
     좌표는 기존 역과 겹치면 CSV에서, 신설역은 MANUAL 좌표.
"""
import os, csv, json, datetime
from collections import OrderedDict

ROOT = os.path.join(os.path.dirname(__file__), "..")
CSV  = os.path.join(ROOT, "data", "subway_stations.csv")
LINESRC = os.path.join(ROOT, "data", "subway_lines.json")
OUT  = os.path.join(ROOT, "docs", "data", "subway.json")

LINE_COLOR = {
    "1호선":"#0052A4","2호선":"#00A84D","3호선":"#EF7C1C","4호선":"#00A5DE",
    "5호선":"#996CAC","6호선":"#CD7C2F","7호선":"#747F00","8호선":"#E6186C",
    "9호선":"#BDB092","분당선":"#FABE00","신분당선":"#D31145",
}

MANUAL = {
    "킨텍스": (37.6685, 126.7460), "창릉": (37.6516, 126.8930),
    "서울역": (37.5547, 126.9707), "성남": (37.3935, 127.1115),
    "동탄": (37.2008, 127.0985), "운정중앙": (37.7262, 126.7680),
}

# GTX: (역명, 역상태, 다음 역까지 구간이 '운영중'인가)  마지막 역의 세그 플래그는 무시
GTX = [
    ("GTX-A", "#8E44AD", [
        ("운정중앙","운영",True),("킨텍스","운영",True),("대곡","운영",True),("창릉","공사중",True),
        ("연신내","운영",True),("서울역","운영",False),("삼성","공사중",False),("수서","운영",True),
        ("성남","운영",True),("구성","운영",True),("동탄","운영",False),
    ]),
    ("GTX-B", "#2980B9", [
        ("인천대입구","공사중",False),("인천시청","공사중",False),("부평","공사중",False),("부천종합운동장","공사중",False),
        ("신도림","계획",False),("여의도","공사중",False),("용산","공사중",False),("서울역","공사중",False),
        ("청량리","공사중",False),("망우","공사중",False),("별내","공사중",False),("평내호평","공사중",False),("마석","공사중",False),
    ]),
    ("GTX-C", "#C0392B", [
        ("덕정","계획",False),("의정부","계획",False),("창동","계획",False),("광운대","계획",False),("청량리","계획",False),
        ("왕십리","계획",False),("삼성","계획",False),("양재","계획",False),("정부과천청사","계획",False),
        ("인덕원","계획",False),("금정","계획",False),("수원","계획",False),
    ]),
]

def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    coord = {}
    for r in rows:
        coord.setdefault(r["name"], (round(float(r["lat"]),6), round(float(r["lon"]),6)))

    # 일반 역 점(전체 589)
    stations = [[la, lo, n] for n,(la,lo) in coord.items()]

    # 노선 실선: subway_lines.json 을 노선별·순서대로 폴리라인화
    lines = []
    if os.path.exists(LINESRC):
        src = json.load(open(LINESRC, encoding="utf-8"))
        by = OrderedDict()
        for r in src:
            by.setdefault(r["line"], []).append([r["lat"], r["lon"]])
        for name, pts in by.items():
            lines.append({"name": name, "color": LINE_COLOR.get(name, "#888"), "pts": pts})

    def resolve(name):
        if name in MANUAL: return MANUAL[name]
        if name in coord:  return coord[name]
        hit = next((k for k in coord if name in k or k in name), None)
        return coord[hit] if hit else None

    gtx, missing = [], []
    for line, color, seq in GTX:
        sts, segs = [], []
        for i,(nm, status, openNext) in enumerate(seq):
            c = resolve(nm)
            if not c: missing.append(f"{line}:{nm}"); continue
            sts.append({"name": nm, "lat": c[0], "lon": c[1], "status": status})
            if i < len(seq)-1: segs.append(bool(openNext))
        gtx.append({"line": line, "color": color, "stations": sts, "segs": segs})

    out = {"updated": datetime.date.today().isoformat(),
           "stations": stations, "lines": lines, "gtx": gtx}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
    print(f"subway.json: 역점 {len(stations)} · 노선 {len(lines)}개({sum(len(l['pts']) for l in lines)}점) · "
          f"GTX {sum(len(g['stations']) for g in gtx)}역")
    if missing: print("  ! 좌표 못 찾음:", missing)

if __name__ == "__main__": main()
