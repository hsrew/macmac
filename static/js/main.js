// 전역 변수
let currentVideo = null;
let allVideos = []; // 모든 영상 목록 저장
let allPlaylist = []; // 모든 재생 목록 저장
let allSearchResults = []; // 모든 검색 결과 저장
let displayedSearchCount = 20; // 현재 표시된 검색 결과 수
let isListView = false; // 목록 보기 상태
let audioElement = null; // 오디오 엘리먼트
let currentVideoId = null; // 현재 재생 중인 video_id
let downloadCheckInterval = null; // 다운로드 체크 인터벌
let currentPlaylistIndex = -1; // 현재 재생 중인 플레이리스트 인덱스
let nextTrackPrefetch = null; // 다음 곡 미리 준비된 데이터
let isStreamingMode = false; // 실시간 스트리밍 모드 (테슬라용) - 기본값: false (캐시 사용)

// 로딩 팝업 표시/숨기기 (조건부 표시)
function showLoadingPopup(text = '⚡ 음원 준비 중...', subtext = '잠시만 기다려주세요', forceShow = false) {
    // forceShow가 true이거나 다운로드 중일 때만 표시
    if (forceShow || text.includes('다운로드') || text.includes('준비')) {
        const popup = document.getElementById('loadingPopup');
        const textEl = popup.querySelector('.loading-text');
        const subtextEl = popup.querySelector('.loading-subtext');
        
        textEl.textContent = text;
        subtextEl.textContent = subtext;
        popup.style.display = 'flex';
        
        console.log('🔄 로딩 팝업 표시:', text);
    } else {
        console.log('⚡ 로딩 스킵 - 즉시 재생:', text);
    }
}

function hideLoadingPopup() {
    const popup = document.getElementById('loadingPopup');
    popup.style.display = 'none';
    
    console.log('✅ 로딩 팝업 숨김');
}

// 모바일 감지
function isMobileDevice() {
    const mobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
           (window.innerWidth <= 768);
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    
    console.log('🔍 기기 정보:', {
        mobile: mobile,
        safari: isSafari,
        ios: isIOS,
        userAgent: navigator.userAgent,
        width: window.innerWidth
    });
    
    return mobile;
}

// 테슬라 브라우저 감지
function isTeslaBrowser() {
    const userAgent = navigator.userAgent.toLowerCase();
    const isTesla = userAgent.includes('tesla') || 
                   userAgent.includes('model') || 
                   userAgent.includes('cybertruck') ||
                   (userAgent.includes('chrome') && userAgent.includes('linux') && window.screen.width > 2000);
    
    console.log('🚗 테슬라 브라우저 감지:', {
        isTesla: isTesla,
        userAgent: navigator.userAgent,
        screenWidth: window.screen.width
    });
    
    return isTesla;
}

// 스트리밍 모드 토글
function toggleStreamingMode() {
    const toggle = document.getElementById('streamingModeToggle');
    const label = document.getElementById('streamingModeLabel');
    
    isStreamingMode = toggle.checked;
    
    if (isStreamingMode) {
        label.textContent = '🚗 테슬라 모드 (실시간 스트리밍) - 활성화';
        label.style.color = '#2BAE66';
        showStatus('🚗 테슬라 모드 활성화 - 캐시 없이 실시간 스트리밍', 'success');
    } else {
        label.textContent = '🚗 테슬라 모드 (실시간 스트리밍)';
        label.style.color = '#666';
        showStatus('💾 일반 모드 - 캐시 사용 가능', 'info');
    }
    
    // 스킵 버튼 상태 업데이트
    updateSkipButtonsState();
    
    console.log('🔄 스트리밍 모드 변경:', isStreamingMode);
}

// 스킵 버튼 상태 업데이트
function updateSkipButtonsState() {
    const skipButtons = document.querySelectorAll('.skip-btn');
    
    skipButtons.forEach(btn => {
        if (isStreamingMode) {
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
            btn.title = '🚗 테슬라 모드: 실시간 스트리밍에서는 탐색 불가';
        } else {
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.title = btn.getAttribute('data-original-title') || '';
        }
    });
}

// YouTube URL에서 video ID 추출
function extractVideoId(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

// 페이지 로드 시 실행
// 접속자 통계 함수
function updateActiveUsers() {
    fetch('/api/active-users')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 카운터 업데이트
                document.getElementById('userCount').textContent = data.total_users;
                document.getElementById('popupUserCount').textContent = data.total_users;
                
                // 접속자 목록 업데이트
                const usersList = document.getElementById('activeUsersList');
                if (data.users.length === 0) {
                    usersList.innerHTML = '<div class="no-users">접속자가 없습니다</div>';
                } else {
                    usersList.innerHTML = data.users.map(user => `
                        <div class="user-item">
                            <div class="user-info">
                                <div class="user-device">${user.device}</div>
                                <div class="user-details">
                                    <span class="user-ip">IP: ${user.ip}</span>
                                    <span class="user-os">${user.os}</span>
                                    <span class="user-browser">${user.browser}</span>
                                </div>
                            </div>
                            <div class="user-time">${user.last_active}</div>
                        </div>
                    `).join('');
                }
            }
        })
        .catch(err => console.error('접속자 정보 로드 실패:', err));
}

function toggleActiveUsers() {
    const popup = document.getElementById('activeUsersPopup');
    if (popup.style.display === 'none' || popup.style.display === '') {
        popup.style.display = 'flex';
        updateActiveUsers(); // 팝업 열 때 즉시 업데이트
    } else {
        popup.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    audioElement = document.getElementById('audioElement');
    setupMediaSession();
    
    // 모바일 감지 로그
    if (isMobileDevice()) {
        console.log('📱 모바일 모드 활성화 - 로컬 파일 다운로드 후 재생');
    } else {
        console.log('💻 데스크톱 모드 - 즉시 재생 + 백그라운드 다운로드');
    }
    
    // 접속자 통계 업데이트 (5초마다)
    updateActiveUsers();
    setInterval(updateActiveUsers, 5000);
    
    // 🚗 테슬라 브라우저 자동 감지 (일반 사용자는 기본 OFF)
    if (isTeslaBrowser()) {
        const toggle = document.getElementById('streamingModeToggle');
        const label = document.getElementById('streamingModeLabel');
        
        toggle.checked = true;
        isStreamingMode = true;
        label.textContent = '🚗 테슬라 모드 (실시간 스트리밍) - 자동 활성화';
        label.style.color = '#2BAE66';
        
        // 스킵 버튼들 비활성화
        updateSkipButtonsState();
        
        showStatus('🚗 테슬라 브라우저 감지! 실시간 스트리밍 모드로 자동 전환', 'success');
        console.log('🚗 테슬라 브라우저 감지 - 스트리밍 모드 자동 활성화');
    }
    
    // 🎵 갤러리와 플레이리스트 로드 (테슬라 모드 감지 후!)
    loadGallery();
    loadPlaylist();
    
    // 새로고침 버튼 이벤트 리스너
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async function() {
            await hardRefresh();
        });
    }
});

