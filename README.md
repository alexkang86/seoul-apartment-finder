# 🏠 서울·경기 아파트 후보 탐색기

국토교통부 **실거래가 공개 데이터**(합법·무료)로 **서울+경기 통근권** 아파트를
내 조건에 맞게 찾아 순위를 매겨주는 **개인용 웹 도구(PWA)**.
네이버 부동산 스크래핑(약관 위반) 없이 동작.

> ⚠️ **후보를 좁혀주는 보조 도구**입니다. 실시간 매물이 아니라 실거래가 기반이며,
> 방/욕실 수는 전용면적 기반 근사치, **전세가율 90%+는 깡통전세 위험**입니다.
> **최종 결정 전 현장 확인·전문가 상담·대출 한도(은행)** 를 반드시 확인하세요.

## 기능
- **조건 필터**: 매매가·건축연도·전용면적(59/84형 버튼)·방/욕실·전세가율 범위·추세 임계값·지역(서울/경기)·시구
- **프리셋 버튼**: 신축 균형형 / 갭 우선(실거주) / 저가 신축형 / 넓은집(방4)
- **종합 점수 가중치 조절**: 갭·신축·상승세·학교 비중 슬라이더
- **깡통전세 회피**: 전세가율 95%+ 자동 숨김 옵션
- **설정 저장**: 필터·가중치 새로고침해도 유지
- **카드 + 지도(OpenStreetMap)** 보기
- **서울 초품아**: 동별 초등학교 수 표시 (경기는 미포함)

## 실행
```bash
cd ~/Desktop/seoul-apartment-finder
python3 -m http.server 8000 --directory web
# 브라우저 → http://localhost:8000
# 폰: 같은 와이파이로 http://(맥IP):8000 → 공유 → '홈 화면에 추가' (앱처럼)
```

## 데이터 갱신 (실거래가)
```bash
export MOLIT_SERVICE_KEY="data.go.kr 발급 Decoding 키"
python3 scripts/pipeline.py --months 6 --gg     # 서울+경기, 최근 6개월
python3 scripts/enrich_schools.py               # 서울 초품아 정보 추가
```
- `pipeline.py` : 국토부 아파트 매매(상세)+전월세 실거래가 수집 → 평형별 분리·중앙값·이상치 제거 → `web/data/apartments.json`
- `enrich_schools.py` : `data/schools_seoul.csv`(NEIS 학교기본정보)로 서울 동별 초등학교 수 매칭

## (선택) 매일 알림 — 텔레그램
```bash
export TG_BOT_TOKEN="..."; export TG_CHAT_ID="..."
python3 scripts/alert.py          # config.json 기준 조건 충족 단지 발송
# cron:  0 9 * * * cd ~/Desktop/seoul-apartment-finder && python3 scripts/pipeline.py --months 6 --gg && python3 scripts/enrich_schools.py && python3 scripts/alert.py
```

## 한계
- 방/욕실은 전용면적 근사(59㎡≈방3/욕1, 84㎡≈방3/욕2). 실제는 단지마다 다름 → 최종 확인 필수.
- 실거래가 기반(일~월 갱신), 실시간 매물 아님.
- 초품아는 **서울만** 데이터 보유(경기 미포함) → 경기 후보는 카카오맵에서 직접 확인.
- 용적률·세대수 등 단지 상세는 미포함(실거래가 API에 없음).
