#!/bin/bash
# PyQt5 GUI 실행 스크립트 (macOS 안정화)

cd "$(dirname "$0")"

# venv 비활성화 (있다면)
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate 2>/dev/null || true
    unset VIRTUAL_ENV
fi

# macOS PyQt5 안정화 환경 변수
export QT_MAC_WANTS_LAYER=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1  
export QT_ENABLE_HIGHDPI_SCALING=1
export QT_LOGGING_RULES="*.debug=false;qt.qpa.*=false"

echo "🎬 영상 다운로더 서버 GUI 시작 중..."
echo "📌 시스템 Python3 사용 (venv 제외)"
echo ""

# 시스템 Python3 직접 실행
/usr/bin/python3 server_controller.py