// 영상 다운로드
async function downloadVideo() {
    const url = document.getElementById('videoUrl').value.trim();
    const statusMessage = document.getElementById('statusMessage');
    const downloadBtn = document.getElementById('downloadBtn');
    const btnText = downloadBtn.querySelector('.btn-text');
    const btnLoading = downloadBtn.querySelector('.btn-loading');
    
    if (!url) {
        showStatus('URL을 입력해주세요', 'error');
        return;
    }
    
    // 버튼 비활성화 및 로딩 표시
    downloadBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline-flex';
    showStatus('영상을 다운로드하는 중입니다... (시간이 걸릴 수 있습니다)', 'info');
    
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(data.message, 'success');
            document.getElementById('videoUrl').value = '';
            
            // 갤러리 새로고침
            setTimeout(() => {
                loadGallery();
            }, 1000);
        } else {
            showStatus(data.message || '다운로드에 실패했습니다', 'error');
        }
    } catch (error) {
        showStatus('서버 오류가 발생했습니다: ' + error.message, 'error');
    } finally {
        // 버튼 활성화
        downloadBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// 상태 메시지 표시
function showStatus(message, type) {
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.textContent = message;
    statusMessage.className = 'status-message ' + type;
    
    // 성공 메시지는 5초 후 자동 숨김
    if (type === 'success') {
        setTimeout(() => {
            statusMessage.textContent = '';
            statusMessage.className = 'status-message';
        }, 5000);
    }
}

// 갤러리 로드
async function loadGallery() {
    const gallery = document.getElementById('videoGallery');
    const emptyState = document.getElementById('emptyState');
    
    try {
        console.log('🎬 갤러리 로드 시작...');
        const response = await fetch('/api/videos');
        const data = await response.json();
        
        console.log('🎬 갤러리 응답:', data);
        
        if (data.success) {
            if (data.videos && data.videos.length > 0) {
                allVideos = data.videos; // 전역 변수에 저장
                displayVideos(allVideos);
            } else {
                console.log('🎬 영상 목록이 비어있습니다');
                gallery.innerHTML = '';
                emptyState.style.display = 'block';
            }
        } else {
            console.error('🎬 갤러리 로드 실패:', data.message);
            gallery.innerHTML = '';
            emptyState.style.display = 'block';
        }
    } catch (error) {
        console.error('❌ 갤러리 로드 실패:', error);
        gallery.innerHTML = '<p style="text-align: center; color: #999;">영상 목록을 불러오는데 실패했습니다</p>';
        showStatus('영상 목록을 불러올 수 없습니다', 'error');
    }
}

// 뷰 토글
function toggleView() {
    isListView = !isListView;
    const gallery = document.getElementById('videoGallery');
    const toggleBtn = document.getElementById('viewToggleBtn');
    
    if (isListView) {
        gallery.classList.add('list-view');
        gallery.classList.remove('video-grid');
        toggleBtn.textContent = '🎬';
        toggleBtn.title = '갤러리 보기';
    } else {
        gallery.classList.remove('list-view');
        gallery.classList.add('video-grid');
        toggleBtn.textContent = '📋';
        toggleBtn.title = '목록 보기';
    }
    
    displayVideos(allVideos);
}

// 영상 표시 함수
function displayVideos(videos) {
    const gallery = document.getElementById('videoGallery');
    const emptyState = document.getElementById('emptyState');
    
    gallery.innerHTML = '';
    
    if (videos.length > 0) {
        emptyState.style.display = 'none';
        
        if (isListView) {
            // 목록 보기
            videos.forEach(video => {
                const listItem = createVideoListItem(video);
                gallery.appendChild(listItem);
            });
        } else {
            // 갤러리 보기
            videos.forEach(video => {
                const card = createVideoCard(video);
                gallery.appendChild(card);
            });
        }
    } else {
        emptyState.style.display = 'block';
    }
}

// 검색 기능
function searchVideos() {
    const searchInput = document.getElementById('searchInput');
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    if (searchTerm === '') {
        displayVideos(allVideos);
        return;
    }
    
    const filteredVideos = allVideos.filter(video => {
        const title = video.title.toLowerCase();
        const platform = video.platform.toLowerCase();
        return title.includes(searchTerm) || platform.includes(searchTerm);
    });
    
    displayVideos(filteredVideos);
}

// 목록 아이템 생성 (리스트 뷰)
function createVideoListItem(video) {
    const item = document.createElement('div');
    item.className = 'video-list-item';
    
    const platformClass = video.platform || 'youtube';
    const date = formatDate(video.downloaded_at);
    const duration = formatDuration(video.duration);
    
    // 공유받은 영상 확인
    const isShared = video.is_shared || video.shared_from;
    const sharedBadge = isShared ? `<span class="shared-badge">📤 ${escapeHtml(video.shared_from)}님이 공유</span>` : '';
    
    // 썸네일 URL 처리
    let thumbnailUrl;
    if (isShared && video.thumbnail && video.thumbnail.startsWith('http')) {
        // 공유받은 영상: 외부 썸네일 URL
        thumbnailUrl = video.thumbnail;
    } else if (video.thumbnail && video.thumbnail.endsWith('_thumb.jpg')) {
        // 로컬 썸네일
        thumbnailUrl = `/api/video/${encodeURIComponent(video.thumbnail)}`;
    } else {
        thumbnailUrl = null;
    }
    
    // 썸네일 클릭 이벤트
    item.innerHTML = `
        <div class="list-thumbnail">
            ${thumbnailUrl 
                ? `<img src="${thumbnailUrl}" alt="${escapeHtml(video.title)}">`
                : `<div class="no-thumbnail">📹</div>`
            }
        </div>
        <div class="list-info">
            <div class="list-title">${escapeHtml(video.title)}</div>
            <div class="list-meta">
                <span class="platform-badge ${platformClass}">${platformClass}</span>
                <span>${duration ? duration + ' • ' : ''}${date} ${sharedBadge}</span>
            </div>
        </div>
        <div class="list-actions">
            <button class="list-btn download-list-btn" title="다운로드">
                ⬇️
            </button>
            <button class="list-btn share-list-btn" title="공유">
                📤
            </button>
            <button class="list-btn delete-list-btn" title="삭제">
                🗑️
            </button>
        </div>
    `;
    
    // 썸네일과 제목 클릭 시 재생
    const thumbnail = item.querySelector('.list-thumbnail');
    const info = item.querySelector('.list-info');
    thumbnail.addEventListener('click', () => openVideo(video));
    info.addEventListener('click', () => openVideo(video));
    
    // 다운로드 버튼 클릭 이벤트
    const downloadBtn = item.querySelector('.download-list-btn');
    downloadBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        
        const isShared = video.is_shared || video.shared_from;
        if (isShared) {
            // 공유받은 영상: 브라우저 다운로드만 (재생목록에 추가 안 됨)
            console.log('📤 공유받은 영상 브라우저 다운로드:', video.filename);
            if (confirm(`"${video.title}"\n\n📤 ${video.shared_from}님이 공유한 영상입니다.\n컴퓨터로 다운로드하시겠습니까?`)) {
                browserDownload(video.filename);
            }
        } else {
            // 본인 영상: 브라우저 다운로드
            browserDownload(video.filename);
        }
    });
    
    // 공유 버튼 클릭 이벤트
    const shareBtn = item.querySelector('.share-list-btn');
    shareBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        
        console.log('📤 영상 공유 버튼 클릭:', video);
        
        try {
            // video_id 추출 (여러 방법 시도)
            let videoId = video.video_id;
            
            if (!videoId && video.url) {
                const match = video.url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})/);
                if (match) videoId = match[1];
            }
            
            if (!videoId && video.filename) {
                videoId = extractVideoIdFromFilename(video.filename);
            }
            
            console.log('🔍 video_id 추출:', videoId);
            
            // URL 생성
            let url = video.url || '';
            if (!url && videoId) {
                url = `https://www.youtube.com/watch?v=${videoId}`;
            }
            
            console.log('🔗 URL 생성:', url);
            
            // 영상 데이터를 공유용으로 변환
            const shareItem = {
                title: video.title,
                thumbnail: thumbnailUrl,
                duration: video.duration,
                url: url,
                video_id: videoId,
                filename: video.filename  // 실제 파일명 추가!
            };
            
            console.log('📦 공유 아이템:', shareItem);
            
            openShareModal(shareItem, 'video');  // 갤러리는 항상 영상
        } catch (error) {
            console.error('❌ 영상 공유 오류:', error);
            showStatus('영상 공유 중 오류가 발생했습니다', 'error');
        }
    });
    
    // 삭제 버튼 클릭 이벤트
    const deleteBtn = item.querySelector('.delete-list-btn');
    deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        
        const isShared = video.is_shared || video.shared_from;
        console.log('🗑️ 삭제 버튼 클릭:', {
            title: video.title,
            isShared: isShared,
            shared_from: video.shared_from,
            filename: video.filename
        });
        
        if (isShared) {
            // 공유받은 영상: 메타데이터에서만 삭제 (원본 파일 보호)
            console.log('📤 공유받은 영상 - 메타데이터만 삭제');
            if (confirm(`"${video.title}"\n\n📤 ${video.shared_from}님이 공유한 영상입니다.\n\n❌ 내 목록에서만 제거하시겠습니까?\n\n✅ 원본 파일은 삭제되지 않습니다\n(공유자의 파일 보호)`)) {
                await deleteSharedVideo(video.video_id, video.title);
            }
        } else {
            // 본인 영상: 실제 파일 삭제
            console.log('💾 본인 영상 - 서버에서 파일 삭제');
            if (confirm(`"${video.title}"\n\n💾 본인이 다운로드한 영상입니다.\n\n⚠️ 서버에서 영구 삭제하시겠습니까?\n(복구 불가능)`)) {
                deleteVideoConfirm(video.filename, video.title);
            }
        }
    });
    
    return item;
}

// 파일명에서 video_id 추출 (유튜브 영상용)
function extractVideoIdFromFilename(filename) {
    console.log('🔍 파일명에서 video_id 추출 시도:', filename);
    
    // 유튜브 video_id는 정확히 11자리
    const match = filename.match(/\b([a-zA-Z0-9_-]{11})\b/);
    const result = match ? match[1] : '';
    
    console.log('📝 추출 결과:', result);
    return result;
}

// 비디오 카드 생성
function createVideoCard(video) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.onclick = () => openVideoSimple(video);
    
    const platformClass = video.platform || 'youtube';
    const duration = formatDuration(video.duration);
    const date = formatDate(video.downloaded_at);
    
    // 공유받은 영상인지 확인
    const isShared = video.is_shared || video.shared_from;
    const sharedBadge = isShared ? `<span class="shared-badge">📤 ${escapeHtml(video.shared_from)}님이 공유</span>` : '';
    
    // 썸네일 처리
    let thumbnailContent;
    
    if (isShared && video.thumbnail) {
        // 공유받은 영상: 외부 썸네일 URL 사용
        thumbnailContent = `<img src="${escapeHtml(video.thumbnail)}" alt="${escapeHtml(video.title)}" style="width: 100%; height: 100%; object-fit: cover;">`;
    } else {
        // 로컬 영상: 기존 로직
        const isLocalThumbnail = video.thumbnail && video.thumbnail.endsWith('_thumb.jpg');
        const encodedThumbnail = isLocalThumbnail ? encodeURIComponent(video.thumbnail) : '';
        const encodedFilename = encodeURIComponent(video.filename);
        
        thumbnailContent = isLocalThumbnail 
            ? `<img src="/api/video/${encodedThumbnail}" alt="${escapeHtml(video.title)}" style="width: 100%; height: 100%; object-fit: cover;">`
            : `<video preload="metadata" muted playsinline>
                <source src="/api/video/${encodedFilename}#t=0.5" type="video/mp4">
            </video>`;
    }
    
    card.innerHTML = `
        <div class="video-thumbnail">
            ${thumbnailContent}
            <div class="play-overlay-simple">
                <div class="play-icon-simple">▶️</div>
            </div>
        </div>
        <div class="video-details">
            <div class="video-title">${escapeHtml(video.title)}</div>
            <div class="video-meta">
                <span class="platform-badge ${platformClass}">${platformClass}</span>
                <span>${date}</span>
                ${sharedBadge}
            </div>
        </div>
    `;
    
    return card;
}

// 브라우저 다운로드 (크롬 웹 다운로드)
function browserDownload(filename) {
    // URL 인코딩 (특수문자 처리)
    const encodedFilename = encodeURIComponent(filename);
    const videoUrl = `/api/video/${encodedFilename}`;
    
    // a 태그로 다운로드 (브라우저 기본 다운로드 창 사용)
    const a = document.createElement('a');
    a.href = videoUrl;
    a.download = filename;
    a.style.display = 'none';
    
    document.body.appendChild(a);
    a.click();
    
    // 약간의 지연 후 제거
    setTimeout(() => {
        document.body.removeChild(a);
    }, 100);
    
    // 상태 메시지
    showStatus('다운로드가 시작되었습니다. 브라우저 다운로드를 확인하세요.', 'success');
}

// 목록 보기에서 빠른 다운로드
async function quickDownload(filename, title) {
    browserDownload(filename);
}

