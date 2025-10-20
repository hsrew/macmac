#!/bin/bash
# 더블클릭으로 실행 가능한 스크립트

cd "$(dirname "$0")"

# venv 비활성화
unset VIRTUAL_ENV
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"

# 시스템 Python3로 실행
/usr/bin/python3 server_controller.py


