#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수도권 전철 역 좌표(data/subway_stations.csv) + GTX A·B·C(미개통·계획역 포함)를
   docs/data/subway.json 으로 굽는다. 지도 레이어 + 카드 '가까운 GTX역 거리'에 사용.

   - 일반 전철역: 589개(서울+수도권 전 노선) → 작은 회색 점
   - GTX: 노선별 색, 큰 마커. 좌표는 기존 역과 겹치면 CSV에서 빌려오고,
          신설역(킨텍스·창릉 등)은 아래 MANUAL 좌표 사용.
   상태(status): 운영 / 공사중 / 계획  (정밀 개통일이 아니라 표시용 구분)
"""
import os, csv, json, datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
CSV  = os.path.join(ROOT, "data", "subway_stations.csv")
OUT  = os.path.join(ROOT, "docs", "data", "subway.json")

# 신설(또는 동명이역과 구분 필요한) GTX역 좌표 직접 지정
MANUAL = {
    "킨텍스": (37.6685, 126.7460),
    "창릉":   (37.6516, 126.8930),
    "서울역": (37.5547, 126.9707),
    "성남":   (37.3935, 127.1115),   # GTX 성남(판교 인근)
    "동탄":   (37.2008, 127.0985),   # GTX 동탄(서동탄과 다름)
    "운정중앙": (37.7262, 126.7680),
}

# (노선, 색, [ (역명, 상태) ... ])  순서 = 노선 순서
GTX = [
    ("GTX-A", "#8E44AD", [
        ("운정중앙","공사중"),("킨텍스","공사중"),("대곡","운영"),("창릉","공사중"),
        ("연신내","운영"),("서울역","운영"),("삼성","공사중"),("수서","운영"),
        ("성남","운영"),("구성","운영"),("동탄","운영"),
    ]),
    ("GTX-B", "#2980B9", [
        ("인천대입구","공사중"),("인천시청","공사중"),("부평","공사중"),("부천종합운동장","공사중"),
        ("신도림","계획"),("여의도","공사중"),("용산","공사중"),("서울역","공사중"),
        ("청량리","공사중"),("망우","공사중"),("별내","공사중"),("평내호평","공사중"),("마석","공사중"),
    ]),
    ("GTX-C", "#C0392B", [
        ("덕정","계획"),("의정부","계획"),("창동","계획"),("광운대","계획"),("청량리","계획"),
        ("왕십리","계획"),("삼성","계획"),("양재","계획"),("정부과천청사","계획"),
        ("인덕원","계획"),("금정","계획"),("수원","계획"),
    ]),
]

def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    coord = {}
    for r in rows:
        coord.setdefault(r["name"], (round(float(r["lat"]),6), round(float(r["lon"]),6)))

    def resolve(name):
        if name in MANUAL: return MANUAL[name]
        if name in coord:  return coord[name]
        hit = next((k for k in coord if name in k or k in name), None)
        return coord[hit] if hit else None

    stations = [[la, lo, n] for n,(la,lo) in coord.items()]   # 일반역(전체)

    gtx = []
    missing = []
    for line, color, seq in GTX:
        sts = []
        for nm, status in seq:
            c = resolve(nm)
            if not c: missing.append(f"{line}:{nm}"); continue
            sts.append({"name": nm, "lat": c[0], "lon": c[1], "status": status})
        gtx.append({"line": line, "color": color, "stations": sts})

    out = {"updated": datetime.date.today().isoformat(),
           "stations": stations, "gtx": gtx}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
    print(f"subway.json: 일반역 {len(stations)}개 · GTX {sum(len(g['stations']) for g in gtx)}개 "
          f"({', '.join(g['line']+str(len(g['stations'])) for g in gtx)})")
    if missing: print("  ! 좌표 못 찾음:", missing)

if __name__ == "__main__": main()