// 간단한 영상 재생 (갤러리 모드 - 버튼 없음)
async function openVideoSimple(video) {
    currentVideo = video;
    
    // 공유받은 영상인지 확인
    const isShared = video.is_shared || video.shared_from;
    
    if (isShared) {
        // 공유받은 영상: 공유자의 파일을 직접 재생 (서버에 이미 있음!)
        console.log('📤 공유받은 영상 재생 (서버 파일 직접 사용):', video);
        console.log('📂 파일명:', video.filename);
        
        if (!video.filename || video.filename.includes('_shared')) {
            // 파일명이 없거나 가상 파일명인 경우 → 스트리밍으로 재생
            console.warn('⚠️ 실제 파일명이 없음 - 스트리밍으로 전환');
            showLoadingPopup('📹 서버에 영상 다운로드 중...', '잠시만 기다려주세요', true);
            await watchVideoFromSearch(video.url, video.title);
            return;
        }
        
        const modal = document.getElementById('videoModal');
        const modalVideo = document.getElementById('modalVideo');
        const modalVideoSource = document.getElementById('modalVideoSource');
        
        // 공유자의 실제 파일 사용 (다운로드 없이 바로 재생!)
        const encodedFilename = encodeURIComponent(video.filename);
        const videoUrl = `/api/video/${encodedFilename}`;
        
        console.log('🔗 영상 URL:', videoUrl);
        
        modalVideoSource.src = videoUrl;
        
        // 비디오 리셋 후 로드
        modalVideo.pause();
        modalVideo.currentTime = 0;
        modalVideo.load();
        
        // 로드 후 자동 재생
        modalVideo.addEventListener('loadeddata', function onLoaded() {
            console.log('✅ 영상 로드 완료 - 재생 시작');
            modalVideo.play().catch(e => console.log('자동 재생 실패:', e));
            modalVideo.removeEventListener('loadeddata', onLoaded);
        });
        
        // 에러 처리
        modalVideo.addEventListener('error', function onError(e) {
            console.error('❌ 영상 로드 실패:', e);
            console.error('파일명:', video.filename);
            console.error('URL:', videoUrl);
            hideLoadingPopup();
            showStatus('영상 파일을 찾을 수 없습니다. 스트리밍으로 전환합니다...', 'info');
            
            // 스트리밍으로 전환
            modal.style.display = 'none';
            watchVideoFromSearch(video.url, video.title);
            modalVideo.removeEventListener('error', onError);
        }, { once: true });
        
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        
        console.log('✅ 공유받은 영상 즉시 재생 시도 (다운로드 없음)');
    } else {
        // 로컬 영상: 기존 방식
        const modal = document.getElementById('videoModal');
        const modalVideo = document.getElementById('modalVideo');
        const modalVideoSource = document.getElementById('modalVideoSource');
        
        // URL 인코딩 (특수문자 처리)
        const encodedFilename = encodeURIComponent(video.filename);
        modalVideoSource.src = `/api/video/${encodedFilename}`;
        
        // 비디오 리셋 후 로드
        modalVideo.pause();
        modalVideo.currentTime = 0;
        modalVideo.load();
        
        // 로드 후 자동 재생
        modalVideo.addEventListener('loadeddata', function onLoaded() {
            modalVideo.play().catch(e => console.log('자동 재생 실패:', e));
            modalVideo.removeEventListener('loadeddata', onLoaded);
        });
        
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

// 비디오 재생 모달 열기 (리스트 모드 - 버튼 포함)
function openVideo(video) {
    openVideoSimple(video);
}


// 모달 닫기
function closeModal() {
    const modal = document.getElementById('videoModal');
    const modalVideo = document.getElementById('modalVideo');
    
    modal.style.display = 'none';
    modalVideo.pause();
    document.body.style.overflow = 'auto';
    currentVideo = null;
}

// ESC 키로 모달 닫기
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeModal();
        closeWatchModal();
        closeShareModal();
    }
});

// 영상 삭제 확인 (갤러리에서)
function deleteVideoConfirm(filename, title) {
    if (confirm(`"${title}"\n\n📹 본인이 다운로드한 영상을 삭제하시겠습니까?\n\n⚠️ 서버에서 실제 파일이 영구 삭제됩니다!`)) {
        deleteVideoFromGallery(filename);
    }
}

