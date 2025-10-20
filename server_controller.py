#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 영상 다운로더 서버 컨트롤러 (개선 버전)
- 빠른 재생 속도
- 현대적인 UI
- 안정적인 스트리밍
"""

import sys
import os
import webbrowser
import socket
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QTextEdit, QGroupBox, QMessageBox,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QLineEdit, QListWidget, QListWidgetItem, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, Response, make_response
from flask_cors import CORS
import yt_dlp
import instaloader
import json
from datetime import datetime
import re
import cv2
from PIL import Image
from functools import wraps

# 🎯 포맷 이력 관리 파일 (학습 시스템)
FORMAT_HISTORY_FILE = 'format_history.json'

# ============================================================================
# Flask 서버 설정
# ============================================================================

class VideoDownloaderServer:
    """영상 다운로더 Flask 서버 (개선 버전)"""
    
    def __init__(self, port=7777, gui_log_callback=None):
        self.port = port
        self.app = Flask(__name__)
        self.app.secret_key = 'video-downloader-secret-key-2025'
        
        # CORS 설정 (모든 도메인 허용)
        CORS(self.app)
        
        # 🔋 macOS 잠금 방지 (caffeinate)
        self.caffeinate_process = None
        self.prevent_sleep()
        
        # 서버 안정성 설정
        self.app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 캐시 비활성화
        
        # 다운로드 중복 방지
        self.downloading_files = set()
        
        # 접속자 추적
        self.active_sessions = {}  # session_id: {ip, user_agent, device, browser, last_active}
        
        self.server_thread = None
        self.server_instance = None
        self.is_running = False
        
        # GUI 로그 콜백 함수
        self.gui_log_callback = gui_log_callback
        
        # 👥 사용자 관리
        self.USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
        self.BLOCKED_IPS_FILE = os.path.join(os.path.dirname(__file__), 'blocked_ips.json')
        self.init_users_db()
        self.init_blocked_ips()
        
        # 영상 저장 디렉토리
        self.VIDEOS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'videos')
        os.makedirs(self.VIDEOS_DIR, exist_ok=True)
        
        # 템플릿 디렉토리 확인/생성
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(templates_dir, exist_ok=True)
        
        # HTML 템플릿 생성
        self.create_templates()
        
        # 라우트 설정
        self.setup_routes()
    
    def create_templates(self):
        """HTML 템플릿 자동 생성 - 사용하지 않음 (외부 파일 사용)"""
        pass
    
    def parse_user_agent(self, user_agent):
        """User-Agent 문자열 파싱"""
        import re
        ua_lower = user_agent.lower()
        
        # 디바이스 감지
        if 'iphone' in ua_lower:
            device = '📱 iPhone'
        elif 'ipad' in ua_lower:
            device = '📱 iPad'
        elif 'android' in ua_lower:
            # Android 기종 추출
            if 'samsung' in ua_lower or 'sm-' in ua_lower:
                device = '📱 Samsung Galaxy'
            elif 'pixel' in ua_lower:
                device = '📱 Google Pixel'
            elif 'xiaomi' in ua_lower or 'redmi' in ua_lower:
                device = '📱 Xiaomi'
            elif 'huawei' in ua_lower:
                device = '📱 Huawei'
            elif 'lg' in ua_lower:
                device = '📱 LG'
            else:
                device = '📱 Android'
        elif 'macintosh' in ua_lower or 'mac os' in ua_lower:
            device = '💻 Mac'
        elif 'windows' in ua_lower:
            device = '💻 Windows'
        elif 'linux' in ua_lower:
            device = '💻 Linux'
        elif 'tesla' in ua_lower:
            device = '🚗 Tesla'
        else:
            device = '🖥️ Unknown'
        
        # OS 버전 추출
        os_version = 'Unknown'
        if 'android' in ua_lower:
            match = re.search(r'android (\d+\.?\d*)', ua_lower)
            if match:
                os_version = f'Android {match.group(1)}'
        elif 'iphone os' in ua_lower or 'cpu os' in ua_lower:
            match = re.search(r'os (\d+_\d+)', ua_lower)
            if match:
                os_version = f'iOS {match.group(1).replace("_", ".")}'
        elif 'mac os x' in ua_lower:
            match = re.search(r'mac os x (\d+[_\.]\d+)', ua_lower)
            if match:
                os_version = f'macOS {match.group(1).replace("_", ".")}'
        elif 'windows nt' in ua_lower:
            match = re.search(r'windows nt (\d+\.\d+)', ua_lower)
            if match:
                nt_version = match.group(1)
                win_versions = {
                    '10.0': 'Windows 10/11',
                    '6.3': 'Windows 8.1',
                    '6.2': 'Windows 8',
                    '6.1': 'Windows 7'
                }
                os_version = win_versions.get(nt_version, f'Windows NT {nt_version}')
        
        # 브라우저 감지
        if 'edg' in ua_lower:
            browser = '🌐 Edge'
        elif 'chrome' in ua_lower and 'safari' in ua_lower:
            browser = '🌐 Chrome'
        elif 'firefox' in ua_lower:
            browser = '🌐 Firefox'
        elif 'safari' in ua_lower and 'chrome' not in ua_lower:
            browser = '🌐 Safari'
        elif 'opera' in ua_lower or 'opr' in ua_lower:
            browser = '🌐 Opera'
        else:
            browser = '🌐 Unknown'
        
        return {
            'device': device,
            'os': os_version,
            'browser': browser
        }
    
    # ========================================================================
    # 👥 사용자 관리
    # ========================================================================
    
    def init_users_db(self):
        """사용자 데이터베이스 초기화"""
        if not os.path.exists(self.USERS_FILE):
            # 기본 관리자 계정 생성
            users_data = {
                'admin': {
                    'password': 'admin1234',
                    'created_at': datetime.now().isoformat()
                }
            }
            with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
    
    def get_user_dir(self, username):
        """사용자별 디렉토리 경로 반환"""
        user_dir = os.path.join(self.VIDEOS_DIR, username)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    def get_user_metadata_file(self, username):
        """사용자별 metadata.json 경로"""
        return os.path.join(self.get_user_dir(username), 'metadata.json')
    
    def get_user_playlist_file(self, username):
        """사용자별 playlist.json 경로"""
        return os.path.join(self.get_user_dir(username), 'playlist.json')
    
    def get_user_favorites_file(self, username):
        """사용자별 즐겨찾기 파일 경로"""
        return os.path.join(self.get_user_dir(username), 'favorites.json')
    
    def register_user(self, username, password):
        """회원가입"""
        try:
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            if username in users:
                return False, "이미 존재하는 아이디입니다"
            
            users[username] = {
                'password': password,
                'created_at': datetime.now().isoformat()
            }
            
            with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            
            # 사용자 디렉토리 생성
            self.get_user_dir(username)
            
            return True, "회원가입 성공"
        except Exception as e:
            return False, f"회원가입 실패: {str(e)}"
    
    def verify_user(self, username, password):
        """로그인 검증"""
        try:
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            if username not in users:
                return False
            
            return users[username]['password'] == password
        except:
            return False
    
    def init_blocked_ips(self):
        """차단된 IP 데이터베이스 초기화"""
        if not os.path.exists(self.BLOCKED_IPS_FILE):
            with open(self.BLOCKED_IPS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def is_ip_blocked(self, ip):
        """IP 차단 여부 확인"""
        try:
            with open(self.BLOCKED_IPS_FILE, 'r', encoding='utf-8') as f:
                blocked_ips = json.load(f)
            return ip in blocked_ips
        except:
            return False
    
    def block_user_ip(self, username):
        """사용자의 마지막 접속 IP 차단"""
        try:
            # 사용자의 마지막 접속 IP 찾기
            user_ip = None
            for session_id, info in self.active_sessions.items():
                if info.get('username') == username:
                    user_ip = info.get('ip')
                    break
            
            if not user_ip:
                return False, "사용자의 IP를 찾을 수 없습니다"
            
            # IP 차단 목록에 추가
            with open(self.BLOCKED_IPS_FILE, 'r', encoding='utf-8') as f:
                blocked_ips = json.load(f)
            
            if user_ip not in blocked_ips:
                blocked_ips.append(user_ip)
                with open(self.BLOCKED_IPS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(blocked_ips, f, indent=2)
            
            # 사용자 계정 삭제
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            if username in users:
                del users[username]
                with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(users, f, ensure_ascii=False, indent=2)
            
            return True, f"{username} 차단 완료 (IP: {user_ip})"
        except Exception as e:
            return False, f"차단 실패: {str(e)}"
    
    def get_all_users(self):
        """모든 사용자 목록 반환"""
        try:
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            # 각 사용자의 활동 정보 추가
            user_list = []
            for username, info in users.items():
                user_info = {
                    'username': username,
                    'created_at': info.get('created_at', 'Unknown'),
                    'is_online': False,
                    'ip': None
                }
                
                # 현재 접속 중인지 확인
                for session_id, session_info in self.active_sessions.items():
                    if session_info.get('username') == username:
                        user_info['is_online'] = True
                        user_info['ip'] = session_info.get('ip')
                        break
                
                user_list.append(user_info)
            
            return user_list
        except:
            return []
    
    def change_user_password(self, username, new_password):
        """사용자 비밀번호 강제 변경 (admin 포함)"""
        try:
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            
            if username not in users:
                return False, "사용자를 찾을 수 없습니다"
            
            users[username]['password'] = new_password
            
            with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            
            return True, f"{username}의 비밀번호가 변경되었습니다"
        except Exception as e:
            return False, f"비밀번호 변경 실패: {str(e)}"
    
    def get_pin_code(self):
        """PIN 비밀번호 불러오기"""
        pin_file = os.path.join(os.path.dirname(__file__), 'pin_code.txt')
        
        if os.path.exists(pin_file):
            try:
                with open(pin_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                return '12345'
        
        return '12345'
    
    def share_content_to_users(self, from_username, to_usernames, video_id, title, thumbnail, duration, content_type='audio', filename=None):
        """컨텐츠 공유 (음원/영상)"""
        try:
            self.log(f"🔍 공유 시작: content_type={content_type}, video_id={video_id}")
            
            shared_count = 0
            for to_username in to_usernames:
                if to_username == from_username:
                    continue  # 자신에게는 공유 안 함
                
                if content_type == 'audio':
                    # 🎵 음원 공유: 재생 목록에만 추가
                    self.log(f"🎵 음원 모드 - 재생 목록에만 추가 시작")
                    playlist = self.load_playlist(to_username)
                    
                    # 이미 있는지 확인
                    already_exists = False
                    for item in playlist:
                        if item.get('video_id') == video_id:
                            already_exists = True
                            break
                    
                    if not already_exists:
                        playlist.append({
                            'url': f'https://www.youtube.com/watch?v={video_id}',
                            'title': title,
                            'thumbnail': thumbnail,
                            'duration': duration,
                            'video_id': video_id,
                            'added_at': datetime.now().isoformat(),
                            'shared_from': from_username
                        })
                        self.save_playlist(playlist, to_username)
                        self.log(f"✅ 🎵 음원 공유 완료 - 재생 목록에만 추가됨: {to_username} - {title}")
                    else:
                        self.log(f"⚠️ 이미 재생 목록에 있음: {to_username} - {title}")
                    
                    # 갤러리에는 절대 추가 안 함!
                    self.log(f"✅ 갤러리 건너뜀 (음원 모드)")
                    
                elif content_type == 'video':
                    # 📹 영상 공유: 갤러리에만 추가 (실제 파일명 사용)
                    self.log(f"📹 영상 모드 - 갤러리에만 추가 시작")
                    metadata = self.load_metadata(to_username)
                    
                    # metadata가 list인지 확인하고 추가
                    if not isinstance(metadata, list):
                        metadata = []
                    
                    # 이미 있는지 확인
                    already_in_gallery = False
                    for item in metadata:
                        if isinstance(item, dict) and item.get('video_id') == video_id:
                            already_in_gallery = True
                            break
                    
                    if not already_in_gallery:
                        # 갤러리에 추가 (실제 파일명 사용 - 공유자의 파일 직접 재생)
                        metadata.insert(0, {
                            'filename': filename or f'{video_id}_shared.mp4',  # 실제 파일명 사용!
                            'title': title,
                            'url': f'https://www.youtube.com/watch?v={video_id}',
                            'platform': 'youtube',
                            'thumbnail': thumbnail,
                            'duration': duration,
                            'video_id': video_id,
                            'downloaded_at': datetime.now().isoformat(),
                            'shared_from': from_username,
                            'is_shared': True  # 공유받은 영상 표시
                        })
                        self.save_metadata(metadata, to_username)
                        self.log(f"✅ 📹 영상 공유 완료 - 갤러리에만 추가됨: {to_username} - {title} (파일: {filename})")
                    else:
                        self.log(f"⚠️ 이미 갤러리에 있음: {to_username} - {title}")
                    
                    # 재생 목록에는 절대 추가 안 함!
                    self.log(f"✅ 재생 목록 건너뜀 (영상 모드)")
                
                else:
                    self.log(f"❌ 알 수 없는 content_type: {content_type}")
                
                shared_count += 1
            
            content_name = '음원' if content_type == 'audio' else '영상'
            return True, f"{shared_count}명에게 {content_name} 공유 완료"
        except Exception as e:
            import traceback
            self.log(f"❌ 공유 실패: {str(e)}\n{traceback.format_exc()}")
            return False, f"공유 실패: {str(e)}"
    
    # ========================================================================
    # 🔋 macOS 잠금 방지
    # ========================================================================
    
    def prevent_sleep(self):
        """macOS 잠금 방지 시작"""
        try:
            if sys.platform == 'darwin':  # macOS only
                # caffeinate: 시스템 잠금 방지 (-d: 디스플레이 슬립 방지, -i: 유휴 슬립 방지)
                self.caffeinate_process = subprocess.Popen(
                    ['caffeinate', '-di'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("🔋 macOS 잠금 방지 활성화 (caffeinate)")
        except Exception as e:
            print(f"⚠️ caffeinate 실행 실패: {e}")
    
    def allow_sleep(self):
        """macOS 잠금 방지 해제"""
        try:
            if self.caffeinate_process:
                self.caffeinate_process.terminate()
                self.caffeinate_process.wait(timeout=5)
                self.caffeinate_process = None
                print("🔋 macOS 잠금 방지 해제")
        except Exception as e:
            print(f"⚠️ caffeinate 종료 실패: {e}")
    
    # ========================================================================
    # 📝 로그 출력 헬퍼
    # ========================================================================
    
    def log(self, message):
        """로그 출력 (콘솔 + GUI)"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        
        # 콘솔 출력
        print(log_message)
        
        # GUI 로그 출력
        if self.gui_log_callback:
            try:
                self.gui_log_callback(message)
            except Exception as e:
                print(f"GUI 로그 전송 실패: {e}")
    
    # ========================================================================
    # 🎯 포맷 이력 관리 (학습 시스템)
    # ========================================================================
    
    def load_format_history(self):
        """포맷 이력 로드"""
        try:
            if os.path.exists(FORMAT_HISTORY_FILE):
                with open(FORMAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ 포맷 이력 로드 실패: {e}")
        return {}
    
    def save_format_history(self, history):
        """포맷 이력 저장"""
        try:
            with open(FORMAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 포맷 이력 저장 실패: {e}")
    
    def record_format_success(self, video_id, format_string, is_mobile=False):
        """포맷 성공 기록"""
        history = self.load_format_history()
        
        if video_id not in history:
            history[video_id] = {
                'success_format': None,
                'failed_formats': [],
                'last_updated': None,
                'success_count': 0,
                'device': 'mobile' if is_mobile else 'desktop'
            }
        
        history[video_id]['success_format'] = format_string
        history[video_id]['success_count'] = history[video_id].get('success_count', 0) + 1
        history[video_id]['last_updated'] = datetime.now().isoformat()
        history[video_id]['device'] = 'mobile' if is_mobile else 'desktop'
        
        # 성공하면 failed_formats에서 제거
        if format_string in history[video_id].get('failed_formats', []):
            history[video_id]['failed_formats'].remove(format_string)
        
        self.save_format_history(history)
        print(f"✅ 포맷 학습: {video_id} → {format_string} (성공 {history[video_id]['success_count']}회)")
    
    def record_format_failure(self, video_id, format_string):
        """포맷 실패 기록"""
        history = self.load_format_history()
        
        if video_id not in history:
            history[video_id] = {
                'success_format': None,
                'failed_formats': [],
                'last_updated': None,
                'success_count': 0
            }
        
        if format_string not in history[video_id]['failed_formats']:
            history[video_id]['failed_formats'].append(format_string)
        
        self.save_format_history(history)
        print(f"❌ 포맷 실패 기록: {video_id} → {format_string}")
    
    def get_optimized_formats(self, video_id, is_mobile=False):
        """학습된 최적의 포맷 순서 반환"""
        history = self.load_format_history()
        
        # 기본 포맷 순서
        if is_mobile:
            default_formats = [
                'bestaudio[ext=m4a]',
                'bestaudio[ext=mp4]',
                'bestaudio[ext=webm]',
                'bestaudio[ext=opus]',
                'bestaudio/best'
            ]
        else:
            default_formats = [
                'bestaudio[ext=m4a]',
                'bestaudio[ext=mp4]',
                'bestaudio[ext=webm]',
                'bestaudio[ext=opus]',
                'bestaudio/best'
            ]
        
        # 해당 video_id의 이력이 있으면 최적화
        if video_id in history:
            info = history[video_id]
            success_format = info.get('success_format')
            failed_formats = info.get('failed_formats', [])
            
            if success_format:
                # 성공한 포맷을 맨 앞으로
                optimized = [success_format]
                
                # 실패한 포맷 제외하고 나머지 추가
                for fmt in default_formats:
                    if fmt != success_format and fmt not in failed_formats:
                        optimized.append(fmt)
                
                print(f"🎯 최적화된 포맷 순서 적용: {video_id}")
                print(f"   └─ 우선순위 1: {success_format} (이전 성공 {info.get('success_count', 0)}회)")
                if failed_formats:
                    print(f"   └─ 스킵: {', '.join(failed_formats)}")
                
                return optimized
        
        return default_formats
    
    def login_required(self, f):
        """로그인 필요 데코레이터"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    
    def setup_routes(self):
        """Flask 라우트 설정"""
        
        # JavaScript 파일 캐시 방지
        @self.app.after_request
        def add_no_cache_headers(response):
            """JavaScript 파일 캐시 방지"""
            if request.path.endswith('.js'):
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            return response
        
        @self.app.before_request
        def track_session():
            """접속자 추적 및 IP 차단 검사"""
            # 🚫 IP 차단 검사
            client_ip = request.remote_addr
            if self.is_ip_blocked(client_ip):
                return jsonify({'success': False, 'message': '차단된 IP입니다'}), 403
            
            if session.get('logged_in'):
                from datetime import datetime
                import uuid
                
                # 세션 ID 생성 또는 가져오기
                if 'session_id' not in session:
                    session['session_id'] = str(uuid.uuid4())
                
                session_id = session['session_id']
                username = session.get('username', 'unknown')
                
                # User-Agent 파싱
                user_agent = request.headers.get('User-Agent', '')
                
                # 디바이스 정보 추출
                device_info = self.parse_user_agent(user_agent)
                
                # 접속자 정보 업데이트
                self.active_sessions[session_id] = {
                    'username': username,
                    'ip': request.remote_addr,
                    'user_agent': user_agent,
                    'device': device_info['device'],
                    'os': device_info['os'],
                    'browser': device_info['browser'],
                    'last_active': datetime.now().isoformat()
                }
                
                # 10분 이상 비활성 세션 제거
                from datetime import timedelta
                cutoff_time = datetime.now() - timedelta(minutes=10)
                inactive_sessions = [
                    sid for sid, info in self.active_sessions.items()
                    if datetime.fromisoformat(info['last_active']) < cutoff_time
                ]
                for sid in inactive_sessions:
                    del self.active_sessions[sid]
        
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                if self.verify_user(username, password):
                    import uuid
                    session['logged_in'] = True
                    session['username'] = username  # 사용자명 저장
                    session['session_id'] = str(uuid.uuid4())
                    return redirect(url_for('index'))
                else:
                    # PIN 불러오기
                    pin_code = self.get_pin_code()
                    return render_template('login.html', error='아이디 또는 비밀번호가 잘못되었습니다', pin_code=pin_code)
            
            # PIN 불러오기
            pin_code = self.get_pin_code()
            return render_template('login.html', pin_code=pin_code)
        
        @self.app.route('/register', methods=['GET', 'POST'])
        def register_page():
            if request.method == 'POST':
                # 이건 HTML form 용
                return render_template('register.html')
            return render_template('register.html')
        
        @self.app.route('/api/register', methods=['POST'])
        def register_api():
            # 🚫 IP 차단 검사
            client_ip = request.remote_addr
            if self.is_ip_blocked(client_ip):
                return jsonify({'success': False, 'message': '차단된 IP입니다. 회원가입이 불가능합니다.'}), 403
            
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if len(username) < 3:
                return jsonify({'success': False, 'message': '아이디는 3자 이상이어야 합니다'})
            
            if len(password) < 4:
                return jsonify({'success': False, 'message': '비밀번호는 4자 이상이어야 합니다'})
            
            success, message = self.register_user(username, password)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/logout')
        def logout():
            session.pop('logged_in', None)
            session.pop('username', None)
            session.pop('session_id', None)
            return redirect(url_for('login'))
        
        @self.app.route('/')
        def index():
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            
            # 강력 새로고침 파라미터 처리 (_nocache, _refresh, _force 등)
            # 캐시 방지 헤더 추가
            response = make_response(render_template('index.html'))
            
            # 브라우저 캐시 완전 비활성화
            if request.args.get('_nocache') or request.args.get('_refresh') or request.args.get('_force'):
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                self.log(f"🔥 강력 새로고침 요청 감지 - 캐시 비활성화 헤더 적용")
            
            return response
        
        @self.app.route('/api/download', methods=['POST'])
        def download_video():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            data = request.get_json()
            url = data.get('url', '').strip()
            
            if not url:
                return jsonify({'success': False, 'message': 'URL을 입력해주세요'})
            
            if 'youtube.com' in url or 'youtu.be' in url:
                result = self.download_youtube(url)
            elif 'instagram.com' in url:
                result = self.download_instagram(url)
            else:
                return jsonify({
                    'success': False,
                    'message': '지원하지 않는 URL입니다'
                })
            
            return jsonify(result)
        
        @self.app.route('/api/stream', methods=['POST'])
        def stream_audio():
            """오디오 스트리밍 - 모바일 최적화 (다운로드 후 재생)"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            # yt_dlp import를 함수 시작 부분으로 이동
            import yt_dlp
            
            try:
                data = request.get_json()
                url = data.get('url', '').strip()
                is_mobile = data.get('is_mobile', False)  # 모바일 여부
                streaming_mode = data.get('streaming_mode', False)  # 테슬라 스트리밍 모드
                
                # 디버깅: 받은 파라미터 로그 출력
                self.log(f"🔍 요청 파라미터: url={url[:50]}..., is_mobile={is_mobile}, streaming_mode={streaming_mode}")
                
                if not url:
                    return jsonify({'success': False, 'message': 'URL을 입력해주세요'})
                
                # 임시 폴더 생성
                temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
                os.makedirs(temp_dir, exist_ok=True)
                
                # 캐시 파일은 사용자가 직접 삭제할 때까지 보관
                # (플레이리스트에서 삭제 또는 "음원 파일 열기"에서 수동 삭제)
                
                # 🚗 스트리밍 모드: 캐시 건너뛰고 실시간 URL만 반환
                if streaming_mode:
                    self.log(f"🚗 테슬라 스트리밍 모드: 캐시 건너뛰고 실시간 URL 요청")
                    
                    # 빠른 포맷 선택 (스트리밍용)
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'quiet': True,
                        'no_warnings': True,
                        'nocheckcertificate': True,
                        'socket_timeout': 10,
                        'retries': 3,
                        'youtube_include_dash_manifest': False,
                        'youtube_include_hls_manifest': False,
                        'skip_unavailable_fragments': True,
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        audio_url = info.get('url')
                        title = info.get('title', '실시간 스트리밍')
                        duration = info.get('duration', 0)
                        
                        if not audio_url:
                            return jsonify({'success': False, 'message': '스트리밍 URL을 가져올 수 없습니다'})
                        
                        self.log(f"🚗 실시간 스트리밍 URL 획득: {title}")
                        
                        return jsonify({
                            'success': True,
                            'audio_url': audio_url,
                            'title': title,
                            'duration': duration,
                            'streaming_mode': True,
                            'local_file': False,
                            'instant_play': True
                        })
                
                # 🚀 일반 모드: 빠른 캐시 확인
                import re
                # 쇼츠 URL 지원: /shorts/, /v=, /youtu.be/
                video_id_match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', url)
                if video_id_match:
                    quick_video_id = video_id_match.group(1)
                    
                    # 캐시 파일이 있는지 빠르게 확인
                    for ext in ['m4a', 'webm', 'opus', 'mp3', 'mp4']:
                        cached_file = os.path.join(temp_dir, f"{quick_video_id}.{ext}")
                        if os.path.exists(cached_file):
                            self.log(f"⚡ 캐시 즉시 사용: {quick_video_id}.{ext} (YouTube 확인 생략)")
                            
                            # Duration 읽기
                            file_duration = 0
                            try:
                                try:
                                    from mutagen import File
                                    audio = File(cached_file)
                                    if audio and audio.info and hasattr(audio.info, 'length'):
                                        file_duration = int(audio.info.length)
                                except:
                                    import subprocess
                                    result = subprocess.run(
                                        ['ffprobe', '-v', 'error', '-show_entries', 
                                         'format=duration', '-of', 
                                         'default=noprint_wrappers=1:nokey=1', cached_file],
                                        capture_output=True,
                                        text=True,
                                        timeout=3
                                    )
                                    file_duration = int(float(result.stdout.strip()))
                            except:
                                file_duration = 0
                            
                            # 🎵 실제 제목 가져오기 (playlist 우선, 없으면 metadata.json, 마지막으로 YouTube API)
                            cached_title = None
                            cached_thumbnail = ''
                            cached_duration_from_meta = 0
                            
                            try:
                                # 1순위: 재생 목록에서 찾기
                                playlist = self.load_playlist()
                                self.log(f"🔍 재생 목록 검색 중... (video_id: {quick_video_id}, 항목 수: {len(playlist)})")
                                for item in playlist:
                                    item_video_id = item.get('video_id', '')
                                    item_url = item.get('url', '')
                                    if item_video_id == quick_video_id or quick_video_id in item_url:
                                        cached_title = item.get('title', '')
                                        cached_thumbnail = item.get('thumbnail', '')
                                        cached_duration_from_meta = item.get('duration', 0)
                                        self.log(f"✅ 재생 목록에서 찾음: {cached_title}")
                                        break
                                
                                # 2순위: 메타데이터에서 찾기 (재생 목록에 없으면)
                                if not cached_title:
                                    metadata = self.load_metadata()
                                    self.log(f"🔍 메타데이터 검색 중... (video_id: {quick_video_id}, 키 수: {len(metadata)})")
                                    if quick_video_id in metadata:
                                        cached_title = metadata[quick_video_id].get('title', '')
                                        cached_thumbnail = metadata[quick_video_id].get('thumbnail', '')
                                        cached_duration_from_meta = metadata[quick_video_id].get('duration', 0)
                                        self.log(f"✅ 메타데이터에서 찾음: {cached_title}")
                                
                                # 3순위: YouTube API로 직접 가져오기 (빠른 조회)
                                if not cached_title:
                                    self.log(f"🌐 YouTube API로 제목 조회 시도...")
                                    info_opts = {
                                        'quiet': True,
                                        'no_warnings': True,
                                        'extract_flat': False,
                                        'skip_download': True,
                                        'socket_timeout': 5,
                                    }
                                    with yt_dlp.YoutubeDL(info_opts) as ydl:
                                        video_info = ydl.extract_info(f'https://www.youtube.com/watch?v={quick_video_id}', download=False)
                                        cached_title = video_info.get('title', '')
                                        if not cached_thumbnail:
                                            cached_thumbnail = video_info.get('thumbnail', '')
                                        if cached_duration_from_meta == 0:
                                            cached_duration_from_meta = video_info.get('duration', 0)
                                        self.log(f"✅ YouTube API에서 가져옴: {cached_title}")
                            except Exception as e:
                                self.log(f"⚠️ 캐시 제목 가져오기 실패: {e}")
                                import traceback
                                self.log(f"상세 오류: {traceback.format_exc()}")
                            
                            # 최종 제목 설정
                            if not cached_title:
                                cached_title = 'Cached Audio'
                                self.log(f"❌ 제목을 찾을 수 없음 - 기본값 사용")
                            
                            # duration은 파일에서 읽은 값 우선, 없으면 메타데이터 값
                            if file_duration == 0 and cached_duration_from_meta > 0:
                                file_duration = cached_duration_from_meta
                            
                            file_name = os.path.basename(cached_file)
                            return jsonify({
                                'success': True,
                                'audio_url': f'/temp_audio/{file_name}',
                                'title': cached_title,
                                'duration': file_duration,
                                'thumbnail': cached_thumbnail,
                                'video_id': quick_video_id,
                                'local_file': True,
                                'from_cache': True
                            })
                
                # 캐시 없음 - 정보 가져오기 (학습 기반 최적화 포맷)
                # 🎯 학습된 최적 포맷 순서 가져오기
                format_options = self.get_optimized_formats(quick_video_id if video_id_match else 'unknown', is_mobile)
                
                if is_mobile:
                    print(f"📱 모바일 모드: 학습 기반 포맷 순서 ({len(format_options)}개)")
                else:
                    print(f"💻 데스크톱 모드: 학습 기반 포맷 순서 ({len(format_options)}개)")
                
                # 포맷별로 시도
                info = None
                stream_url = None
                video_id = 'unknown'
                actual_duration = 0
                successful_format = None
                
                for i, format_str in enumerate(format_options):
                    try:
                        info_opts = {
                            'format': format_str,
                            'quiet': True,
                            'no_warnings': True,
                            'extract_flat': False,
                            'socket_timeout': 10,  # 10초 타임아웃
                            'nocheckcertificate': True,  # SSL 인증서 체크 생략 (빠름)
                            'no_check_certificate': True,
                            'prefer_insecure': False,
                            'http_chunk_size': 10485760,  # 10MB 청크
                            'youtube_include_dash_manifest': False,  # DASH manifest 생략 (빠름!)
                            'youtube_include_hls_manifest': False,   # HLS manifest 생략 (빠름!)
                            'skip_unavailable_fragments': True,      # 없는 조각 건너뛰기
                        }
                        
                        print(f"🔄 포맷 시도 {i+1}/{len(format_options)}: {format_str}")
                        
                        with yt_dlp.YoutubeDL(info_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                            video_id = info.get('id', 'unknown')
                            stream_url = info.get('url')
                            
                            if stream_url:
                                print(f"✅ 포맷 성공: {format_str} (최적화 모드)")
                                successful_format = format_str
                                # 🎯 성공한 포맷 기록
                                self.record_format_success(video_id, format_str, is_mobile)
                                break
                            else:
                                print(f"❌ 포맷 실패: {format_str} - URL 없음")
                                # 🎯 실패한 포맷 기록
                                if video_id != 'unknown':
                                    self.record_format_failure(video_id, format_str)
                                
                    except Exception as e:
                        print(f"❌ 포맷 실패: {format_str} - {str(e)}")
                        # 🎯 실패한 포맷 기록
                        if video_id != 'unknown':
                            self.record_format_failure(video_id, format_str)
                        continue
                
                if not info or not stream_url:
                    return jsonify({
                        'success': False, 
                        'message': '🎵 이 영상은 오디오 포맷을 지원하지 않습니다. 다른 영상을 시도해보세요.',
                        'error_type': 'format_not_available'
                    })
                
                # Duration 디버깅
                raw_duration = info.get('duration', 0)
                print(f"📊 원본 Duration: {raw_duration}초 ({raw_duration/60:.1f}분)")
                
                # 실제 사용할 duration
                actual_duration = raw_duration
                
                # 이미 다운로드된 파일 확인
                downloaded_file = None
                for ext in ['m4a', 'webm', 'opus', 'mp3', 'mp4']:
                    file_path = os.path.join(temp_dir, f"{video_id}.{ext}")
                    if os.path.exists(file_path):
                        downloaded_file = file_path
                        print(f"💾 캐시된 파일 사용: {file_path}")
                        break
                    
                # 캐시된 파일이 있으면 로컬 파일로 즉시 반환
                if downloaded_file:
                    # 실제 파일에서 duration 읽기
                    try:
                        try:
                            from mutagen import File as MutagenFile
                            audio = MutagenFile(downloaded_file)
                            if audio and audio.info and hasattr(audio.info, 'length'):
                                file_duration = audio.info.length
                                actual_duration = int(file_duration)
                                print(f"📊 캐시 파일 Duration: {actual_duration}초 ({actual_duration/60:.1f}분)")
                        except:
                            pass
                    except:
                        pass
                    
                    file_name = os.path.basename(downloaded_file)
                    print(f"✅ 캐시 사용 - Duration: {actual_duration}초")
                    return jsonify({
                        'success': True,
                        'audio_url': f'/temp_audio/{file_name}',
                        'youtube_url': stream_url,  # 모바일용 YouTube URL 추가
                        'title': info.get('title', 'Unknown'),
                        'duration': actual_duration,
                        'thumbnail': info.get('thumbnail', ''),
                        'video_id': video_id,
                        'local_file': True
                    })
                
                # 🚀 모든 플랫폼: 즉시 재생 + 백그라운드 다운로드 (서버가 중계!)
                if stream_url:
                    # 백그라운드 다운로드 시작 (중복 방지)
                    if video_id not in self.downloading_files:
                        self.downloading_files.add(video_id)
                        import threading
                        def background_download():
                            try:
                                bg_download_format_options = [
                                    'bestaudio[ext=webm]',  # 🍎 Safari duration 버그 없음!
                                    'bestaudio[ext=opus]',
                                    'bestaudio[ext=m4a]',
                                    'bestaudio[ext=mp4]',
                                    'bestaudio/best'
                                ]
                                
                                self.log(f"🚀 백그라운드 다운로드 시작: {video_id}")
                                
                                download_success = False
                                for fmt in bg_download_format_options:
                                    try:
                                        download_opts = {
                                            'format': fmt,
                                            'quiet': True,
                                            'no_warnings': True,
                                            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                                            'nocheckcertificate': True,
                                            'no_check_certificate': True,
                                            'socket_timeout': 30,  # 타임아웃 줄임
                                            'retries': 5,  # 재시도 늘림
                                            'http_chunk_size': 10485760,  # 10MB 청크 (더 빠름!)
                                            'fragment_retries': 10,  # 조각 재시도 늘림
                                            'extractor_retries': 5,
                                            'concurrent_fragment_downloads': 5,  # 🚀 병렬 다운로드 5개!
                                            'buffersize': 16384,  # 버퍼 크기 증가
                                            'throttledratelimit': None,  # 속도 제한 없음
                                        }
                                        with yt_dlp.YoutubeDL(download_opts) as ydl:
                                            ydl.download([url])
                                            self.log(f"✅ 백그라운드 다운로드 완료: {video_id} (포맷: {fmt})")
                                            download_success = True
                                            break
                                    except Exception as fmt_error:
                                        self.log(f"⚠️ 포맷 {fmt} 다운로드 실패: {str(fmt_error)[:100]}...")
                                        continue
                                
                                if not download_success:
                                    self.log(f"❌ 백그라운드 다운로드 완전 실패: {video_id} (모든 포맷 실패)")
                                    
                            except Exception as e:
                                self.log(f"❌ 백그라운드 다운로드 오류: {e}")
                            finally:
                                self.downloading_files.discard(video_id)
                        
                        thread = threading.Thread(target=background_download, daemon=True)
                        thread.start()
                    else:
                        self.log(f"⏳ 이미 다운로드 중: {video_id} (중복 방지)")
                    
                    # 🎵 사용자별 메타데이터 저장
                    try:
                        metadata = self.load_metadata()
                        metadata[video_id] = {
                            'title': info.get('title', 'Unknown'),
                            'duration': actual_duration,
                            'thumbnail': info.get('thumbnail', ''),
                            'added_at': datetime.now().isoformat()
                        }
                        self.save_metadata(metadata)
                    except Exception as e:
                        self.log(f"⚠️ 메타데이터 저장 실패: {e}")
                    
                    instant_play_message = "📱 모바일 즉시 재생" if is_mobile else "💻 데스크톱 즉시 재생"
                    print(f"⚡ {instant_play_message} - Duration: {actual_duration}초 (서버 중계 + 백그라운드 다운로드)")
                    return jsonify({
                        'success': True,
                        'audio_url': stream_url,
                        'title': info.get('title', 'Unknown'),
                        'duration': actual_duration,
                        'thumbnail': info.get('thumbnail', ''),
                        'video_id': video_id,
                        'local_file': False,
                        'downloading': True,
                        'instant_play': True
                    })
                else:
                    return jsonify({'success': False, 'message': '오디오 URL을 찾을 수 없습니다'})
            
            except Exception as e:
                print(f"❌ 스트리밍 오류: {str(e)}")
                return jsonify({'success': False, 'message': f'스트리밍 실패: {str(e)}'})
        
        @self.app.route('/temp_audio/<path:filename>')
        def serve_temp_audio(filename):
            """임시 오디오 파일 서빙 - Safari/iOS 완벽 호환"""
            import os  # 명시적으로 import
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
            file_path = os.path.join(temp_dir, filename)
            
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다'}), 404
            
            file_size = os.path.getsize(file_path)
            
            # 🍎 Safari를 위한 정확한 MIME type 설정
            ext = os.path.splitext(filename)[1].lower()
            mime_types = {
                '.m4a': 'audio/mp4',      # Safari 필수!
                '.mp4': 'audio/mp4',
                '.mp3': 'audio/mpeg',
                '.webm': 'audio/webm',
                '.opus': 'audio/ogg',
                '.ogg': 'audio/ogg'
            }
            mimetype = mime_types.get(ext, 'audio/mpeg')
            
            # 첫 요청만 로그 출력 (Range 요청이 아닌 경우만)
            # Safari는 Range 요청을 미친듯이 보내서 로그가 도배됨
            
            # Range 요청 처리 (모든 플랫폼 지원 - Safari 필수!)
            range_header = request.headers.get('Range', None)
            user_agent = request.headers.get('User-Agent', '').lower()
            is_mobile_request = 'mobile' in user_agent or 'iphone' in user_agent or 'android' in user_agent or 'ipad' in user_agent
            
            if range_header:
                # Range 요청: bytes=start-end
                import re
                match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if match:
                    start = int(match.group(1))
                    end = int(match.group(2)) if match.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    
                    # 첫 Range 요청만 로그 출력
                    if start == 0:
                        self.log(f"🎵 Range 스트리밍 시작: {filename} (크기: {file_size/1024/1024:.1f}MB)")
                    
                    def generate():
                        with open(file_path, 'rb') as f:
                            f.seek(start)
                            remaining = length
                            chunk_size = 256 * 1024  # 256KB 청크
                            while remaining > 0:
                                chunk = f.read(min(chunk_size, remaining))
                                if not chunk:
                                    break
                                remaining -= len(chunk)
                                yield chunk
                    
                    response = Response(
                        generate(),
                        206,  # Partial Content
                        mimetype=mimetype,  # 🍎 정확한 MIME type!
                        direct_passthrough=True
                    )
                    response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    response.headers['Content-Length'] = str(length)
                    response.headers['Accept-Ranges'] = 'bytes'
                    response.headers['Cache-Control'] = 'no-cache'  # Safari: no-cache 권장
                    # 🍎 Safari/iOS 추가 헤더
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range'
                    
                    # Range 서빙 완료 로그도 제거 (너무 많음)
                    # self.log(f"✅ Range 서빙 완료: {filename}")
                    return response
            
            # 전체 파일 서빙 (Range 요청 없음)
            self.log(f"🎵 전체 파일 서빙: {filename}")
            
            def generate_full():
                with open(file_path, 'rb') as f:
                    # 🍎 Safari 즉시 재생을 위해 작은 청크 사용
                    chunk_size = 64 * 1024  # 64KB 청크 (Safari 최적화)
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
            
            response = Response(
                generate_full(),
                200,
                mimetype=mimetype,  # 🍎 정확한 MIME type!
                direct_passthrough=True
            )
            response.headers['Content-Length'] = str(file_size)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'  # Safari: no-cache 권장
            # 🍎 Safari/iOS 추가 헤더
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Accept-Ranges'
            
            self.log(f"✅ 파일 서빙 완료: {filename}")
            return response
        
        @self.app.route('/api/check-download/<video_id>')
        def check_download(video_id):
            """다운로드 완료 여부 확인"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
            
            # 다운로드된 파일 확인
            for ext in ['m4a', 'webm', 'opus', 'mp3', 'mp4']:
                file_path = os.path.join(temp_dir, f"{video_id}.{ext}")
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    return jsonify({
                        'success': True,
                        'ready': True,
                        'audio_url': f'/temp_audio/{file_name}'
                    })
            
            return jsonify({
                'success': True,
                'ready': False
            })
        
        @self.app.route('/api/video-stream', methods=['POST'])
        def get_video_stream():
            """비디오 스트리밍 (학습 기반 포맷 최적화)"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                data = request.get_json()
                url = data.get('url', '').strip()
                
                if not url:
                    return jsonify({'success': False, 'message': 'URL을 입력해주세요'})
                
                # video_id 추출
                import re
                video_id_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
                video_id = video_id_match.group(1) if video_id_match else 'unknown'
                
                # 🎯 학습된 최적 비디오 포맷 순서 가져오기 (비디오는 모바일/데스크톱 구분 없음)
                default_video_formats = [
                    'best[height<=720][ext=mp4]',
                    'best[height<=1080][ext=mp4]',
                    'best[height<=720]',
                    'best[ext=mp4]',
                    'best'
                ]
                
                # 비디오용 이력 키는 'video_' 접두사 추가
                video_history_id = f"video_{video_id}"
                history = self.load_format_history()
                
                if video_history_id in history:
                    info = history[video_history_id]
                    success_format = info.get('success_format')
                    failed_formats = info.get('failed_formats', [])
                    
                    if success_format:
                        format_options = [success_format]
                        for fmt in default_video_formats:
                            if fmt != success_format and fmt not in failed_formats:
                                format_options.append(fmt)
                        
                        print(f"🎯 비디오 최적화 포맷 적용: {video_id}")
                        print(f"   └─ 우선순위 1: {success_format}")
                    else:
                        format_options = default_video_formats
                else:
                    format_options = default_video_formats
                
                print(f"🎬 비디오 포맷 학습 기반 최적화 ({len(format_options)}개)")
                
                # 포맷별로 시도
                info = None
                video_url = None
                successful_format = None
                
                for i, format_str in enumerate(format_options):
                    try:
                        ydl_opts = {
                            'format': format_str,
                            'quiet': True,
                            'no_warnings': True,
                            'socket_timeout': 10,  # 10초 타임아웃
                            'nocheckcertificate': True,  # SSL 인증서 체크 생략 (빠름)
                            'no_check_certificate': True,
                            'http_chunk_size': 10485760,  # 10MB 청크
                            'youtube_include_dash_manifest': False,  # DASH manifest 생략 (빠름!)
                            'youtube_include_hls_manifest': False,   # HLS manifest 생략 (빠름!)
                            'skip_unavailable_fragments': True,      # 없는 조각 건너뛰기
                        }
                        
                        print(f"🔄 비디오 포맷 시도 {i+1}/{len(format_options)}: {format_str}")
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                            video_url = info.get('url')
                            
                            if video_url:
                                print(f"✅ 비디오 포맷 성공: {format_str}")
                                successful_format = format_str
                                # 🎯 성공한 비디오 포맷 기록
                                self.record_format_success(video_history_id, format_str, is_mobile=False)
                                break
                            else:
                                print(f"❌ 비디오 포맷 실패: {format_str} - URL 없음")
                                # 🎯 실패한 비디오 포맷 기록
                                self.record_format_failure(video_history_id, format_str)
                                
                    except Exception as e:
                        print(f"❌ 비디오 포맷 실패: {format_str} - {str(e)}")
                        # 🎯 실패한 비디오 포맷 기록
                        self.record_format_failure(video_history_id, format_str)
                        continue
                
                if not info or not video_url:
                    return jsonify({
                        'success': False, 
                        'message': '🎬 이 영상은 비디오 포맷을 지원하지 않습니다. 다른 영상을 시도해보세요.',
                        'error_type': 'format_not_available'
                    })
                
                return jsonify({
                    'success': True,
                    'video_url': video_url,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', '')
                })
            
            except Exception as e:
                return jsonify({'success': False, 'message': f'비디오 로드 실패: {str(e)}'})
        
        @self.app.route('/api/search', methods=['POST'])
        def search_youtube():
            """유튜브 검색"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                data = request.get_json()
                query = data.get('query', '').strip()
                max_results = min(data.get('max_results', 20), 50)
                
                if not query:
                    return jsonify({'success': False, 'message': '검색어를 입력해주세요'})
                
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_results = ydl.extract_info(f'ytsearch{max_results}:{query}', download=False)
                    
                    if not search_results or 'entries' not in search_results:
                        return jsonify({'success': False, 'message': '검색 결과 없음'})
                    
                    results = []
                    for entry in search_results['entries']:
                        if entry:
                            video_id = entry.get('id', '')
                            thumbnail = entry.get('thumbnail', '')
                            if not thumbnail and video_id:
                                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                            
                            results.append({
                                'id': video_id,
                                'title': entry.get('title', 'Unknown'),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'thumbnail': thumbnail,
                                'duration': entry.get('duration', 0),
                                'channel': entry.get('uploader', 'Unknown'),
                                'view_count': entry.get('view_count', 0)
                            })
                    
                    return jsonify({
                        'success': True,
                        'results': results,
                        'count': len(results)
                    })
            
            except Exception as e:
                return jsonify({'success': False, 'message': f'검색 실패: {str(e)}'})
        
        @self.app.route('/api/videos', methods=['GET'])
        def get_videos():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                username = session.get('username', 'admin')
                metadata = self.load_metadata(username)
                
                # metadata가 리스트인지 확인
                if not isinstance(metadata, list):
                    metadata = []
                
                # 각 영상에 video_id 추가 (URL에서 추출)
                import re
                for video in metadata:
                    if isinstance(video, dict):
                        if 'video_id' not in video and 'url' in video:
                            url = video.get('url', '')
                            # YouTube video_id 추출
                            patterns = [
                                r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
                                r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
                                r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
                            ]
                            for pattern in patterns:
                                match = re.search(pattern, url)
                                if match:
                                    video['video_id'] = match.group(1)
                                    break
                            
                            # video_id가 없으면 파일명에서 추출 시도
                            if 'video_id' not in video:
                                filename = video.get('filename', '')
                                match = re.search(r'[a-zA-Z0-9_-]{11}', filename)
                                if match:
                                    video['video_id'] = match.group(0)
                
                return jsonify({'success': True, 'videos': metadata})
            except Exception as e:
                self.log(f"❌ 영상 목록 로드 실패: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f'영상 목록 로드 실패: {str(e)}', 'videos': []})
        
        @self.app.route('/api/video/<path:filename>')
        def serve_video(filename):
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            
            import urllib.parse
            filename = urllib.parse.unquote(filename)
            
            self.log(f"📹 영상 요청: {filename}")
            
            # 정확한 파일명으로 찾기 (공용 videos 폴더)
            filepath = os.path.join(self.VIDEOS_DIR, filename)
            self.log(f"🔍 파일 경로 확인: {filepath}")
            
            if os.path.exists(filepath):
                self.log(f"✅ 파일 발견! 전송 시작: {filename}")
                return send_from_directory(self.VIDEOS_DIR, filename)
            
            # 파일명이 잘린 경우 유연하게 찾기
            import glob
            # 파일명의 앞부분으로 검색
            base_name = os.path.splitext(filename)[0]
            pattern = os.path.join(self.VIDEOS_DIR, f"{base_name}*.mp4")
            matching_files = glob.glob(pattern)
            
            self.log(f"🔍 패턴 검색: {pattern}")
            self.log(f"🔍 매칭 결과: {len(matching_files)}개 파일")
            
            if matching_files:
                # 가장 유사한 파일명 찾기
                actual_filename = os.path.basename(matching_files[0])
                self.log(f"✅ 파일명 매칭: '{filename}' → '{actual_filename}'")
                return send_from_directory(self.VIDEOS_DIR, actual_filename)
            
            # 파일을 찾을 수 없음
            self.log(f"❌ 파일을 찾을 수 없음: {filename}")
            self.log(f"📂 VIDEOS_DIR 내용: {os.listdir(self.VIDEOS_DIR) if os.path.exists(self.VIDEOS_DIR) else '폴더 없음'}")
            return jsonify({'error': 'File not found', 'filename': filename}), 404
        
        @self.app.route('/api/delete/<path:filename>', methods=['DELETE'])
        def delete_video(filename):
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                import urllib.parse
                filename = urllib.parse.unquote(filename)
                filepath = os.path.join(self.VIDEOS_DIR, filename)
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                metadata = self.load_metadata()
                metadata = [m for m in metadata if m.get('filename') != filename]
                self.save_metadata(metadata)
                
                return jsonify({'success': True, 'message': '삭제 완료'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'삭제 실패: {str(e)}'})
        
        @self.app.route('/api/delete-shared', methods=['DELETE'])
        def delete_shared_video():
            """공유받은 영상 삭제 (메타데이터 및 재생 목록에서만)"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                data = request.get_json()
                video_id = data.get('video_id', '')
                
                if not video_id:
                    return jsonify({'success': False, 'message': 'video_id가 필요합니다'})
                
                username = session.get('username', '')
                
                self.log(f"📤 공유받은 영상 삭제 요청: {username} - video_id={video_id}")
                
                # 메타데이터(갤러리)에서 삭제 (파일은 보존)
                metadata = self.load_metadata(username)
                if isinstance(metadata, list):
                    original_count = len(metadata)
                    metadata = [m for m in metadata if m.get('video_id') != video_id]
                    removed_from_gallery = len(metadata) < original_count
                    self.save_metadata(metadata, username)
                    if removed_from_gallery:
                        self.log(f"✅ 갤러리에서 메타데이터 제거: {username} - video_id={video_id}")
                
                # 재생 목록에서도 삭제 (파일은 보존)
                playlist = self.load_playlist(username)
                original_count = len(playlist)
                playlist = [p for p in playlist if p.get('video_id') != video_id]
                removed_from_playlist = len(playlist) < original_count
                self.save_playlist(playlist, username)
                if removed_from_playlist:
                    self.log(f"✅ 재생 목록에서 메타데이터 제거: {username} - video_id={video_id}")
                
                self.log(f"✅ 공유받은 영상 삭제 완료 (원본 파일 보호됨): {username}")
                
                return jsonify({
                    'success': True,
                    'message': '내 목록에서 제거했습니다 (원본 파일 보호)'
                })
            except Exception as e:
                self.log(f"❌ 공유받은 영상 삭제 실패: {str(e)}")
                return jsonify({'success': False, 'message': f'삭제 실패: {str(e)}'})
        
        @self.app.route('/api/playlist', methods=['GET'])
        def get_playlist():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                username = session.get('username', 'admin')
                playlist = self.load_playlist(username)
                favorites = self.load_favorites(username)
                
                # playlist가 리스트인지 확인
                if not isinstance(playlist, list):
                    playlist = []
                
                # 즐겨찾기 상태 추가 (최적화)
                needs_save = False  # video_id 추가로 변경되었는지 추적
                
                if len(favorites) > 0:
                    favorite_video_ids = {fav.get('video_id') for fav in favorites if fav.get('video_id')}
                    
                    import re
                    favorite_count = 0
                    
                    # video_id 추출 및 즐겨찾기 매칭
                    for item in playlist:
                        if isinstance(item, dict):
                            # video_id가 이미 있으면 추출 스킵 (성능 향상)
                            video_id = item.get('video_id')
                            if not video_id and item.get('url'):
                                url = item.get('url', '')
                                # 간단한 정규식으로 최적화
                                match = re.search(r'(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
                                if match:
                                    video_id = match.group(1)
                                    item['video_id'] = video_id
                                    needs_save = True  # playlist.json 업데이트 필요
                            
                            # 즐겨찾기 여부 확인
                            is_fav = video_id and video_id in favorite_video_ids
                            item['is_favorite'] = is_fav
                            if is_fav:
                                favorite_count += 1
                    
                    # 즐겨찾기 우선 정렬 (즐겨찾기가 있을 때만)
                    if favorite_count > 0:
                        playlist.sort(key=lambda x: (not x.get('is_favorite', False), x.get('title', '')))
                        self.log(f"⭐ 즐겨찾기 {favorite_count}개")
                else:
                    # 즐겨찾기가 없으면 즐겨찾기 매칭만 스킵 (video_id는 추출)
                    import re
                    for item in playlist:
                        if isinstance(item, dict):
                            item['is_favorite'] = False
                            # video_id가 없으면 추출 후 저장
                            if not item.get('video_id') and item.get('url'):
                                url = item.get('url', '')
                                match = re.search(r'(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
                                if match:
                                    item['video_id'] = match.group(1)
                                    needs_save = True
                
                # video_id가 새로 추가된 항목이 있으면 저장 (다음부터는 빠름)
                if needs_save:
                    self.save_playlist(playlist, username)
                    self.log(f"💾 video_id 자동 저장 완료 (다음부터 빠른 로딩)")
                
                return jsonify({'success': True, 'playlist': playlist})
            except Exception as e:
                self.log(f"❌ 재생 목록 로드 실패: {str(e)}")
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'message': f'재생 목록 로드 실패: {str(e)}', 'playlist': []})
        
        @self.app.route('/api/toggle-favorite', methods=['POST'])
        def toggle_favorite():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            data = request.get_json()
            video_id = data.get('video_id')
            title = data.get('title')
            url = data.get('url')
            
            if not video_id:
                return jsonify({'success': False, 'message': 'video_id 필요'})
            
            username = session.get('username', 'admin')
            favorites = self.load_favorites(username)
            
            # 이미 즐겨찾기에 있는지 확인
            existing_favorite = None
            for fav in favorites:
                if fav.get('video_id') == video_id:
                    existing_favorite = fav
                    break
            
            if existing_favorite:
                # 즐겨찾기에서 제거
                favorites = [fav for fav in favorites if fav.get('video_id') != video_id]
                self.save_favorites(favorites, username)
                self.log(f"⭐ 즐겨찾기 제거: {title}")
                return jsonify({
                    'success': True,
                    'message': '즐겨찾기에서 제거했습니다',
                    'is_favorite': False,
                    'favorites_count': len(favorites)
                })
            else:
                # 즐겨찾기에 추가
                favorite_item = {
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'added_at': datetime.now().isoformat()
                }
                favorites.insert(0, favorite_item)  # 상단에 추가
                self.save_favorites(favorites, username)
                self.log(f"⭐ 즐겨찾기 추가: {title}")
                return jsonify({
                    'success': True,
                    'message': '즐겨찾기에 추가했습니다',
                    'is_favorite': True,
                    'favorites_count': len(favorites)
                })
        
        @self.app.route('/api/favorites', methods=['GET'])
        def get_favorites():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            username = session.get('username', 'admin')
            favorites = self.load_favorites(username)
            
            return jsonify({
                'success': True,
                'favorites': favorites,
                'count': len(favorites)
            })
        
        @self.app.route('/api/playlist', methods=['POST'])
        def add_to_playlist():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            data = request.get_json()
            url = data.get('url')
            title = data.get('title')
            thumbnail = data.get('thumbnail', '')
            duration = data.get('duration', 0)
            
            if not url or not title:
                return jsonify({'success': False, 'message': '필수 정보 누락'})
            
            playlist = self.load_playlist()
            
            if any(item['url'] == url for item in playlist):
                return jsonify({'success': False, 'message': '이미 목록에 있습니다'})
            
            # video_id 추출 (저장해두면 나중에 재추출 안 해도 됨 - 성능 향상)
            import re
            video_id = None
            match = re.search(r'(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
            if match:
                video_id = match.group(1)
            
            playlist.insert(0, {
                'url': url,
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'video_id': video_id,  # video_id 미리 저장 (성능 최적화)
                'added_at': datetime.now().isoformat()
            })
            
            self.save_playlist(playlist)
            return jsonify({'success': True, 'message': '재생 목록에 추가됨'})
        
        @self.app.route('/api/playlist/<int:index>', methods=['DELETE'])
        def delete_from_playlist(index):
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                # URL에서 video_id 추출 함수
                def extract_video_id(url):
                    import re
                    patterns = [
                        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
                        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, url)
                        if match:
                            return match.group(1)
                    return None
                
                playlist = self.load_playlist()
                cache_deleted = False
                cache_size_mb = 0
                
                if 0 <= index < len(playlist):
                    deleted_item = playlist.pop(index)
                    
                    # 🔒 공유받은 항목인지 확인
                    is_shared = deleted_item.get('shared_from') is not None
                    
                    if is_shared:
                        # 공유받은 음원: 목록에서만 삭제, 캐시 파일은 유지
                        self.log(f"📤 공유받은 음원 삭제 (캐시 유지): {deleted_item.get('title', '')}")
                        self.save_playlist(playlist)
                        
                        return jsonify({
                            'success': True, 
                            'message': '공유받은 음원을 목록에서 제거했습니다 (캐시 파일은 유지됨)',
                            'cache_deleted': False,
                            'cache_size': 0
                        })
                    else:
                        # 본인이 추가한 음원: 캐시 파일도 함께 삭제
                        # URL에서 video_id 추출
                        data = request.get_json() or {}
                        url = data.get('url', '') or deleted_item.get('url', '')
                        
                        if url:
                            video_id = extract_video_id(url)
                            if video_id:
                                # temp_audio 폴더에서 해당 파일 찾아서 삭제
                                temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
                                for ext in ['m4a', 'webm', 'opus', 'mp3', 'mp4']:
                                    file_path = os.path.join(temp_dir, f"{video_id}.{ext}")
                                    if os.path.exists(file_path):
                                        try:
                                            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                                            os.remove(file_path)
                                            cache_deleted = True
                                            cache_size_mb = round(file_size, 1)
                                            self.log(f"🗑️ 캐시 파일 삭제: {file_path} ({cache_size_mb}MB)")
                                        except Exception as e:
                                            self.log(f"⚠️ 캐시 파일 삭제 실패: {e}")
                        
                        self.save_playlist(playlist)
                        
                        return jsonify({
                            'success': True, 
                            'message': '삭제 완료',
                            'cache_deleted': cache_deleted,
                            'cache_size': cache_size_mb
                        })
                else:
                    return jsonify({'success': False, 'message': '잘못된 인덱스'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'삭제 실패: {str(e)}'})
        
        @self.app.route('/api/playlist/clear', methods=['DELETE'])
        def clear_playlist():
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                # URL에서 video_id 추출 함수
                def extract_video_id(url):
                    import re
                    patterns = [
                        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
                        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, url)
                        if match:
                            return match.group(1)
                    return None
                
                # 플레이리스트 항목의 캐시 파일 삭제 (공유받은 항목 제외)
                playlist = self.load_playlist()
                cache_deleted_count = 0
                total_cache_size_mb = 0
                shared_items_count = 0
                
                temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
                
                for item in playlist:
                    # 🔒 공유받은 항목은 캐시 삭제 안 함
                    is_shared = item.get('shared_from') is not None
                    if is_shared:
                        shared_items_count += 1
                        self.log(f"📤 공유받은 음원 캐시 유지: {item.get('title', '')}")
                        continue
                    
                    # 본인이 추가한 항목만 캐시 삭제
                    url = item.get('url', '')
                    if url:
                        video_id = extract_video_id(url)
                        if video_id:
                            for ext in ['m4a', 'webm', 'opus', 'mp3', 'mp4']:
                                file_path = os.path.join(temp_dir, f"{video_id}.{ext}")
                                if os.path.exists(file_path):
                                    try:
                                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                                        os.remove(file_path)
                                        cache_deleted_count += 1
                                        total_cache_size_mb += file_size
                                        self.log(f"🗑️ 캐시 파일 삭제: {file_path} ({file_size:.1f}MB)")
                                    except Exception as e:
                                        self.log(f"⚠️ 캐시 파일 삭제 실패: {e}")
                
                self.save_playlist([])
                
                message = '재생 목록 비움'
                if shared_items_count > 0:
                    message += f' (공유받은 {shared_items_count}개 음원의 캐시는 유지됨)'
                
                return jsonify({
                    'success': True, 
                    'message': message,
                    'cache_deleted_count': cache_deleted_count,
                    'total_cache_size': round(total_cache_size_mb, 1)
                })
            except Exception as e:
                return jsonify({'success': False, 'message': f'실패: {str(e)}'})
        
        @self.app.route('/api/active-users')
        def get_active_users():
            """현재 접속자 통계"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            # 접속자 수와 상세 정보
            users = []
            for session_id, info in self.active_sessions.items():
                from datetime import datetime
                last_active = datetime.fromisoformat(info['last_active'])
                
                users.append({
                    'session_id': session_id[:8] + '...',  # 짧게 표시
                    'ip': info['ip'],
                    'device': info['device'],
                    'os': info['os'],
                    'browser': info['browser'],
                    'last_active': last_active.strftime('%H:%M:%S')
                })
            
            return jsonify({
                'success': True,
                'total_users': len(users),
                'users': users
            })
        
        @self.app.route('/api/users')
        def get_users_list():
            """사용자 목록 가져오기 (음원 공유용)"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                current_username = session.get('username', '')
                all_users = self.get_all_users()
                
                # username만 추출하고 현재 사용자 제외
                users_list = [user['username'] for user in all_users if user['username'] != current_username]
                
                return jsonify({
                    'success': True,
                    'users': users_list
                })
            except Exception as e:
                return jsonify({'success': False, 'message': f'사용자 목록 조회 실패: {str(e)}'})
        
        @self.app.route('/api/share', methods=['POST'])
        def share_content():
            """음원/영상 공유"""
            if not session.get('logged_in'):
                return jsonify({'success': False, 'message': '로그인 필요'})
            
            try:
                data = request.get_json()
                video_id = data.get('video_id', '')
                title = data.get('title', '')
                thumbnail = data.get('thumbnail', '')
                duration = data.get('duration', 0)
                to_usernames = data.get('to_usernames', [])
                content_type = data.get('content_type', 'audio')  # 'audio' 또는 'video'
                filename = data.get('filename', '')  # 실제 파일명 (영상 공유 시)
                
                self.log(f"📤 공유 요청: type={content_type}, video_id={video_id}, title={title}, filename={filename}, users={to_usernames}")
                
                if not video_id:
                    self.log(f"❌ video_id 누락")
                    return jsonify({'success': False, 'message': '공유할 컨텐츠의 video_id가 없습니다'})
                
                if not title:
                    self.log(f"❌ title 누락")
                    return jsonify({'success': False, 'message': '공유할 컨텐츠의 제목이 없습니다'})
                
                if not to_usernames:
                    self.log(f"❌ to_usernames 누락")
                    return jsonify({'success': False, 'message': '공유받을 사용자를 선택해주세요'})
                
                from_username = session.get('username', '')
                self.log(f"👤 공유자: {from_username}")
                
                success, message = self.share_content_to_users(
                    from_username=from_username,
                    to_usernames=to_usernames,
                    video_id=video_id,
                    title=title,
                    thumbnail=thumbnail,
                    duration=duration,
                    content_type=content_type,
                    filename=filename  # 실제 파일명 전달
                )
                
                if success:
                    self.log(f"✅ 공유 성공: {message}")
                else:
                    self.log(f"❌ 공유 실패: {message}")
                
                return jsonify({'success': success, 'message': message})
                
            except Exception as e:
                self.log(f"❌ 공유 오류: {str(e)}")
                import traceback
                self.log(f"상세: {traceback.format_exc()}")
                return jsonify({'success': False, 'message': f'공유 실패: {str(e)}'})
    
    def load_metadata(self, username=None):
        """메타데이터 로드 (사용자별)"""
        if username is None:
            username = session.get('username', 'admin')
        
        metadata_file = self.get_user_metadata_file(username)
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_metadata(self, metadata, username=None):
        """메타데이터 저장 (사용자별)"""
        if username is None:
            username = session.get('username', 'admin')
        
        metadata_file = self.get_user_metadata_file(username)
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def load_playlist(self, username=None):
        """재생 목록 로드 (사용자별)"""
        if username is None:
            username = session.get('username', 'admin')
        
        playlist_file = self.get_user_playlist_file(username)
        if os.path.exists(playlist_file):
            try:
                with open(playlist_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_playlist(self, playlist, username=None):
        """재생 목록 저장 (사용자별)"""
        if username is None:
            username = session.get('username', 'admin')
        
        playlist_file = self.get_user_playlist_file(username)
        with open(playlist_file, 'w', encoding='utf-8') as f:
            json.dump(playlist, f, ensure_ascii=False, indent=2)
    
    def load_favorites(self, username=None):
        """사용자별 즐겨찾기 목록 로드"""
        if username is None:
            username = session.get('username', 'admin')
        
        favorites_file = self.get_user_favorites_file(username)
        if os.path.exists(favorites_file):
            try:
                with open(favorites_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_favorites(self, favorites, username=None):
        """사용자별 즐겨찾기 목록 저장"""
        if username is None:
            username = session.get('username', 'admin')
        
        favorites_file = self.get_user_favorites_file(username)
        with open(favorites_file, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
    
    def sanitize_filename(self, filename):
        """파일명 정리"""
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename[:200]
    
    def download_youtube(self, url):
        """유튜브 영상 다운로드"""
        try:
            # 다운로드 전 파일 목록 확인
            before_files = set(os.listdir(self.VIDEOS_DIR)) if os.path.exists(self.VIDEOS_DIR) else set()
            
            ydl_opts = {
                'format': 'best[ext=mp4][height<=720][vcodec^=avc1]/best[ext=mp4][height<=720]/best[ext=mp4]/best',
                'outtmpl': os.path.join(self.VIDEOS_DIR, '%(title)s.%(ext)s'),
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                title = info.get('title', 'Unknown')
                
                # 다운로드 후 파일 목록 확인하여 실제 파일명 찾기
                after_files = set(os.listdir(self.VIDEOS_DIR))
                new_files = after_files - before_files
                
                # 실제 다운로드된 파일명 찾기
                actual_filename = None
                for f in new_files:
                    if f.endswith(('.mp4', '.webm', '.mkv')):
                        actual_filename = f
                        break
                
                # 파일명을 찾지 못하면 기존 방식 사용
                if not actual_filename:
                    actual_filename = f"{self.sanitize_filename(title)}.{info.get('ext', 'mp4')}"
                
                metadata = self.load_metadata()
                metadata.insert(0, {
                    'filename': actual_filename,
                    'title': title,
                    'url': url,
                    'platform': 'youtube',
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'downloaded_at': datetime.now().isoformat()
                })
                self.save_metadata(metadata)
                
                return {
                    'success': True,
                    'filename': actual_filename,
                    'title': title,
                    'message': '유튜브 다운로드 완료!'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'다운로드 실패: {str(e)}'
            }
    
    def download_instagram(self, url):
        """인스타그램 영상 다운로드"""
        try:
            L = instaloader.Instaloader(
                dirname_pattern=self.VIDEOS_DIR,
                filename_pattern='{date_utc}_UTC',
                download_pictures=False,
                download_videos=True,
                download_video_thumbnails=False,
            )
            
            shortcode_match = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not shortcode_match:
                return {'success': False, 'message': '잘못된 인스타그램 URL'}
            
            shortcode = shortcode_match.group(2)
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            
            if post.is_video:
                before_files = set(os.listdir(self.VIDEOS_DIR))
                L.download_post(post, target=self.VIDEOS_DIR)
                after_files = set(os.listdir(self.VIDEOS_DIR))
                new_files = after_files - before_files
                
                video_file = None
                for f in new_files:
                    if f.endswith(('.mp4', '.mov')):
                        video_file = f
                        break
                
                if video_file:
                    metadata = self.load_metadata()
                    metadata.insert(0, {
                        'filename': video_file,
                        'title': post.caption[:100] if post.caption else 'Instagram Video',
                        'url': url,
                        'platform': 'instagram',
                        'thumbnail': post.url,
                        'duration': 0,
                        'downloaded_at': datetime.now().isoformat()
                    })
                    self.save_metadata(metadata)
                    
                    return {
                        'success': True,
                        'filename': video_file,
                        'title': 'Instagram Video',
                        'message': '인스타그램 다운로드 완료!'
                    }
            
            return {'success': False, 'message': '영상이 없습니다'}
        except Exception as e:
            return {'success': False, 'message': f'실패: {str(e)}'}
    
    def start(self, host='0.0.0.0'):
        """서버 시작"""
        if self.is_running:
            return False
        
        try:
            from werkzeug.serving import make_server
            import logging
            
            self.is_running = True
            
            # 로거 비활성화
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            self.server_instance = make_server(host, self.port, self.app, threaded=True)
            self.server_instance.serve_forever()
            
            return True
        except Exception as e:
            self.is_running = False
            raise e
    
    def stop(self):
        """서버 중지"""
        self.is_running = False
        
        # 🔋 macOS 잠금 방지 해제
        self.allow_sleep()
        
        if hasattr(self, 'server_instance') and self.server_instance:
            self.server_instance.shutdown()


# ============================================================================
# 서버 워커 스레드
# ============================================================================

class ServerWorker(QThread):
    """서버 실행 스레드"""
    
    log_signal = pyqtSignal(str)
    started_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    stopped_signal = pyqtSignal()
    
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.server = None
        self.should_stop = False
    
    def run(self):
        """서버 실행"""
        try:
            self.should_stop = False
            
            # GUI 로그 콜백 함수 전달
            def gui_log_callback(message):
                self.log_signal.emit(message)
            
            self.server = VideoDownloaderServer(self.port, gui_log_callback=gui_log_callback)
            
            self.log_signal.emit(f"✅ 서버 시작: {self.port}번 포트")
            self.log_signal.emit(f"🌐 http://localhost:{self.port}")
            self.log_signal.emit(f"📱 http://{self.get_ip()}:{self.port}")
            self.started_signal.emit()
            
            self.server.start(host='0.0.0.0')
            self.stopped_signal.emit()
        except Exception as e:
            if not self.should_stop:
                self.error_signal.emit(f"서버 시작 실패: {str(e)}")
    
    def get_ip(self):
        """로컬 IP 주소"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def stop(self):
        """서버 중지"""
        self.should_stop = True
        if self.server:
            try:
                self.server.stop()
            except:
                pass


# ============================================================================
# 컨텐츠 공유 다이얼로그
# ============================================================================

class ContentShareDialog(QDialog):
    """컨텐츠 공유 다이얼로그"""
    
    def __init__(self, server, from_username, parent=None):
        super().__init__(parent)
        self.server = server
        self.from_username = from_username
        self.selected_content = None
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('📤 컨텐츠 공유')
        self.setGeometry(150, 150, 900, 600)
        
        layout = QVBoxLayout()
        
        # 헤더
        header = QLabel('📤 음원/영상 공유하기')
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #667eea;
            padding: 10px;
        """)
        layout.addWidget(header)
        
        # 컨텐츠 선택 섹션
        content_group = QGroupBox('1️⃣ 공유할 컨텐츠 선택')
        content_layout = QVBoxLayout()
        
        # 검색 바
        search_layout = QHBoxLayout()
        search_label = QLabel('🔍 검색:')
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('제목으로 검색...')
        self.search_input.textChanged.connect(self.filter_content)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #667eea;
            }
        """)
        search_layout.addWidget(self.search_input)
        content_layout.addLayout(search_layout)
        
        # 컨텐츠 목록
        self.content_list = QListWidget()
        self.content_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #667eea;
                color: white;
            }
        """)
        content_layout.addWidget(self.content_list)
        content_group.setLayout(content_layout)
        layout.addWidget(content_group)
        
        # 사용자 선택 섹션
        user_group = QGroupBox('2️⃣ 공유받을 사용자 선택')
        user_layout = QVBoxLayout()
        
        # 전체 선택 버튼
        select_all_layout = QHBoxLayout()
        self.select_all_btn = QPushButton('✅ 전체 선택')
        self.select_all_btn.clicked.connect(self.select_all_users)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        select_all_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton('❌ 전체 해제')
        self.deselect_all_btn.clicked.connect(self.deselect_all_users)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #c82333; }
        """)
        select_all_layout.addWidget(self.deselect_all_btn)
        select_all_layout.addStretch()
        user_layout.addLayout(select_all_layout)
        
        # 사용자 체크박스 목록
        self.user_checkboxes = []
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        users = self.server.get_all_users()
        for user in users:
            if user['username'] != self.from_username:  # 자신 제외
                checkbox = QCheckBox(f"{user['username']} {'🟢' if user['is_online'] else '⚪'}")
                checkbox.setStyleSheet("font-size: 13px; padding: 5px;")
                checkbox.user_data = user
                self.user_checkboxes.append(checkbox)
                scroll_layout.addWidget(checkbox)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)
        user_layout.addWidget(scroll_area)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.share_btn = QPushButton('📤 공유하기')
        self.share_btn.setStyleSheet("""
            QPushButton {
                background: #667eea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5568d3; }
        """)
        self.share_btn.clicked.connect(self.share_content)
        button_layout.addWidget(self.share_btn)
        
        close_btn = QPushButton('닫기')
        close_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 15px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 컨텐츠 로드
        self.load_content()
    
    def load_content(self):
        """컨텐츠 로드"""
        self.all_content = []
        metadata = self.server.load_metadata(self.from_username)
        
        for video_id, info in metadata.items():
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail', '')
            
            self.all_content.append({
                'video_id': video_id,
                'title': title,
                'duration': duration,
                'thumbnail': thumbnail
            })
        
        self.filter_content()
    
    def filter_content(self):
        """컨텐츠 필터링"""
        self.content_list.clear()
        search_text = self.search_input.text().lower()
        
        for content in self.all_content:
            if search_text in content['title'].lower():
                duration_min = content['duration'] // 60
                duration_sec = content['duration'] % 60
                item_text = f"🎵 {content['title']} ({duration_min}:{duration_sec:02d})"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, content)
                self.content_list.addItem(item)
    
    def select_all_users(self):
        """전체 사용자 선택"""
        for checkbox in self.user_checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all_users(self):
        """전체 사용자 해제"""
        for checkbox in self.user_checkboxes:
            checkbox.setChecked(False)
    
    def share_content(self):
        """컨텐츠 공유"""
        # 선택된 컨텐츠 확인
        selected_items = self.content_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '오류', '공유할 컨텐츠를 선택해주세요')
            return
        
        content = selected_items[0].data(Qt.UserRole)
        
        # 선택된 사용자 확인
        selected_users = []
        for checkbox in self.user_checkboxes:
            if checkbox.isChecked():
                selected_users.append(checkbox.user_data['username'])
        
        if not selected_users:
            QMessageBox.warning(self, '오류', '공유받을 사용자를 선택해주세요')
            return
        
        # 공유 실행 (GUI는 기본적으로 음원 공유)
        success, message = self.server.share_content_to_users(
            self.from_username,
            selected_users,
            content['video_id'],
            content['title'],
            content['thumbnail'],
            content['duration'],
            content_type='audio'  # GUI는 음원 공유만 지원
        )
        
        if success:
            QMessageBox.information(self, '성공', message)
            self.close()
        else:
            QMessageBox.warning(self, '실패', message)

# ============================================================================
# 사용자 관리 다이얼로그
# ============================================================================

class UserManagementDialog(QDialog):
    """사용자 관리 다이얼로그"""
    
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.server = server
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('👥 사용자 관리')
        self.setGeometry(200, 200, 800, 500)
        
        layout = QVBoxLayout()
        
        # 헤더
        header = QLabel('👥 사용자 관리')
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #667eea;
            padding: 10px;
        """)
        layout.addWidget(header)
        
        # 사용자 테이블
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(6)
        self.user_table.setHorizontalHeaderLabels(['아이디', '상태', 'IP 주소', '가입일', '비밀번호', '차단'])
        self.user_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.user_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                background: white;
            }
            QHeaderView::section {
                background: #667eea;
                color: white;
                padding: 8px;
                font-weight: bold;
                border: none;
            }
        """)
        layout.addWidget(self.user_table)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton('🔄 새로고침')
        refresh_btn.clicked.connect(self.refresh_users)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        button_layout.addWidget(refresh_btn)
        
        # 공유하기 버튼
        share_btn = QPushButton('📤 공유하기')
        share_btn.clicked.connect(self.open_share_dialog)
        share_btn.setStyleSheet("""
            QPushButton {
                background: #667eea;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5568d3; }
        """)
        button_layout.addWidget(share_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton('닫기')
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover { background: #5a6268; }
        """)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 초기 데이터 로드
        self.refresh_users()
    
    def refresh_users(self):
        """사용자 목록 새로고침"""
        users = self.server.get_all_users()
        self.user_table.setRowCount(len(users))
        
        for row, user in enumerate(users):
            # 아이디
            self.user_table.setItem(row, 0, QTableWidgetItem(user['username']))
            
            # 상태
            status = '🟢 온라인' if user['is_online'] else '⚪ 오프라인'
            self.user_table.setItem(row, 1, QTableWidgetItem(status))
            
            # IP
            ip = user['ip'] if user['ip'] else '-'
            self.user_table.setItem(row, 2, QTableWidgetItem(ip))
            
            # 가입일
            created = user['created_at'][:10] if 'T' in user['created_at'] else user['created_at']
            self.user_table.setItem(row, 3, QTableWidgetItem(created))
            
            # 비밀번호 변경 버튼 (모든 사용자 가능)
            password_btn = QPushButton('🔑 변경')
            password_btn.setStyleSheet("""
                QPushButton {
                    background: #ffc107;
                    color: #333;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #e0a800; }
            """)
            password_btn.clicked.connect(lambda checked, u=user['username']: self.change_password(u))
            self.user_table.setCellWidget(row, 4, password_btn)
            
            # 차단 버튼 (admin 제외)
            if user['username'] != 'admin':
                block_btn = QPushButton('🚫 차단')
                block_btn.setStyleSheet("""
                    QPushButton {
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                        font-size: 12px;
                    }
                    QPushButton:hover { background: #c82333; }
                """)
                block_btn.clicked.connect(lambda checked, u=user['username']: self.block_user(u))
                self.user_table.setCellWidget(row, 5, block_btn)
            else:
                self.user_table.setItem(row, 5, QTableWidgetItem('-'))
    
    def open_share_dialog(self):
        """공유 다이얼로그 열기"""
        from PyQt5.QtWidgets import QInputDialog
        
        # 현재 로그인한 사용자 선택
        users = self.server.get_all_users()
        usernames = [u['username'] for u in users]
        
        username, ok = QInputDialog.getItem(
            self,
            '사용자 선택',
            '누구의 컨텐츠를 공유하시겠습니까?',
            usernames,
            0,
            False
        )
        
        if ok and username:
            dialog = ContentShareDialog(self.server, username, self)
            dialog.exec_()
    
    def change_password(self, username):
        """비밀번호 변경"""
        from PyQt5.QtWidgets import QInputDialog, QLineEdit
        
        new_password, ok = QInputDialog.getText(
            self,
            '비밀번호 변경',
            f'{username}의 새 비밀번호를 입력하세요:',
            QLineEdit.Password
        )
        
        if ok and new_password:
            if len(new_password) < 4:
                QMessageBox.warning(self, '오류', '비밀번호는 4자 이상이어야 합니다')
                return
            
            success, message = self.server.change_user_password(username, new_password)
            if success:
                QMessageBox.information(self, '성공', message)
            else:
                QMessageBox.warning(self, '실패', message)
    
    def block_user(self, username):
        """사용자 차단"""
        reply = QMessageBox.question(
            self,
            '사용자 차단',
            f'{username} 사용자를 차단하시겠습니까?\n\n• 계정이 삭제됩니다\n• IP가 영구 차단됩니다\n• 회원가입이 불가능합니다',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.server.block_user_ip(username)
            if success:
                QMessageBox.information(self, '성공', message)
                self.refresh_users()
            else:
                QMessageBox.warning(self, '실패', message)

# ============================================================================
# GUI 윈도우
# ============================================================================

class ServerControllerWindow(QMainWindow):
    """서버 컨트롤러"""
    
    def __init__(self):
        super().__init__()
        self.server_worker = None
        self.server_port = 7777
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('🎬 영상 다운로더 서버')
        self.setGeometry(100, 100, 700, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 헤더
        header = QLabel('🎬 영상 다운로더 서버')
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
            padding: 20px;
        """)
        main_layout.addWidget(header)
        
        # 서버 설정
        settings_group = QGroupBox('⚙️ 서버 설정')
        settings_layout = QVBoxLayout()
        
        port_layout = QHBoxLayout()
        port_label = QLabel('포트:')
        port_label.setMinimumWidth(80)
        port_layout.addWidget(port_label)
        
        self.port_input = QSpinBox()
        self.port_input.setMinimum(1024)
        self.port_input.setMaximum(65535)
        self.port_input.setValue(7777)
        self.port_input.setStyleSheet("""
            QSpinBox {
                padding: 8px;
                font-size: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
            }
        """)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch()
        
        settings_layout.addLayout(port_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # 제어 버튼
        control_group = QGroupBox('🎮 제어')
        control_layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton('🚀 시작')
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5568d3, stop:1 #6a3f8f);
            }
            QPushButton:disabled { background: #ccc; }
        """)
        self.start_btn.clicked.connect(self.start_server)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton('⏹️ 중지')
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #c82333; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.stop_btn.clicked.connect(self.stop_server)
        button_layout.addWidget(self.stop_btn)
        
        control_layout.addLayout(button_layout)
        
        self.open_browser_btn = QPushButton('🌐 사이트 열기')
        self.open_browser_btn.setMinimumHeight(50)
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
            QPushButton:disabled { background: #ccc; }
        """)
        self.open_browser_btn.clicked.connect(self.open_browser)
        control_layout.addWidget(self.open_browser_btn)
        
        self.open_folder_btn = QPushButton('📁 폴더 열기')
        self.open_folder_btn.setMinimumHeight(50)
        self.open_folder_btn.setStyleSheet("""
            QPushButton {
                background: #17a2b8;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #138496; }
        """)
        self.open_folder_btn.clicked.connect(self.open_video_folder)
        control_layout.addWidget(self.open_folder_btn)
        
        # 음원 파일 열기 버튼
        self.open_audio_folder_btn = QPushButton('🎵 음원 파일 열기')
        self.open_audio_folder_btn.setMinimumHeight(50)
        self.open_audio_folder_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #218838; }
        """)
        self.open_audio_folder_btn.clicked.connect(self.open_audio_folder)
        control_layout.addWidget(self.open_audio_folder_btn)
        
        # 👥 사용자 관리 버튼
        self.user_management_btn = QPushButton('👥 사용자 관리')
        self.user_management_btn.setMinimumHeight(50)
        self.user_management_btn.setStyleSheet("""
            QPushButton {
                background: #667eea;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5568d3; }
        """)
        self.user_management_btn.clicked.connect(self.open_user_management)
        control_layout.addWidget(self.user_management_btn)
        
        # 🔐 PIN 비밀번호 설정 버튼
        self.pin_setting_btn = QPushButton('🔐 PIN 비밀번호 변경')
        self.pin_setting_btn.setMinimumHeight(50)
        self.pin_setting_btn.setStyleSheet("""
            QPushButton {
                background: #ffc107;
                color: #1d1d1f;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #e0a800; }
        """)
        self.pin_setting_btn.clicked.connect(self.change_pin_code)
        control_layout.addWidget(self.pin_setting_btn)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # 로그
        status_group = QGroupBox('📊 상태')
        status_layout = QVBoxLayout()
        
        # 🔋 macOS 잠금 방지 상태 표시
        sleep_prevent_layout = QHBoxLayout()
        self.sleep_prevent_led = QLabel('●')
        self.sleep_prevent_led.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 20px;
                padding: 5px;
            }
        """)
        sleep_prevent_layout.addWidget(self.sleep_prevent_led)
        
        self.sleep_prevent_label = QLabel('macOS 잠금 방지: 대기 중')
        self.sleep_prevent_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                padding: 5px;
            }
        """)
        sleep_prevent_layout.addWidget(self.sleep_prevent_label)
        sleep_prevent_layout.addStretch()
        status_layout.addLayout(sleep_prevent_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.log_text.append("💡 '시작' 버튼을 클릭하세요")
        status_layout.addWidget(self.log_text)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 10px;
                padding: 15px;
                background-color: white;
            }
        """)
    
    def update_sleep_prevent_status(self, is_active):
        """macOS 잠금 방지 상태 업데이트"""
        if is_active:
            # 🟢 녹색 LED (활성)
            self.sleep_prevent_led.setStyleSheet("""
                QLabel {
                    color: #00ff00;
                    font-size: 20px;
                    padding: 5px;
                }
            """)
            self.sleep_prevent_label.setText('macOS 잠금 방지: 활성화 ✅')
            self.sleep_prevent_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #00aa00;
                    font-weight: bold;
                    padding: 5px;
                }
            """)
        else:
            # ⚪ 회색 LED (비활성)
            self.sleep_prevent_led.setStyleSheet("""
                QLabel {
                    color: #888888;
                    font-size: 20px;
                    padding: 5px;
                }
            """)
            self.sleep_prevent_label.setText('macOS 잠금 방지: 대기 중')
            self.sleep_prevent_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #666;
                    padding: 5px;
                }
            """)
    
    def add_log(self, message):
        """로그 추가"""
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.log_text.moveCursor(QTextCursor.End)
    
    def start_server(self):
        """서버 시작"""
        if self.server_worker and self.server_worker.isRunning():
            QMessageBox.warning(self, '경고', '이미 실행 중')
            return
        
        self.server_port = self.port_input.value()
        
        if self.is_port_in_use(self.server_port):
            QMessageBox.critical(self, '오류', f'{self.server_port}번 포트 사용 중')
            return
        
        self.add_log(f"🚀 서버 시작 중... ({self.server_port})")
        
        self.start_btn.setEnabled(False)
        self.port_input.setEnabled(False)
        
        self.server_worker = ServerWorker(self.server_port)
        self.server_worker.log_signal.connect(self.add_log)
        self.server_worker.started_signal.connect(self.on_server_started)
        self.server_worker.error_signal.connect(self.on_server_error)
        self.server_worker.stopped_signal.connect(self.on_server_stopped)
        self.server_worker.start()
    
    def on_server_started(self):
        """서버 시작 완료"""
        self.stop_btn.setEnabled(True)
        self.open_browser_btn.setEnabled(True)
        self.add_log("✅ 서버 시작 완료!")
        
        # 🔋 macOS 잠금 방지 LED 활성화
        self.update_sleep_prevent_status(True)
    
    def on_server_stopped(self):
        """서버 중지"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_browser_btn.setEnabled(False)
        
        # 🔋 macOS 잠금 방지 LED 비활성화
        self.update_sleep_prevent_status(False)
        self.port_input.setEnabled(True)
        self.add_log("⏹️ 서버 중지")
    
    def on_server_error(self, error):
        """서버 오류"""
        self.add_log(f"❌ {error}")
        QMessageBox.critical(self, '오류', error)
        self.start_btn.setEnabled(True)
        self.port_input.setEnabled(True)
    
    def stop_server(self):
        """서버 중지"""
        if self.server_worker and self.server_worker.isRunning():
            reply = QMessageBox.question(self, '확인', '서버를 중지하시겠습니까?',
                                        QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.add_log("⏹️ 중지 중...")
                self.stop_btn.setEnabled(False)
                self.open_browser_btn.setEnabled(False)
                self.server_worker.stop()
                
                if not self.server_worker.wait(5000):
                    self.server_worker.terminate()
                    self.on_server_stopped()
    
    def open_browser(self):
        """브라우저 열기"""
        url = f"http://localhost:{self.server_port}"
        self.add_log(f"🌐 {url}")
        webbrowser.open(url)
    
    def open_video_folder(self):
        """폴더 열기"""
        videos_dir = os.path.join(os.path.dirname(__file__), 'static', 'videos')
        os.makedirs(videos_dir, exist_ok=True)
        
        self.add_log(f"📁 {videos_dir}")
        
        if sys.platform == 'darwin':
            os.system(f'open "{videos_dir}"')
        elif sys.platform == 'win32':
            os.startfile(videos_dir)
        else:
            os.system(f'xdg-open "{videos_dir}"')
    
    def open_audio_folder(self):
        """음원 파일 폴더 열기"""
        temp_audio_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
        os.makedirs(temp_audio_dir, exist_ok=True)
        
        self.add_log(f"🎵 음원 파일 폴더: {temp_audio_dir}")
        
        # 파일 개수와 총 용량 계산
        try:
            file_count = 0
            total_size = 0
            for filename in os.listdir(temp_audio_dir):
                file_path = os.path.join(temp_audio_dir, filename)
                if os.path.isfile(file_path):
                    file_count += 1
                    total_size += os.path.getsize(file_path)
            
            total_size_mb = total_size / (1024 * 1024)
            self.add_log(f"💾 캐시된 음원: {file_count}개 파일, {total_size_mb:.1f}MB")
        except Exception as e:
            self.add_log(f"⚠️ 용량 계산 실패: {e}")
        
        # 폴더 열기
        if sys.platform == 'darwin':
            os.system(f'open "{temp_audio_dir}"')
        elif sys.platform == 'win32':
            os.startfile(temp_audio_dir)
        else:
            os.system(f'xdg-open "{temp_audio_dir}"')
    
    def is_port_in_use(self, port):
        """포트 사용 확인"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def open_user_management(self):
        """사용자 관리 다이얼로그 열기"""
        if self.server_worker and self.server_worker.server:
            dialog = UserManagementDialog(self.server_worker.server, self)
            dialog.exec_()
        else:
            QMessageBox.warning(self, '경고', '서버가 실행되지 않았습니다')
    
    def change_pin_code(self):
        """PIN 비밀번호 변경"""
        from PyQt5.QtWidgets import QInputDialog
        
        # PIN 파일 경로
        pin_file = os.path.join(os.path.dirname(__file__), 'pin_code.txt')
        
        # 현재 PIN 불러오기
        current_pin = '12345'
        if os.path.exists(pin_file):
            try:
                with open(pin_file, 'r', encoding='utf-8') as f:
                    current_pin = f.read().strip()
            except:
                pass
        
        # 현재 PIN 확인
        old_pin, ok = QInputDialog.getText(
            self, 
            '🔐 PIN 비밀번호 변경', 
            f'현재 PIN 비밀번호를 입력하세요:\n\n현재 PIN: {current_pin}',
            QLineEdit.Password
        )
        
        if not ok:
            return
        
        if old_pin != current_pin:
            QMessageBox.warning(self, '오류', '현재 PIN이 일치하지 않습니다')
            return
        
        # 새 PIN 입력
        new_pin, ok = QInputDialog.getText(
            self, 
            '🔐 새 PIN 설정', 
            '새 PIN 비밀번호를 입력하세요:\n(1~12자리)',
            QLineEdit.Normal
        )
        
        if not ok or not new_pin:
            return
        
        if len(new_pin) > 12:
            QMessageBox.warning(self, '오류', 'PIN은 최대 12자리까지 입력 가능합니다')
            return
        
        # 새 PIN 확인
        confirm_pin, ok = QInputDialog.getText(
            self, 
            '🔐 PIN 확인', 
            '새 PIN을 다시 입력하세요:',
            QLineEdit.Password
        )
        
        if not ok:
            return
        
        if new_pin != confirm_pin:
            QMessageBox.warning(self, '오류', 'PIN이 일치하지 않습니다')
            return
        
        # PIN 저장
        try:
            with open(pin_file, 'w', encoding='utf-8') as f:
                f.write(new_pin)
            
            QMessageBox.information(
                self, 
                '성공', 
                f'PIN 비밀번호가 변경되었습니다!\n\n새 PIN: {new_pin}\n\n※ 웹 로그인 페이지의 PIN이 즉시 변경됩니다.'
            )
            self.add_log(f"🔐 PIN 비밀번호 변경 완료: {new_pin}")
        except Exception as e:
            QMessageBox.critical(self, '오류', f'PIN 저장 실패: {str(e)}')
    
    def closeEvent(self, event):
        """종료"""
        if self.server_worker and self.server_worker.isRunning():
            reply = QMessageBox.question(self, '확인', '서버가 실행 중입니다. 종료하시겠습니까?',
                                        QMessageBox.Yes | QMessageBox.No)
            event.accept() if reply == QMessageBox.Yes else event.ignore()
        else:
            event.accept()


# ============================================================================
# 메인
# ============================================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('영상 다운로더 서버')
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(245, 245, 245))
    app.setPalette(palette)
    
    window = ServerControllerWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()