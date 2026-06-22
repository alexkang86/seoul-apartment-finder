#!/bin/bash
# 매일 실거래가 재수집 → 학교/단지번호 갱신 → 깃허브 푸시(= Pages 자동 업데이트)
# launchd(매일) 또는 수동 실행. data/.molit_key 에 국토부 키가 있어야 동작.
cd "$(dirname "$0")/.." || exit 1
exec >> /tmp/aptfinder_refresh.log 2>&1
echo "===== $(date '+%F %T') 자동갱신 시작 ====="

[ -f data/.molit_key ] && export MOLIT_SERVICE_KEY="$(tr -d '[:space:]' < data/.molit_key)"
if [ -z "$MOLIT_SERVICE_KEY" ]; then
  echo "키 없음(data/.molit_key) → 갱신 건너뜀"; exit 0
fi

python3 scripts/pipeline.py --gg --months 6 || { echo "pipeline 실패"; exit 1; }
python3 scripts/enrich_schools.py || { echo "enrich 실패"; exit 1; }
python3 scripts/enrich_households.py || echo "세대수 보강 건너뜀(CSV 없음/openpyxl 미설치)"
RESOLVE_LIMIT=3000 RESOLVE_DELAY=0.2 python3 scripts/resolve_complexno.py || true

git add docs/data/apartments.json data/complexno_cache.json
if git diff --cached --quiet; then
  echo "변경 없음 → 커밋 생략"
else
  git commit -m "data: 실거래가 자동갱신 $(date +%F)" && git push && echo "푸시 완료 → Pages 갱신됨"
fi
echo "===== 완료 ====="