// 갤러리에서 영상 삭제
async function deleteVideoFromGallery(filename) {
    try {
        // URL 인코딩 (특수문자, 공백, # 등 처리)
        const encodedFilename = encodeURIComponent(filename);
        
        const response = await fetch(`/api/delete/${encodedFilename}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadGallery();
            showStatus('영상이 삭제되었습니다', 'success');
        } else {
            alert(data.message || '삭제에 실패했습니다');
        }
    } catch (error) {
        console.error('삭제 오류:', error);
        alert('삭제 중 오류가 발생했습니다: ' + error.message);
    }
}

// 공유받은 영상 삭제 (메타데이터에서만)
async function deleteSharedVideo(videoId, title) {
    try {
        console.log('📤 공유받은 영상 삭제 요청:', videoId, title);
        
        const response = await fetch('/api/delete-shared', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_id: videoId
            })
        });
        
        const data = await response.json();
        console.log('📤 공유받은 영상 삭제 응답:', data);
        
        if (data.success) {
            console.log('✅ 공유받은 영상 삭제 성공 - 원본 파일은 보호됨');
            loadGallery();
            loadPlaylist();  // 재생 목록도 새로고침
            showStatus('✅ 내 목록에서 제거했습니다 (원본 파일 보호)', 'success');
        } else {
            console.error('❌ 공유받은 영상 삭제 실패:', data.message);
            showStatus(data.message || '삭제에 실패했습니다', 'error');
        }
    } catch (error) {
        console.error('❌ 공유받은 영상 삭제 오류:', error);
        showStatus('삭제 중 오류가 발생했습니다: ' + error.message, 'error');
    }
}

// 백그라운드 오디오 스트리밍
async function streamAudio() {
    const url = document.getElementById('videoUrl').value.trim();
    const streamBtn = document.getElementById('streamBtn');
    
    if (!url) {
        showStatus('URL을 입력해주세요', 'error');
        return;
    }
    
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        showStatus('유튜브 URL만 지원합니다', 'error');
        return;
    }
    
    // 기존 다운로드 체크 중지
    if (downloadCheckInterval) {
        clearInterval(downloadCheckInterval);
        downloadCheckInterval = null;
    }
    
    // ⚡ 로딩창을 버튼 클릭 즉시 표시 (지연 시간 제거)
    showLoadingPopup('⚡ 음원 준비 중...', '잠시만 기다려주세요', true);
    
    // 버튼이 있는 경우에만 비활성화
    if (streamBtn) {
        streamBtn.disabled = true;
        streamBtn.textContent = '⚡ 로딩';
    }
    showStatus('⚡ 빠른 로딩...', 'info');
    
    try {
        // 🚗 스트리밍 모드 (테슬라용) - 서버에서 실시간 URL만 가져오기
        console.log('🔍 디버깅: isStreamingMode =', isStreamingMode);
        console.log('🔍 디버깅: typeof isStreamingMode =', typeof isStreamingMode);
        
        // 🚗 강제로 테슬라 모드 활성화 (디버깅용)
        const toggle = document.getElementById('streamingModeToggle');
        console.log('🔍 토글 엘리먼트:', toggle);
        console.log('🔍 토글 체크 상태:', toggle ? toggle.checked : '토글 없음');
        
        if (toggle && toggle.checked) {
            isStreamingMode = true;
            console.log('🚗 토글 체크됨 - isStreamingMode 강제 설정:', isStreamingMode);
        } else {
            console.log('❌ 토글 체크 안됨 또는 토글 없음');
        }
        
        // 🚗 최종 확인
        console.log('🔍 최종 isStreamingMode:', isStreamingMode);
        
        // 🚗 토글이 체크되어 있으면 무조건 테슬라 모드 실행
        if (toggle && toggle.checked) {
            console.log('🚗 토글 체크됨 - 테슬라 모드 강제 실행!');
            isStreamingMode = true;
        }
        
        if (isStreamingMode) {
            console.log('🚗 스트리밍 모드 활성화됨 - 서버에서 실시간 URL 요청');
            console.log('🚗 isStreamingMode:', isStreamingMode);
            showStatus('🚗 테슬라 모드: 실시간 스트리밍 URL 요청 중...', 'info');
            
            // 서버에 실시간 스트리밍 모드임을 알림
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30초 타임아웃
            
            const response = await fetch('/api/stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ 
                    url: url,
                    is_mobile: false,
                    streaming_mode: true  // 테슬라 모드임을 서버에 알림
                }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.message || '스트리밍 URL 가져오기 실패');
            }
            
            // 오디오 플레이어 설정
            const playerSection = document.getElementById('audioPlayer');
            const playerTitle = document.getElementById('playerTitle');
            const playerSubtitle = document.getElementById('playerSubtitle');
            const audioEl = document.getElementById('audioElement');
            
            // 이전 오디오 정리
            audioEl.pause();
            audioEl.src = '';
            
            // 🚗 실시간 스트리밍 URL 사용 (캐시 없음)
            audioEl.src = data.audio_url;
            audioEl.preload = 'none'; // 캐시 방지
            audioEl.load();
            
            playerTitle.textContent = data.title || '실시간 스트리밍';
            playerSubtitle.textContent = '🚗 테슬라 모드 - 캐시 없음';
            
            playerSection.style.display = 'block';
            
            // 버튼 복원
            if (streamBtn) {
                streamBtn.disabled = false;
                streamBtn.textContent = '🎵 재생';
            }
            
            // 재생 시도
            const playPromise = audioEl.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    console.log('✅ 테슬라 모드 재생 성공 - 실시간 스트리밍');
                    hideLoadingPopup();
                    showStatus('🚗 테슬라 모드: 실시간 스트리밍 시작! (캐시 없음)', 'success');
                }).catch(err => {
                    console.error('❌ 테슬라 모드 재생 실패:', err);
                    hideLoadingPopup();
                    showStatus('🚗 테슬라 모드: 재생 버튼을 눌러주세요', 'info');
                });
            }
            
            return;
        }
        
        // 일반 모드 (캐시 사용)
        console.log('💾 일반 모드 - 캐시 사용');
        console.log('💾 isStreamingMode:', isStreamingMode);
        const isMobile = isMobileDevice();
        if (isMobile) {
            console.log('📱 모바일 기기 감지 - 다운로드 후 재생 모드');
            showStatus('📱 모바일 최적화: 고품질 다운로드 중... (최대 60초 소요)', 'info');
        }
        
        // 직접 URL 방식 (모바일 최적화)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), isMobile ? 90000 : 30000); // 모바일 90초, 데스크톱 30초
        
        const response = await fetch('/api/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                url: url,
                is_mobile: isMobile
            }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        const data = await response.json();
        
        if (!data.success) {
            // 포맷 지원 안함 에러 처리
            if (data.error_type === 'format_not_available') {
                showStatus(`❌ ${data.message}`, 'error');
                hideLoadingPopup();
                return;
            }
            throw new Error(data.message || '알 수 없는 오류');
        }
        
        // ⚡ 로딩창은 이미 표시되어 있음 (streamAudio 시작 시 표시됨)
        // 추가 메시지만 업데이트
        if (data.downloading && !data.from_cache && !data.local_file) {
            // 다운로드 중인 경우에만 메시지 업데이트
            const popup = document.getElementById('loadingPopup');
            const textEl = popup.querySelector('.loading-text');
            const subtextEl = popup.querySelector('.loading-subtext');
            textEl.textContent = '⚡ 서버에 음원 다운로드 중...';
            subtextEl.textContent = '처음 재생하는 곡입니다. 잠시만 기다려주세요';
        }
        
        if (data.success && data.audio_url) {
            const playerSection = document.getElementById('audioPlayer');
            const playerTitle = document.getElementById('playerTitle');
            const playerSubtitle = document.getElementById('playerSubtitle');
            const audioEl = document.getElementById('audioElement');
            
            // 이전 오디오 정리
            audioEl.pause();
            audioEl.src = '';
            
            // Safari 감지
            const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
            const isMobile = isMobileDevice();
            
            // 📱 모바일 Safari 고속 로딩 최적화
            if (isMobile) {
                audioEl.setAttribute('webkit-playsinline', 'true');
                audioEl.setAttribute('playsinline', 'true');
            }
            
            // 🚀 항상 서버 URL 사용 (서버가 YouTube보다 빠름!)
            let audioUrl = data.audio_url;
            let useYouTubeCDN = false;
            
            console.log('🎵 서버 스트리밍 사용 (로컬 파일 또는 YouTube 중계)');
            
            console.log(`🎵 오디오 설정 시작:`, {
                safari: isSafari,
                ios: isIOS,
                mobile: isMobile,
                localFile: data.local_file,
                useYouTubeCDN: useYouTubeCDN,
                audioUrl: audioUrl
            });
            
            // 새 오디오 설정
            audioEl.src = audioUrl;
            
            // 오디오 preload 설정
            audioEl.preload = 'auto';
            
            playerTitle.textContent = data.title;
            playerSubtitle.textContent = `${formatDuration(data.duration)} • YouTube`;
            
            playerSection.style.display = 'block';
            
            // 즉시 재생
            const playPromise = audioEl.play();
            if (playPromise !== undefined) {
                playPromise.then(() => {
                    console.log('✅ 오디오 재생 성공');
                    hideLoadingPopup();
                    
                    if (data.from_cache) {
                        showStatus('⚡ 캐시에서 즉시 재생! (초고속)', 'success');
                    } else if (data.local_file) {
                        showStatus('⚡ 로컬 파일 재생! (고속 탐색 가능)', 'success');
                    } else if (data.instant_play) {
                        showStatus('⚡ 즉시 재생! (대기 시간 0초, 백그라운드 다운로드 중)', 'success');
                    } else if (data.downloading) {
                        showStatus('🎵 재생 시작! (백그라운드 다운로드 중)', 'info');
                    } else {
                        showStatus('🎵 재생 시작!', 'success');
                    }
                }).catch(err => {
                    console.error('❌ 재생 실패:', err);
                    hideLoadingPopup();
                    showStatus('재생 버튼을 눌러주세요', 'info');
                });
            }
            
            updateMediaSession(data.title, data.thumbnail);
            addToPlaylist(url, data.title, data.thumbnail, data.duration);
            
            // video_id 저장
            if (data.video_id) {
                currentVideoId = data.video_id;
            }
            
            // 백그라운드 다운로드 중이면 완료 체크 시작 (데스크톱만)
            if (data.downloading && data.video_id && !data.mobile_optimized) {
                startDownloadCheck(data.video_id);
            }
            
            document.getElementById('videoUrl').value = '';
        } else {
            showStatus(data.message || '오디오를 가져올 수 없습니다', 'error');
        }
    } catch (error) {
        console.error('스트리밍 오류:', error);
        
        // 🎬 로딩 팝업 숨기기
        hideLoadingPopup();
        
        if (error.name === 'AbortError') {
            showStatus('⏱️ 다운로드 시간 초과 - 다시 시도해주세요', 'error');
        } else {
            showStatus('스트리밍 실패: ' + error.message, 'error');
        }
    } finally {
        // 버튼이 있는 경우에만 활성화
        if (streamBtn) {
            streamBtn.disabled = false;
            streamBtn.textContent = '🎵 재생';
        }
    }
}

// Media Session API 설정 (백그라운드 재생)
function setupMediaSession() {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.setActionHandler('play', () => {
            audioElement.play();
        });
        
        navigator.mediaSession.setActionHandler('pause', () => {
            audioElement.pause();
        });
        
        navigator.mediaSession.setActionHandler('seekbackward', () => {
            audioElement.currentTime = Math.max(audioElement.currentTime - 10, 0);
        });
        
        navigator.mediaSession.setActionHandler('seekforward', () => {
            audioElement.currentTime = Math.min(audioElement.currentTime + 10, audioElement.duration);
        });
    }
}

// 다운로드 완료 체크 시작
function startDownloadCheck(videoId) {
    // 기존 체크 중지
    if (downloadCheckInterval) {
        clearInterval(downloadCheckInterval);
    }
    
    console.log('🔍 다운로드 완료 체크 시작:', videoId);
    
    // 5초마다 체크
    downloadCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/check-download/${videoId}`);
            const data = await response.json();
            
            if (data.success && data.ready) {
                console.log('✅ 다운로드 완료! 로컬 파일로 전환');
                
                // 현재 재생 중인 video_id와 같으면 전환
                if (currentVideoId === videoId) {
                    const audioEl = document.getElementById('audioElement');
                    const currentTime = audioEl.currentTime;
                    const wasPaused = audioEl.paused;
                    
                    // 로컬 파일로 전환
                    audioEl.src = data.audio_url;
                    audioEl.currentTime = currentTime;
                    
                    if (!wasPaused) {
                        audioEl.play().catch(err => {
                            console.log('재생 재개 실패:', err);
                        });
                    }
                    
                    showStatus('고속 탐색 모드 활성화! ⚡', 'success');
                }
                
                // 체크 중지
                clearInterval(downloadCheckInterval);
                downloadCheckInterval = null;
            }
        } catch (error) {
            console.error('다운로드 체크 오류:', error);
        }
    }, 5000);
}

// Media Session 메타데이터 업데이트
function updateMediaSession(title, thumbnail) {
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: title,
            artist: 'YouTube',
            album: '영상 다운로더',
            artwork: thumbnail ? [
                { src: thumbnail, sizes: '512x512', type: 'image/jpeg' }
            ] : []
        });
    }
}

// 플레이어 닫기
function closePlayer() {
    const playerSection = document.getElementById('audioPlayer');
    audioElement.pause();
    audioElement.currentTime = 0;
    audioElement.src = '';
    playerSection.style.display = 'none';
    
    // 다운로드 체크 중지
    if (downloadCheckInterval) {
        clearInterval(downloadCheckInterval);
        downloadCheckInterval = null;
    }
    currentVideoId = null;
}

// 3분 뒤로 가기
function skipBackward() {
    if (!audioElement) return;
    
    // 🚗 테슬라 모드에서는 스킵 불가 (실시간 스트리밍)
    if (isStreamingMode) {
        showStatus('🚗 테슬라 모드: 실시간 스트리밍에서는 탐색이 불가능합니다', 'info');
        return;
    }
    
    const skipTime = 180; // 3분 = 180초
    const oldTime = audioElement.currentTime;
    const newTime = Math.max(0, audioElement.currentTime - skipTime);
    
    audioElement.currentTime = newTime;
    
    console.log(`⏪ 3분 뒤로: ${formatTime(oldTime)} → ${formatTime(newTime)}`);
    showStatus(`⏪ 3분 뒤로 이동`, 'info');
}

// 3분 앞으로 가기
function skipForward() {
    if (!audioElement) return;
    
    // 🚗 테슬라 모드에서는 스킵 불가 (실시간 스트리밍)
    if (isStreamingMode) {
        showStatus('🚗 테슬라 모드: 실시간 스트리밍에서는 탐색이 불가능합니다', 'info');
        return;
    }
    
    const skipTime = 180; // 3분 = 180초
    const oldTime = audioElement.currentTime;
    const newTime = Math.min(audioElement.duration || Infinity, audioElement.currentTime + skipTime);
    
    audioElement.currentTime = newTime;
    
    console.log(`⏩ 3분 앞으로: ${formatTime(oldTime)} → ${formatTime(newTime)}`);
    showStatus(`⏩ 3분 앞으로 이동`, 'info');
}

// 10초 뒤로 가기 (미세 조정)
function skipBackward10() {
    if (!audioElement) return;
    
    // 🚗 테슬라 모드에서는 스킵 불가 (실시간 스트리밍)
    if (isStreamingMode) {
        showStatus('🚗 테슬라 모드: 실시간 스트리밍에서는 탐색이 불가능합니다', 'info');
        return;
    }
    
    const skipTime = 10; // 10초
    const oldTime = audioElement.currentTime;
    const newTime = Math.max(0, audioElement.currentTime - skipTime);
    
    audioElement.currentTime = newTime;
    
    console.log(`⏪ 10초 뒤로: ${formatTime(oldTime)} → ${formatTime(newTime)}`);
    showStatus(`⏪ 10초 뒤로`, 'info');
}

