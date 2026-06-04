#!/bin/bash
# 더블클릭하면: 로컬 서버 실행 + 브라우저 자동 오픈
# (이 창을 닫으면 서버가 종료됩니다)
cd "$(dirname "$0")"

PORT=8000
# 기존에 켜져 있던 같은 포트 서버 정리
lsof -ti:$PORT 2>/dev/null | xargs kill 2>/dev/null

echo "🏠 서울·경기 아파트 후보 탐색기"
echo "-----------------------------------"
echo "서버 시작 중... (포트 $PORT)"

# 백그라운드로 서버 실행 (정적 서빙 + NPay 부동산 단지 직링크 프록시)
PORT=$PORT python3 scripts/server.py >/dev/null 2>&1 &
SERVER_PID=$!
sleep 1

# 브라우저 열기 (매번 고유 주소 → 캐시된 옛 화면 대신 항상 최신 로드)
open "http://localhost:$PORT/?t=$(date +%s)"

echo "✅ 실행됨 →  http://localhost:$PORT"
echo ""

# ── 실거래가 자동 갱신: 데이터가 2일 이상 묵었고 API 키가 있으면 백그라운드로 최신화 ──
[ -f data/.molit_key ] && export MOLIT_SERVICE_KEY="$(cat data/.molit_key)"
DATA="web/data/apartments.json"
if [ -n "$MOLIT_SERVICE_KEY" ]; then
  if [ -n "$(find "$DATA" -mtime +2 2>/dev/null)" ]; then
    echo "🔄 실거래가가 오래되어 백그라운드로 갱신합니다 (몇 분 소요, 끝나면 화면에 알림)..."
    ( touch data/.refreshing
      python3 scripts/pipeline.py --gg --months 6 >/dev/null 2>&1 \
        && python3 scripts/enrich_schools.py >/dev/null 2>&1
      rm -f data/.refreshing ) &
  else
    echo "✅ 실거래가 최신 상태(2일 이내)."
  fi
else
  echo "ℹ️  자동 갱신 끄짐(키 없음). 켜려면 한 번만:  echo '발급키' > data/.molit_key"
fi
echo ""
echo "📱 폰에서도 보려면(같은 와이파이): http://$(ipconfig getifaddr en0 2>/dev/null || echo '맥IP'):$PORT"
echo ""
echo "⛔ 종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요."

# 창이 닫힐 때 서버도 종료
trap "kill $SERVER_PID 2>/dev/null" EXIT
wait $SERVER_PID
