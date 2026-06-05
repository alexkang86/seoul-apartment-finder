#!/bin/bash
# 한 번만 실행 → ① 국토부 키 저장 ② 화면 항상 켜짐 ③ 매일 06:00 자동갱신(깃허브 푸시→Pages 갱신)
# 사용법:  bash scripts/setup_local_auto.sh '국토부_디코딩_키'
KEY="$1"
PROJ="$HOME/Desktop/seoul-apartment-finder"
LA="$HOME/Library/LaunchAgents"
mkdir -p "$LA" "$PROJ/data"

# ① 키 저장(전달했을 때만)
if [ -n "$KEY" ]; then
  printf '%s' "$KEY" > "$PROJ/data/.molit_key"
  chmod 600 "$PROJ/data/.molit_key"
  echo "✅ 국토부 키 저장됨 (data/.molit_key)"
else
  echo "ℹ️  키 인자 없음 → data/.molit_key 가 이미 있어야 자동갱신 동작"
fi

# ② 화면/잠자기 방지 에이전트
cat > "$LA/com.alexkang.aptfinder.awake.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alexkang.aptfinder.awake</string>
  <key>ProgramArguments</key><array><string>/usr/bin/caffeinate</string><string>-dimsu</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>
PLIST

# ③ 매일 06:00 자동갱신 에이전트
cat > "$LA/com.alexkang.aptfinder.refresh.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alexkang.aptfinder.refresh</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>/Users/alex86/Desktop/seoul-apartment-finder/scripts/refresh_and_push.sh</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/aptfinder_refresh.log</string>
  <key>StandardErrorPath</key><string>/tmp/aptfinder_refresh.log</string>
</dict></plist>
PLIST

# 로드(재등록)
for L in awake refresh; do
  P="$LA/com.alexkang.aptfinder.$L.plist"
  launchctl unload "$P" 2>/dev/null
  launchctl load -w "$P" 2>/dev/null && echo "✅ $L 등록됨"
done
echo ""
echo "끝! 화면 항상 켜짐 + 매일 06:00 자동갱신(→ GitHub Pages 자동 업데이트)."
echo "지금 즉시 한 번 갱신해보려면:  bash scripts/refresh_and_push.sh"