// 10초 앞으로 가기 (미세 조정)
function skipForward10() {
    if (!audioElement) return;
    
    // 🚗 테슬라 모드에서는 스킵 불가 (실시간 스트리밍)
    if (isStreamingMode) {
        showStatus('🚗 테슬라 모드: 실시간 스트리밍에서는 탐색이 불가능합니다', 'info');
        return;
    }
    
    const skipTime = 10; // 10초
    const oldTime = audioElement.currentTime;
    const newTime = Math.min(audioElement.duration || Infinity, audioElement.currentTime + skipTime);
    
    audioElement.currentTime = newTime;
    
    console.log(`⏩ 10초 앞으로: ${formatTime(oldTime)} → ${formatTime(newTime)}`);
    showStatus(`10초 ⏩`, 'info');
}

// 시간 포맷팅 (초 → MM:SS)
function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// 갤러리 새로고침
function refreshGallery() {
    const refreshBtn = document.querySelector('.refresh-btn');
    refreshBtn.style.transform = 'rotate(360deg)';
    loadGallery();
    setTimeout(() => {
        refreshBtn.style.transform = '';
    }, 600);
}

// 강력 새로고침 (캐시 초기화) - 최강 버전
async function hardRefresh() {
    if (confirm('강력 새로고침을 진행하시겠습니까?\n\n🔥 완전 초기화:\n- 모든 브라우저 캐시\n- Service Worker 캐시\n- IndexedDB\n- sessionStorage\n- 미디어 캐시\n\n✅ 유지:\n- 재생 목록\n- 로그인 정보')) {
        try {
            console.log('🔥 강력 새로고침 시작...');
            
            // 1. 모든 미디어 요소 정리 (메모리 캐시)
            try {
                const audioEl = document.getElementById('audioElement');
                const modalVideo = document.getElementById('modalVideo');
                const watchVideo = document.getElementById('watchVideo');
                
                if (audioEl) {
                    audioEl.pause();
                    audioEl.src = '';
                    audioEl.load();
                    console.log('🗑️ 오디오 캐시 정리');
                }
                if (modalVideo) {
                    modalVideo.pause();
                    modalVideo.src = '';
                    modalVideo.load();
                }
                if (watchVideo) {
                    watchVideo.pause();
                    watchVideo.src = '';
                    watchVideo.load();
                }
            } catch (e) {
                console.warn('미디어 정리 실패:', e);
            }
            
            // 2. Service Worker 캐시 완전 삭제
            if ('caches' in window) {
                const cacheNames = await caches.keys();
                console.log(`🗑️ Service Worker 캐시 삭제: ${cacheNames.length}개`);
                await Promise.all(cacheNames.map(name => caches.delete(name)));
                console.log('✅ Service Worker 캐시 삭제 완료');
            }
            
            // 3. IndexedDB 초기화
            if ('indexedDB' in window) {
                try {
                    const databases = await indexedDB.databases();
                    for (const db of databases) {
                        indexedDB.deleteDatabase(db.name);
                        console.log(`🗑️ IndexedDB 삭제: ${db.name}`);
                    }
                } catch (e) {
                    console.warn('IndexedDB 초기화 실패:', e);
                }
            }
            
            // 4. sessionStorage 초기화 (임시 데이터만)
            try {
                sessionStorage.clear();
                console.log('🗑️ sessionStorage 초기화 완료');
            } catch (e) {
                console.warn('sessionStorage 초기화 실패:', e);
            }
            
            // 5. Service Worker 등록 해제 (완전 초기화)
            if ('serviceWorker' in navigator) {
                try {
                    const registrations = await navigator.serviceWorker.getRegistrations();
                    for (const registration of registrations) {
                        await registration.unregister();
                        console.log('🗑️ Service Worker 등록 해제');
                    }
                } catch (e) {
                    console.warn('Service Worker 해제 실패:', e);
                }
            }
            
            // 6. 애니메이션 효과
            const refreshBtn = document.getElementById('refreshBtn');
            if (refreshBtn) {
                refreshBtn.style.transform = 'rotate(1080deg)';
                refreshBtn.style.transition = 'transform 1s ease-in-out';
            }
            
            // 7. 상태 메시지 표시
            showStatus('🔥 완전 초기화 중... 모든 캐시 삭제!', 'info');
            
            // 8. 타임스탬프 + Cache-Control 강제로 완전히 새로운 페이지 로드
            setTimeout(() => {
                const timestamp = new Date().getTime();
                const randomHash = Math.random().toString(36).substring(7);
                const currentUrl = window.location.href.split('?')[0].split('#')[0];
                const newUrl = `${currentUrl}?_nocache=${timestamp}&_hash=${randomHash}`;
                
                console.log('✅ 강력 새로고침 실행:', newUrl);
                
                // 완전히 새로운 페이지로 이동 (캐시 완전 무시)
                window.location.href = newUrl;
                
            }, 1000);
            
        } catch (error) {
            console.error('❌ 새로고침 중 오류:', error);
            showStatus('새로고침 중 오류가 발생했습니다', 'error');
            
            // 오류 발생 시 최후의 수단
            setTimeout(() => {
                const timestamp = new Date().getTime();
                window.location.href = `${window.location.href.split('?')[0]}?_force=${timestamp}`;
            }, 1000);
        }
    }
}

// 유틸리티 함수들
function formatDuration(seconds) {
    if (!seconds) return '';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        return '오늘';
    } else if (diffDays === 1) {
        return '어제';
    } else if (diffDays < 7) {
        return `${diffDays}일 전`;
    } else {
        return date.toLocaleDateString('ko-KR', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    }
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function escapeForJS(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
}

// ============================================================================
// 재생 목록 관리
// ============================================================================

// 재생 목록 로드
async function loadPlaylist(skipPrefetch = false) {
    try {
        console.log('📋 재생 목록 로드 시작...');
        const response = await fetch('/api/playlist');
        const data = await response.json();
        
        console.log('📋 재생 목록 응답:', data);
        
        if (data.success) {
            if (data.playlist && data.playlist.length > 0) {
                allPlaylist = data.playlist; // 전역 변수에 저장
                displayPlaylist(allPlaylist);
                
                // 🚀 첫 곡 즉시 준비 (즉시 재생 가능하게) - skipPrefetch가 false일 때만
                if (!skipPrefetch && allPlaylist.length > 0) {
                    console.log('⚡ 플레이리스트 첫 곡 즉시 준비 시작...');
                    // 첫 곡은 즉시 준비 (대기 시간 0초 목표)
                    await prefetchNextTrack(0);
                } else if (skipPrefetch) {
                    console.log('⚡ prefetch 스킵 (즐겨찾기 토글 중)');
                }
            } else {
                console.log('📋 재생 목록이 비어있습니다');
                allPlaylist = [];
                hidePlaylist();
            }
        } else {
            console.error('📋 재생 목록 로드 실패:', data.message);
            allPlaylist = [];
            hidePlaylist();
        }
    } catch (error) {
        console.error('❌ 재생 목록 로드 실패:', error);
        showStatus('재생 목록을 불러올 수 없습니다', 'error');
    }
}

// 재생 목록 표시
function displayPlaylist(playlist) {
    const playlistSection = document.getElementById('playlistSection');
    const playlistContainer = document.getElementById('playlistContainer');
    const emptySearch = document.getElementById('playlistEmptySearch');
    
    if (playlist.length === 0) {
        // 검색어가 있으면 "검색 결과 없음" 표시
        const searchInput = document.getElementById('playlistSearchInput');
        if (searchInput && searchInput.value.trim()) {
            playlistContainer.innerHTML = '';
            emptySearch.style.display = 'block';
        } else {
            hidePlaylist();
        }
        return;
    }
    
    playlistSection.style.display = 'block';
    playlistContainer.innerHTML = '';
    emptySearch.style.display = 'none';
    
    playlist.forEach((item, index) => {
        // 실제 인덱스를 찾기 위해 전체 목록에서 검색
        const realIndex = allPlaylist.findIndex(p => 
            p.url === item.url && p.title === item.title
        );
        const playlistItem = createPlaylistItem(item, realIndex >= 0 ? realIndex : index);
        playlistContainer.appendChild(playlistItem);
    });
}

// 재생 목록 숨기기
function hidePlaylist() {
    const playlistSection = document.getElementById('playlistSection');
    playlistSection.style.display = 'none';
}

// 재생 목록 항목 생성
function createPlaylistItem(item, index) {
    const div = document.createElement('div');
    div.className = 'playlist-item';
    div.setAttribute('data-video-id', item.video_id || '');
    
    const duration = formatDuration(item.duration);
    const addedDate = formatDate(item.added_at);
    
    // 공유받은 음원 표시
    const sharedFrom = item.shared_from ? `<span class="shared-badge">📤 ${escapeHtml(item.shared_from)}님이 공유</span>` : '';
    
    // 즐겨찾기 상태 확인
    const isFavorite = item.is_favorite || false;
    const favoriteClass = isFavorite ? 'favorited' : '';
    const favoriteIcon = isFavorite ? '⭐' : '☆';  // 채워진 별 vs 빈 별
    
    // 디버깅: 즐겨찾기 상태 로그
    if (isFavorite) {
        console.log(`⭐ 즐겨찾기 항목 렌더링: "${item.title}" (video_id: ${item.video_id})`);
    }
    
    div.innerHTML = `
        <div class="playlist-item-content">
            <div class="playlist-thumbnail">
                ${item.thumbnail 
                    ? `<img src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.title)}">`
                    : '<div class="no-thumbnail">🎵</div>'
                }
            </div>
            <div class="playlist-info">
                <div class="playlist-title">${escapeHtml(item.title)}</div>
                <div class="playlist-meta">
                    <span>${duration ? duration + ' • ' : ''}</span>
                    <span style="color: #aaa; font-size: 9px;">${addedDate}</span>
                    ${sharedFrom ? ' ' + sharedFrom : ''}
                </div>
            </div>
        </div>
        <div class="playlist-item-actions">
            <button class="favorite-btn ${favoriteClass}" title="${isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}">
                ${favoriteIcon}
            </button>
            <button class="playlist-btn share-playlist-btn" title="공유">
                📤
            </button>
            <button class="playlist-btn delete-playlist-btn" title="삭제">
                🗑️
            </button>
        </div>
    `;
    
    // 썸네일과 제목 클릭 시 재생 (인덱스 전달)
    const playlistContent = div.querySelector('.playlist-item-content');
    playlistContent.addEventListener('click', () => playFromPlaylist(item.url, index));
    
    // 즐겨찾기 버튼 클릭
    const favoriteBtn = div.querySelector('.favorite-btn');
    favoriteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await toggleFavorite(item);
    });
    
    // 공유 버튼 클릭 (재생 목록 = 음원)
    const shareBtn = div.querySelector('.share-playlist-btn');
    shareBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openShareModal(item, 'audio');  // 재생 목록은 항상 음원
    });
    
    // 삭제 버튼 클릭
    const deleteBtn = div.querySelector('.delete-playlist-btn');
    deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        await deleteFromPlaylist(index, item.title, item.url, item.shared_from);
    });
    
    return div;
}

// 재생 목록에 추가
async function addToPlaylist(url, title, thumbnail, duration) {
    try {
        const response = await fetch('/api/playlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                title: title,
                thumbnail: thumbnail,
                duration: duration
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            loadPlaylist(); // 재생 목록 새로고침
        }
        // 이미 목록에 있어도 에러 표시 안 함
    } catch (error) {
        console.error('재생 목록 추가 실패:', error);
    }
}

// prefetch된 데이터로 즉시 오디오 재생
async function playAudioWithData(data) {
    // prefetch된 데이터는 이미 준비되어 있으므로 로딩 화면 없음
    console.log('⚡ prefetch 데이터로 즉시 재생 (로딩 화면 없음)');
    
    const playerSection = document.getElementById('audioPlayer');
    const playerTitle = document.getElementById('playerTitle');
    const playerSubtitle = document.getElementById('playerSubtitle');
    const audioEl = document.getElementById('audioElement');
    
    // 이전 오디오 정리
    audioEl.pause();
    audioEl.src = '';
    
    // Safari 감지
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const isMobile = isMobileDevice();
    
    // 📱 모바일 Safari 고속 로딩 최적화
    if (isMobile) {
        audioEl.setAttribute('webkit-playsinline', 'true');
        audioEl.setAttribute('playsinline', 'true');
    }
    
    // 🚀 Safari/iOS: metadata만 로드 (duration 버그 수정 유지!)
    if (isSafari || isIOS) {
        audioEl.preload = 'metadata';  // metadata만 로드 (빠름!)
    } else {
        audioEl.preload = 'auto';  // 안드로이드: 자동 프리로드
    }
    
    // 🚀 항상 서버 URL 사용 (서버가 YouTube보다 빠름!)
    let audioUrl = data.audio_url;
    let useYouTubeCDN = false;
    
    console.log('🎵 서버 스트리밍 사용 (로컬 파일 또는 YouTube 중계)');
    
    console.log(`🎵 오디오 설정 시작 (prefetch):`, {
        safari: isSafari,
        ios: isIOS,
        mobile: isMobile,
        useYouTubeCDN: useYouTubeCDN,
        audioUrl: audioUrl,
        title: data.title
    });
    
    // 오디오 소스 설정
    audioEl.src = audioUrl;
    playerTitle.textContent = data.title;
    playerSubtitle.textContent = `${formatDuration(data.duration)} • YouTube`;
    
    // video_id 저장
    currentVideoId = data.video_id;
    
    playerSection.style.display = 'block';
    
    // 🚀 즉시 재생 (모든 브라우저 동일!)
    const playPromise = audioEl.play();
    if (playPromise !== undefined) {
        playPromise.then(() => {
            console.log('✅ 오디오 재생 성공 (prefetch)');
            
            // 🎬 로딩 팝업 숨기기
            hideLoadingPopup();
            
            if (data.from_cache) {
                showStatus('⚡ 캐시에서 즉시 재생! (초고속)', 'success');
            } else if (data.local_file) {
                showStatus('⚡ 로컬 파일 재생! (고속 탐색 가능)', 'success');
            } else if (data.instant_play) {
                showStatus('⚡ prefetch로 즉시 재생! (대기 시간 0초)', 'success');
            } else {
                showStatus('🎵 재생 시작!', 'success');
            }
        }).catch(err => {
            console.error('❌ 재생 실패:', err);
            
            // 🎬 로딩 팝업 숨기기
            hideLoadingPopup();
            
            if (isSafari || isIOS) {
                showStatus('🍎 Safari: 플레이어의 재생 버튼을 눌러주세요', 'info');
            } else {
                showStatus('재생 오류: ' + err.message, 'error');
            }
        });
    }
    
    // 다운로드 체크 시작 (downloading 플래그가 있으면)
    if (data.downloading && data.video_id) {
        startDownloadCheck(data.video_id);
    }
    
    updateMediaSession(data.title, data.thumbnail);
}

// 재생 목록에서 재생
// 다음 곡 미리 준비 (백그라운드에서 URL 미리 가져오기)
async function prefetchNextTrack(index) {
    try {
        // 🚗 테슬라 모드에서는 prefetch 하지 않음 (실시간 스트리밍)
        if (isStreamingMode) {
            console.log('🚗 테슬라 모드: prefetch 비활성화 (실시간 스트리밍)');
            nextTrackPrefetch = null;
            return;
        }
        
        if (index < 0 || index >= allPlaylist.length) {
            console.log('⏭️ 다음 곡 없음 (플레이리스트 끝)');
            nextTrackPrefetch = null;
            return;
        }
        
        const nextTrack = allPlaylist[index];
        console.log(`🔄 다음 곡 미리 준비 시작: ${nextTrack.title}`);
        
        const isMobile = isMobileDevice();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8초 타임아웃 (빠른 포기)
        
        const response = await fetch('/api/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                url: nextTrack.url,
                is_mobile: isMobile
            }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        const data = await response.json();
        
        if (data.success) {
            nextTrackPrefetch = {
                index: index,
                url: nextTrack.url,
                data: data
            };
            console.log(`✅ 다음 곡 준비 완료: ${nextTrack.title} (즉시 재생 가능!)`);
        } else {
            nextTrackPrefetch = null;
            console.log(`❌ 다음 곡 준비 실패: ${data.message}`);
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('⏱️ 다음 곡 준비 타임아웃');
        } else {
            console.error('❌ 다음 곡 준비 오류:', error);
        }
        nextTrackPrefetch = null;
    }
}

async function playFromPlaylist(url, index) {
    // 현재 인덱스 저장
    currentPlaylistIndex = index;
    
    // 🚗 테슬라 모드에서는 prefetch 데이터 무시하고 서버 API 호출
    if (isStreamingMode) {
        console.log('🚗 테슬라 모드: 플레이리스트에서 서버 API 호출 (캐시 우회)');
        
        // URL 입력란에 설정하고 streamAudio 호출
        const urlInput = document.getElementById('videoUrl');
        if (urlInput) {
            urlInput.value = url;
        }
        
        // streamAudio 함수 호출 (이미 테슬라 모드 로직 포함됨)
        await streamAudio();
        
        return;
    }
    
    // 🚀 항상 서버에서 최신 데이터 가져오기 (prefetch 비활성화)
    // prefetch는 YouTube URL이 만료될 수 있어서 사용 안 함!
    nextTrackPrefetch = null; // prefetch 무시
    
    console.log('🚀 서버에서 최신 스트리밍 데이터 가져오는 중...');
    
    // 일반 재생 (서버에서 항상 최신 로컬 파일 또는 YouTube URL 받기)
    document.getElementById('videoUrl').value = url;
    await streamAudio();
    
    // prefetch 비활성화 (YouTube URL 만료 문제로 인해)
    // if (index + 1 < allPlaylist.length) {
    //     prefetchNextTrack(index + 1);
    // }
}

// 재생 목록에서 삭제
async function toggleFavorite(item) {
    try {
        // video_id가 없으면 URL에서 추출 시도
        if (!item.video_id && item.url) {
            const match = item.url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
            if (match) {
                item.video_id = match[1];
            }
        }
        
        // video_id가 여전히 없으면 오류
        if (!item.video_id) {
            showStatus('이 음원은 즐겨찾기에 추가할 수 없습니다 (video_id 없음)', 'error');
            console.error('video_id가 없는 항목:', item);
            return;
        }
        
        const response = await fetch('/api/toggle-favorite', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_id: item.video_id,
                title: item.title,
                url: item.url
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ 즐겨찾기 토글 성공:', result);
            console.log('즐겨찾기 상태:', result.is_favorite ? '⭐ 추가됨' : '☆ 제거됨');
            
            // 즐겨찾기 상태 업데이트
            item.is_favorite = result.is_favorite;
            
            // 전역 재생 목록에서 해당 항목 찾아서 업데이트
            const playlistItem = allPlaylist.find(p => p.video_id === item.video_id);
            if (playlistItem) {
                playlistItem.is_favorite = result.is_favorite;
            }
            
            // 즐겨찾기 우선 정렬 (클라이언트에서 즉시)
            allPlaylist.sort((a, b) => {
                // 즐겨찾기 우선
                if (a.is_favorite !== b.is_favorite) {
                    return b.is_favorite ? 1 : -1;
                }
                // 제목 순
                return (a.title || '').localeCompare(b.title || '');
            });
            
            // UI 즉시 업데이트 (서버 요청 없이)
            displayPlaylist(allPlaylist);
            
            console.log('⚡ 즐겨찾기 토글 완료 (즉시 정렬, 서버 요청 없음)');
            
            // 상태 메시지
            const icon = result.is_favorite ? '⭐' : '☆';
            showStatus(`${icon} ${result.message}`, 'success');
        } else {
            console.error('❌ 즐겨찾기 실패:', result);
            showStatus(result.message, 'error');
        }
    } catch (error) {
        console.error('즐겨찾기 토글 실패:', error);
        showStatus('즐겨찾기 처리 중 오류가 발생했습니다', 'error');
    }
}

async function deleteFromPlaylist(index, title, url, sharedFrom) {
    // 공유받은 음원인지 확인
    const isShared = sharedFrom ? true : false;
    
    let confirmMessage;
    if (isShared) {
        confirmMessage = `"${title}"\n\n📤 ${sharedFrom}님이 공유한 음원입니다.\n재생 목록에서 제거하시겠습니까?\n\n✅ 캐시 파일은 유지됩니다 (공유자의 파일 보호)`;
    } else {
        confirmMessage = `"${title}"\n\n🎵 본인이 추가한 음원을 삭제하시겠습니까?\n\n⚠️ 캐시 파일도 함께 영구 삭제됩니다!`;
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/playlist/${index}`, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.cache_deleted) {
                showStatus(`${data.message} (캐시 ${data.cache_size || '0'}MB 삭제됨)`, 'success');
            } else {
                showStatus(data.message, 'success');
            }
            loadPlaylist(); // 재생 목록 새로고침
        } else {
            alert(data.message || '삭제에 실패했습니다');
        }
    } catch (error) {
        console.error('재생 목록 삭제 실패:', error);
        alert('삭제 중 오류가 발생했습니다: ' + error.message);
    }
}

// 재생 목록 전체 삭제
async function clearAllPlaylist() {
    if (!confirm('재생 목록을 모두 삭제하시겠습니까?\n\n⚠️ 본인이 추가한 음원의 캐시 파일도 함께 영구 삭제됩니다!\n✅ 공유받은 음원의 캐시는 유지됩니다 (공유자의 파일 보호)')) {
        return;
    }
    
    try {
        const response = await fetch('/api/playlist/clear', {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.cache_deleted_count > 0) {
                showStatus(`${data.message} (캐시 ${data.cache_deleted_count}개, ${data.total_cache_size || '0'}MB 삭제됨)`, 'success');
            } else {
                showStatus(data.message, 'success');
            }
            allPlaylist = [];
            hidePlaylist(); // 재생 목록 숨기기
        } else {
            alert(data.message || '삭제에 실패했습니다');
        }
    } catch (error) {
        console.error('재생 목록 전체 삭제 실패:', error);
        alert('삭제 중 오류가 발생했습니다: ' + error.message);
    }
}

// 재생 목록 검색
function searchPlaylist() {
    const searchInput = document.getElementById('playlistSearchInput');
    const searchTerm = searchInput.value.toLowerCase().trim();
    
    if (searchTerm === '') {
        displayPlaylist(allPlaylist);
        return;
    }
    
    const filteredPlaylist = allPlaylist.filter(item => {
        const title = item.title.toLowerCase();
        return title.includes(searchTerm);
    });
    
    displayPlaylist(filteredPlaylist);
}

// ============================================================================
// 유튜브 검색 기능
// ============================================================================

// 유튜브 검색
async function searchYoutube() {
    const query = document.getElementById('videoUrl').value.trim();
    const searchBtn = document.getElementById('searchBtn');
    
    if (!query) {
        showStatus('검색어를 입력해주세요', 'error');
        return;
    }
    
    searchBtn.disabled = true;
    searchBtn.textContent = '⏳ 검색중';
    showStatus('유튜브 검색 중...', 'info');
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                query: query,
                max_results: 50  // 50개 가져오기
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            allSearchResults = data.results;
            displayedSearchCount = 20;
            displaySearchResults(allSearchResults.slice(0, 20));
            showStatus(`${data.count}개의 검색 결과를 찾았습니다`, 'success');
        } else {
            showStatus(data.message, 'error');
        }
    } catch (error) {
        showStatus('검색 실패: ' + error.message, 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = '🔍 검색';
    }
}

// 검색 결과 표시
function displaySearchResults(results) {
    const section = document.getElementById('searchResultsSection');
    const container = document.getElementById('searchResultsContainer');
    
    container.innerHTML = '';
    
    if (results.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999; padding: 40px;">검색 결과가 없습니다</p>';
        section.style.display = 'block';
        return;
    }
    
    results.forEach(result => {
        const item = createSearchResultItem(result);
        container.appendChild(item);
    });
    
    // "더 보기" 버튼 추가 (남은 결과가 있으면)
    if (displayedSearchCount < allSearchResults.length) {
        const loadMoreBtn = document.createElement('button');
        loadMoreBtn.className = 'load-more-btn';
        loadMoreBtn.textContent = `📄 더 보기 (${allSearchResults.length - displayedSearchCount}개 남음)`;
        loadMoreBtn.onclick = loadMoreSearchResults;
        container.appendChild(loadMoreBtn);
    }
    
    section.style.display = 'block';
    
    // 검색 결과로 스크롤
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 더 많은 검색 결과 로드
function loadMoreSearchResults() {
    const container = document.getElementById('searchResultsContainer');
    
    // 현재까지 표시된 것 제거 (더 보기 버튼 포함)
    const loadMoreBtn = container.querySelector('.load-more-btn');
    if (loadMoreBtn) {
        loadMoreBtn.remove();
    }
    
    // 다음 20개 추가
    const nextBatch = allSearchResults.slice(displayedSearchCount, displayedSearchCount + 20);
    nextBatch.forEach(result => {
        const item = createSearchResultItem(result);
        container.appendChild(item);
    });
    
    displayedSearchCount += nextBatch.length;
    
    // 더 남았으면 "더 보기" 버튼 다시 추가
    if (displayedSearchCount < allSearchResults.length) {
        const newLoadMoreBtn = document.createElement('button');
        newLoadMoreBtn.className = 'load-more-btn';
        newLoadMoreBtn.textContent = `📄 더 보기 (${allSearchResults.length - displayedSearchCount}개 남음)`;
        newLoadMoreBtn.onclick = loadMoreSearchResults;
        container.appendChild(newLoadMoreBtn);
    }
}

// 검색 결과 아이템 생성
function createSearchResultItem(result) {
    const div = document.createElement('div');
    div.className = 'search-result-item';
    
    const duration = formatDuration(result.duration);
    const views = formatViews(result.view_count);
    
    // 썸네일 HTML 생성
    let thumbnailHTML = '';
    if (result.thumbnail) {
        thumbnailHTML = `
            <img src="${escapeHtml(result.thumbnail)}" 
                 alt="${escapeHtml(result.title)}"
                 onerror="this.onerror=null; this.src='https://i.ytimg.com/vi/${result.id}/mqdefault.jpg'; if(this.complete && this.naturalHeight===0) this.parentElement.innerHTML='<div class=\\'thumbnail-placeholder\\'>📹</div>';"
                 loading="lazy">
        `;
    } else {
        thumbnailHTML = '<div class="thumbnail-placeholder">📹</div>';
    }
    
    div.innerHTML = `
        <div class="search-result-thumbnail">
            ${thumbnailHTML}
            ${duration ? `<div class="search-result-duration">${duration}</div>` : ''}
        </div>
        <div class="search-result-info">
            <div class="search-result-title">${escapeHtml(result.title)}</div>
            <div class="search-result-channel">${escapeHtml(result.channel)}</div>
            ${views ? `<div class="search-result-views">조회수 ${views}</div>` : ''}
        </div>
        <div class="search-result-actions">
            <button class="search-action-btn play-audio-btn" title="음악으로 재생">
                🎵 재생
            </button>
            <button class="search-action-btn watch-video-btn" title="영상으로 보기">
                ▶️ 보기
            </button>
            <button class="search-action-btn share-search-btn" title="공유하기">
                📤 공유
            </button>
        </div>
    `;
    
    // 음악 재생 버튼
    const playAudioBtn = div.querySelector('.play-audio-btn');
    playAudioBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
            await addToPlaylist(result.url, result.title, result.thumbnail, result.duration);
            document.getElementById('videoUrl').value = result.url;
            await streamAudio();
            // closeSearchResults() 제거 - 검색 결과 유지!
            showStatus(`"${result.title}" 음악 재생 중`, 'success');
        } catch (error) {
            showStatus('재생 실패: ' + error.message, 'error');
        }
    });
    
    // 영상 보기 버튼
    const watchVideoBtn = div.querySelector('.watch-video-btn');
    watchVideoBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
            // closeSearchResults() 제거 - 검색 결과 유지!
            await watchVideoFromSearch(result.url, result.title);
        } catch (error) {
            showStatus('영상 재생 실패: ' + error.message, 'error');
        }
    });
    
    // 공유 버튼
    const shareSearchBtn = div.querySelector('.share-search-btn');
    shareSearchBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
            // 먼저 재생 목록에 추가
            await addToPlaylist(result.url, result.title, result.thumbnail, result.duration);
            
            // 공유 모달 열기
            const shareItem = {
                title: result.title,
                thumbnail: result.thumbnail,
                duration: result.duration,
                url: result.url,
                video_id: result.id
            };
            // 검색 결과는 기본적으로 음원으로 공유 (사용자가 음악 듣는 용도)
            openShareModal(shareItem, 'audio');
        } catch (error) {
            showStatus('공유 실패: ' + error.message, 'error');
        }
    });
    
    // 카드 클릭 시 음악 재생 (기본 동작)
    div.addEventListener('click', async () => {
        try {
            await addToPlaylist(result.url, result.title, result.thumbnail, result.duration);
            document.getElementById('videoUrl').value = result.url;
            await streamAudio();
            // closeSearchResults() 제거 - 검색 결과 유지!
            showStatus(`"${result.title}" 음악 재생 중`, 'success');
        } catch (error) {
            showStatus('재생 실패: ' + error.message, 'error');
        }
    });
    
    return div;
}

// 검색 결과 닫기
function closeSearchResults() {
    const section = document.getElementById('searchResultsSection');
    section.style.display = 'none';
}

// 조회수 포맷
function formatViews(count) {
    if (!count) return '';
    
    if (count >= 100000000) {
        return `${(count / 100000000).toFixed(1)}억회`;
    } else if (count >= 10000) {
        return `${(count / 10000).toFixed(1)}만회`;
    } else if (count >= 1000) {
        return `${(count / 1000).toFixed(1)}천회`;
    }
    return `${count}회`;
}

// ============================================================================
// 검색 결과에서 영상 보기
// ============================================================================

// 검색 결과에서 영상 재생
async function watchVideoFromSearch(url, title) {
    try {
        // ⚡ 로딩 팝업을 즉시 표시 (지연 시간 제거)
        showLoadingPopup('📹 영상 준비 중...', '잠시만 기다려주세요', true);
        
        showStatus('영상을 불러오는 중...', 'info');
        
        // 직접 URL 방식
        const response = await fetch('/api/video-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // 로딩 팝업 숨기기
            hideLoadingPopup();
            // 포맷 지원 안함 에러 처리
            if (data.error_type === 'format_not_available') {
                showStatus(`❌ ${data.message}`, 'error');
                return;
            }
            showStatus(data.message, 'error');
            return;
        }
        
        if (data.success) {
            // 로딩 팝업 숨기기 (성공 시)
            hideLoadingPopup();
            openWatchModal(data);
            showStatus('영상 재생 시작! 광고 없이 재생됩니다 🎬', 'success');
        }
    } catch (error) {
        hideLoadingPopup();
        showStatus('영상 로드 실패: ' + error.message, 'error');
    }
}

// 바로보기 모달 열기
function openWatchModal(data) {
    const modal = document.getElementById('watchModal');
    const video = document.getElementById('watchVideo');
    const source = document.getElementById('watchVideoSource');
    const title = document.getElementById('watchTitle');
    const info = document.getElementById('watchInfo');
    
    // 직접 URL 사용
    source.src = data.video_url;
    video.load();
    
    title.textContent = data.title;
    const duration = formatDuration(data.duration);
    info.textContent = `⚡ 재생 중 | 광고 없음 | ${duration}`;
    
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

// 바로보기 모달 닫기
function closeWatchModal() {
    const modal = document.getElementById('watchModal');
    const video = document.getElementById('watchVideo');
    
    modal.style.display = 'none';
    video.pause();
    document.body.style.overflow = 'auto';
}

// ============================================================================
// 음원 공유 기능
// ============================================================================

let currentShareItem = null;
let currentShareType = 'audio'; // 'audio' 또는 'video'

// 공유 모달 열기
async function openShareModal(item, shareType = 'audio') {
    console.log('🎬 공유 모달 열기:', item, 'type:', shareType);
    
    currentShareItem = item;
    currentShareType = shareType;  // 'audio' 또는 'video'
    
    const modal = document.getElementById('shareModal');
    const shareModalTitle = document.getElementById('shareModalTitle');
    const shareThumbnail = document.getElementById('shareThumbnail');
    const shareTitle = document.getElementById('shareTitle');
    const shareUsersList = document.getElementById('shareUsersList');
    const selectAllCheckbox = document.getElementById('selectAllUsers');
    
    if (!modal) {
        console.error('❌ 공유 모달을 찾을 수 없습니다!');
        showStatus('공유 모달을 찾을 수 없습니다', 'error');
        return;
    }
    
    // 모달 제목 변경
    if (shareModalTitle) {
        shareModalTitle.textContent = shareType === 'video' ? '📹 영상 공유하기' : '🎵 음원 공유하기';
    }
    
    // 전체 선택 체크박스 초기화
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
    }
    
    // 썸네일 및 제목 설정
    if (item.thumbnail) {
        shareThumbnail.innerHTML = `<img src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.title)}">`;
    } else {
        shareThumbnail.innerHTML = shareType === 'video' ? '<div class="no-thumbnail">📹</div>' : '<div class="no-thumbnail">🎵</div>';
    }
    shareTitle.textContent = item.title;
    
    console.log('📋 공유 모달 설정 완료:', {
        title: item.title,
        video_id: item.video_id,
        url: item.url,
        type: shareType
    });
    
    // 사용자 목록 로딩
    shareUsersList.innerHTML = '<div class="loading-users">사용자 목록을 불러오는 중...</div>';
    
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // 사용자 목록 가져오기
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        
        if (data.success && data.users.length > 0) {
            shareUsersList.innerHTML = '';
            data.users.forEach(username => {
                const userItem = document.createElement('div');
                userItem.className = 'share-user-item';
                
                userItem.innerHTML = `
                    <input type="checkbox" class="share-user-checkbox" data-username="${escapeHtml(username)}">
                    <span class="share-user-name">${escapeHtml(username)}</span>
                `;
                
                shareUsersList.appendChild(userItem);
                
                // 이벤트 핸들러 등록 (DOM에 추가된 후)
                const checkbox = userItem.querySelector('.share-user-checkbox');
                const nameSpan = userItem.querySelector('.share-user-name');
                
                // 체크박스 직접 클릭
                checkbox.addEventListener('change', (e) => {
                    if (checkbox.checked) {
                        userItem.classList.add('selected');
                    } else {
                        userItem.classList.remove('selected');
                    }
                    updateSelectAllCheckbox();
                });
                
                // 이름 클릭 시 체크박스 토글
                nameSpan.addEventListener('click', () => {
                    checkbox.checked = !checkbox.checked;
                    if (checkbox.checked) {
                        userItem.classList.add('selected');
                    } else {
                        userItem.classList.remove('selected');
                    }
                    updateSelectAllCheckbox();
                });
                
                // 아이템 배경 클릭 시 체크박스 토글
                userItem.addEventListener('click', (e) => {
                    // 체크박스나 이름을 직접 클릭한 경우는 제외
                    if (e.target === checkbox || e.target === nameSpan) {
                        return;
                    }
                    checkbox.checked = !checkbox.checked;
                    if (checkbox.checked) {
                        userItem.classList.add('selected');
                    } else {
                        userItem.classList.remove('selected');
                    }
                    updateSelectAllCheckbox();
                });
            });
        } else {
            shareUsersList.innerHTML = '<div class="loading-users">다른 사용자가 없습니다</div>';
        }
    } catch (error) {
        console.error('사용자 목록 로드 실패:', error);
        shareUsersList.innerHTML = '<div class="loading-users">사용자 목록을 불러올 수 없습니다</div>';
    }
}

// 전체 선택/해제
function toggleSelectAll(checkbox) {
    const shareUsersList = document.getElementById('shareUsersList');
    const allCheckboxes = shareUsersList.querySelectorAll('.share-user-checkbox');
    const allItems = shareUsersList.querySelectorAll('.share-user-item');
    
    allCheckboxes.forEach((cb, index) => {
        cb.checked = checkbox.checked;
        if (checkbox.checked) {
            allItems[index].classList.add('selected');
        } else {
            allItems[index].classList.remove('selected');
        }
    });
}

// 사용자 선택 토글 (이제 사용하지 않지만 호환성을 위해 유지)
function toggleUserSelection(userItem) {
    const checkbox = userItem.querySelector('.share-user-checkbox');
    checkbox.checked = !checkbox.checked;
    
    if (checkbox.checked) {
        userItem.classList.add('selected');
    } else {
        userItem.classList.remove('selected');
    }
    
    // 전체 선택 체크박스 상태 업데이트
    updateSelectAllCheckbox();
}

// 전체 선택 체크박스 상태 업데이트
function updateSelectAllCheckbox() {
    const shareUsersList = document.getElementById('shareUsersList');
    const selectAllCheckbox = document.getElementById('selectAllUsers');
    const allCheckboxes = shareUsersList.querySelectorAll('.share-user-checkbox');
    const checkedCheckboxes = shareUsersList.querySelectorAll('.share-user-checkbox:checked');
    
    if (allCheckboxes.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCheckboxes.length === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCheckboxes.length === allCheckboxes.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    }
}

// 공유 실행
async function confirmShare() {
    const shareUsersList = document.getElementById('shareUsersList');
    const selectedCheckboxes = shareUsersList.querySelectorAll('.share-user-checkbox:checked');
    
    if (selectedCheckboxes.length === 0) {
        showStatus('공유받을 사용자를 선택해주세요', 'error');
        return;
    }
    
    const selectedUsernames = Array.from(selectedCheckboxes).map(cb => cb.dataset.username);
    
    console.log('📤 공유 실행:', {
        item: currentShareItem,
        users: selectedUsernames
    });
    
    // 버튼 비활성화
    const confirmBtn = document.querySelector('.share-confirm-btn');
    confirmBtn.disabled = true;
    confirmBtn.textContent = '공유 중...';
    
    try {
        // video_id 추출 (여러 패턴 시도)
        let videoId = currentShareItem.video_id;
        if (!videoId && currentShareItem.url) {
            const match = currentShareItem.url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|shorts\/)([a-zA-Z0-9_-]{11})/);
            if (match) videoId = match[1];
        }
        
        console.log('🔍 최종 video_id:', videoId);
        console.log('📋 공유 데이터:', {
            video_id: videoId,
            title: currentShareItem.title,
            thumbnail: currentShareItem.thumbnail,
            duration: currentShareItem.duration,
            to_usernames: selectedUsernames
        });
        
        if (!videoId) {
            showStatus('⚠️ video_id를 찾을 수 없습니다. 유튜브 영상만 공유 가능합니다.', 'error');
            confirmBtn.disabled = false;
            confirmBtn.textContent = '📤 공유하기';
            return;
        }
        
        const response = await fetch('/api/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_id: videoId,
                title: currentShareItem.title,
                thumbnail: currentShareItem.thumbnail,
                duration: currentShareItem.duration,
                to_usernames: selectedUsernames,
                content_type: currentShareType,  // 'audio' 또는 'video'
                filename: currentShareItem.filename  // 실제 파일명 (영상 공유 시)
            })
        });
        
        const data = await response.json();
        
        console.log('📬 서버 응답:', data);
        
        if (data.success) {
            // 공유 완료 팝업 표시 (1초간)
            showShareSuccessPopup();
            closeShareModal();
            showStatus(data.message, 'success');
        } else {
            showStatus(data.message || '공유에 실패했습니다', 'error');
        }
    } catch (error) {
        console.error('❌ 공유 오류:', error);
        showStatus('공유 중 오류가 발생했습니다: ' + error.message, 'error');
    } finally {
        // 버튼 활성화
        confirmBtn.disabled = false;
        confirmBtn.textContent = '📤 공유하기';
    }
}

// 공유 모달 닫기
function closeShareModal() {
    const modal = document.getElementById('shareModal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
    currentShareItem = null;
}

// 공유 완료 팝업 표시 (1초간)
function showShareSuccessPopup() {
    const popup = document.getElementById('shareSuccessPopup');
    popup.style.display = 'block';
    
    setTimeout(() => {
        popup.style.display = 'none';
    }, 1000);
}


