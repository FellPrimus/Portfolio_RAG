// ===================================================================
// 크롤링 모듈
// 네이버 클라우드 및 범용 URL 크롤링 기능
// ===================================================================

import { showErrorMessage } from '../../utils.js';

/**
 * 벡터DB 문서 로드 콜백
 * @type {Function|null}
 */
let onDocumentsLoadCallback = null;

/**
 * 전체 크롤링 상태
 * @type {boolean}
 */
let isFullCrawlRunning = false;

/**
 * 문서 로드 콜백 설정
 * @param {Function} callback - 문서 로드 시 호출될 콜백
 */
export function setCrawlDocumentsLoadCallback(callback) {
    onDocumentsLoadCallback = callback;
}

/**
 * 로그 추가 헬퍼 함수 생성
 * @param {HTMLElement} logContent - 로그 컨테이너 요소
 * @returns {Function} 로그 추가 함수
 */
function createLogAdder(logContent) {
    return function addLog(message, type = 'info') {
        if (logContent) {
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry log-${type}`;
            logEntry.textContent = message;
            logContent.appendChild(logEntry);
            logContent.scrollTop = logContent.scrollHeight;
        }
    };
}

/**
 * 로그 메시지 타입 결정
 * @param {string} message - 로그 메시지
 * @returns {string} 로그 타입
 */
function determineLogType(message) {
    if (message.includes('✅') || message.includes('성공')) {
        return 'success';
    } else if (message.includes('❌') || message.includes('실패') || message.includes('타임아웃')) {
        return 'error';
    } else if (message.includes('⚠️') || message.includes('경고')) {
        return 'info';
    } else if (message.includes('[크롤링') || message.includes('[정보]')) {
        return 'status';
    }
    return 'progress';
}

/**
 * 스트리밍 응답 처리
 * @param {Response} response - fetch 응답
 * @param {Object} handlers - 이벤트 핸들러들
 */
async function processStreamResponse(response, handlers) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.substring(6));

                switch (data.type) {
                    case 'status':
                        handlers.onStatus?.(data);
                        break;
                    case 'progress':
                        handlers.onProgress?.(data);
                        break;
                    case 'complete':
                        await handlers.onComplete?.(data);
                        break;
                    case 'error':
                        handlers.onError?.(data);
                        break;
                }
            }
        }
    }
}

/**
 * 범용 URL 크롤링
 */
export async function startGenericCrawling() {
    const urlInput = document.getElementById('generic-crawl-url-input');
    const headlessCheckbox = document.getElementById('generic-crawl-headless-checkbox');
    const crawlStatus = document.getElementById('generic-crawl-status');
    const crawlStatusText = document.getElementById('generic-crawl-status-text');
    const genericCategorySelect = document.getElementById('generic-category-select');
    const crawlBtn = document.getElementById('generic-crawl-btn');

    const url = urlInput.value.trim();

    if (!url) {
        showErrorMessage(
            'URL을 입력해주세요',
            '크롤링할 웹 페이지의 URL이 입력되지 않았습니다.',
            '📝 예시: https://guide.ncloud-docs.com/docs/...'
        );
        return;
    }

    try {
        new URL(url);
    } catch (e) {
        showErrorMessage(
            '잘못된 URL 형식',
            `입력된 URL이 올바른 형식이 아닙니다: ${url}`,
            '올바른 URL 형식:\n• https://example.com\n• http://example.com/path\n\n프로토콜(http:// 또는 https://)을 포함해주세요.'
        );
        return;
    }

    const headless = headlessCheckbox.checked;
    const selectedCategory = genericCategorySelect ? genericCategorySelect.value : 'general';

    // 상태 표시 및 버튼 비활성화
    crawlStatus.style.display = 'block';
    crawlStatusText.innerHTML = '⏳ 크롤링 준비 중...';
    crawlBtn.disabled = true;
    crawlBtn.innerHTML = '<span>⏳</span> 크롤링 중...';

    // 진행 로그 표시
    const progressLog = document.getElementById('generic-crawl-progress-log');
    const logContent = document.getElementById('generic-crawl-log-content');
    if (progressLog && logContent) {
        progressLog.style.display = 'block';
        logContent.innerHTML = '';
    }

    const addLog = createLogAdder(logContent);

    try {
        const requestBody = {
            url: url,
            headless: headless,
            category_id: selectedCategory,
            crawler_type: 'generic'
        };

        const response = await fetch('api/crawl/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error('크롤링 요청 실패');
        }

        await processStreamResponse(response, {
            onStatus: (data) => {
                crawlStatusText.innerHTML = `📊 ${data.message}`;
                addLog(data.message, 'status');
            },
            onProgress: (data) => {
                const logType = determineLogType(data.message);
                crawlStatusText.innerHTML = `🔄 크롤링 중...`;
                addLog(data.message, logType);
            },
            onComplete: async (data) => {
                crawlStatusText.innerHTML = `✅ 크롤링 완료: ${data.documents_count}개 문서, ${data.chunks_count}개 청크`;
                addLog(`✅ 완료: ${data.documents_count}개 문서, ${data.chunks_count}개 청크`, 'success');

                alert(`크롤링 성공!\n\n페이지 제목: ${data.title || 'N/A'}\n문서: ${data.documents_count}개\n청크: ${data.chunks_count}개`);

                if (onDocumentsLoadCallback) {
                    await onDocumentsLoadCallback();
                }

                urlInput.value = '';

                setTimeout(() => {
                    crawlStatus.style.display = 'none';
                    if (progressLog) progressLog.style.display = 'none';
                    crawlBtn.disabled = false;
                    crawlBtn.innerHTML = '<span>🕷️</span> 크롤링 시작';
                }, 5000);
            },
            onError: (data) => {
                crawlStatusText.innerHTML = `❌ 오류: ${data.message}`;
                addLog(`❌ ${data.message}`, 'error');

                showErrorMessage(
                    '크롤링 실패',
                    `웹 페이지 크롤링 중 오류가 발생했습니다: ${data.message}`,
                    '가능한 원인:\n• 웹 페이지 접근 권한 없음 (403/404 오류)\n• 네트워크 연결 문제\n• 웹 페이지 구조가 변경됨\n\nURL을 확인하거나 다른 페이지로 시도해주세요.'
                );

                crawlBtn.disabled = false;
                crawlBtn.innerHTML = '<span>🕷️</span> 크롤링 시작';
            }
        });
    } catch (error) {
        crawlStatusText.innerHTML = `❌ 오류: ${error.message}`;

        showErrorMessage(
            '크롤링 처리 중 오류 발생',
            `크롤링 요청을 처리하는 중 예상치 못한 오류가 발생했습니다: ${error.message}`,
            '가능한 해결 방법:\n• 서버가 실행 중인지 확인\n• 페이지를 새로고침 후 다시 시도\n• 브라우저 콘솔에서 자세한 오류 확인',
            [
                { text: '페이지 새로고침', action: () => location.reload() },
                { text: '다시 시도', action: () => startGenericCrawling() }
            ]
        );

        crawlBtn.disabled = false;
        crawlBtn.innerHTML = '<span>🕷️</span> 크롤링 시작';
    }
}

// ===================================================================
// 전체 가이드 크롤링
// ===================================================================

/**
 * 카테고리 목록 로드 및 체크박스 생성
 * 선택된 Zone에 맞는 카테고리를 조회합니다.
 */
export async function loadCrawlCategories() {
    const categoriesContainer = document.getElementById('full-crawl-categories');
    if (!categoriesContainer) return;

    // 선택된 Zone과 문서 유형 확인
    const selectedZone = getSelectedZone();
    const selectedDocTypes = getSelectedDocTypes();
    // 첫 번째 선택된 문서 유형으로 카테고리 로드 (사용자 가이드와 API 가이드 카테고리가 유사하므로)
    const docType = selectedDocTypes[0] || 'user_guide';

    try {
        // Zone 및 doc_type 파라미터와 함께 API 호출
        const response = await fetch(`/api/crawl/categories?zone=${selectedZone}&doc_type=${docType}`);
        const data = await response.json();

        if (data.success && data.categories) {
            categoriesContainer.innerHTML = data.categories.map(category => `
                <label class="category-checkbox-item">
                    <input type="checkbox" name="crawl-category" value="${category}" checked>
                    <span class="category-name">${category}</span>
                </label>
            `).join('');
        }
    } catch (error) {
        console.error('카테고리 로드 실패:', error);
        categoriesContainer.innerHTML = '<p class="error-text">카테고리를 불러오는데 실패했습니다.</p>';
    }
}

/**
 * 전체 선택/해제 버튼 이벤트 설정
 */
export function setupFullCrawlCategoryButtons() {
    const selectAllBtn = document.getElementById('full-crawl-select-all');
    const clearAllBtn = document.getElementById('full-crawl-clear-all');

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('#full-crawl-categories input[type="checkbox"]');
            checkboxes.forEach(cb => cb.checked = true);
        });
    }

    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('#full-crawl-categories input[type="checkbox"]');
            checkboxes.forEach(cb => cb.checked = false);
        });
    }
}

/**
 * Zone 라디오 버튼 변경 시 카테고리 자동 재로드 이벤트 설정
 */
export function setupZoneChangeHandler() {
    const zoneRadios = document.querySelectorAll('input[name="crawl-zone"]');
    zoneRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            // Zone 변경 시 카테고리 목록 재로드
            loadCrawlCategories();
        });
    });
}

/**
 * 문서 유형 체크박스 변경 시 카테고리 자동 재로드 이벤트 설정
 */
export function setupDocTypeChangeHandler() {
    const docTypeCheckboxes = document.querySelectorAll('input[name="doc-type"]');
    docTypeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            // 최소 하나는 선택되어 있어야 함
            const checkedCount = document.querySelectorAll('input[name="doc-type"]:checked').length;
            if (checkedCount === 0) {
                e.target.checked = true;  // 체크 해제 방지
                return;
            }
            // 문서 유형 변경 시 카테고리 목록 재로드
            loadCrawlCategories();
        });
    });
}

/**
 * 선택된 카테고리 목록 반환
 * @returns {string[]} 선택된 카테고리 배열
 */
function getSelectedCategories() {
    const checkboxes = document.querySelectorAll('#full-crawl-categories input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

/**
 * 선택된 존(Zone) 반환
 * @returns {string} 선택된 존 (standard, finance, gov)
 */
function getSelectedZone() {
    const selected = document.querySelector('input[name="crawl-zone"]:checked');
    return selected ? selected.value : 'standard';
}

/**
 * 선택된 문서 유형(doc_type) 배열 반환
 * @returns {string[]} 선택된 문서 유형 배열 (user_guide, api_guide)
 */
function getSelectedDocTypes() {
    const checkboxes = document.querySelectorAll('input[name="doc-type"]:checked');
    const docTypes = Array.from(checkboxes).map(cb => cb.value);
    // 최소 하나는 선택되어 있어야 함
    return docTypes.length > 0 ? docTypes : ['user_guide'];
}

/**
 * 존 이름 반환 (표시용)
 * @param {string} zone - 존 코드
 * @returns {string} 존 이름
 */
function getZoneDisplayName(zone) {
    const names = {
        standard: '일반',
        finance: '금융',
        gov: '공공'
    };
    return names[zone] || '일반';
}

/**
 * 문서 유형 이름 반환 (표시용)
 * @param {string} docType - 문서 유형 코드
 * @returns {string} 문서 유형 이름
 */
function getDocTypeDisplayName(docType) {
    const names = {
        user_guide: '사용자 가이드',
        api_guide: 'API 가이드'
    };
    return names[docType] || docType;
}

/**
 * 전체 크롤링 시작
 */
export async function startFullCrawling() {
    if (isFullCrawlRunning) {
        showErrorMessage('크롤링 진행 중', '이미 전체 크롤링이 진행 중입니다.', '');
        return;
    }

    const selectedCategories = getSelectedCategories();

    if (selectedCategories.length === 0) {
        showErrorMessage(
            '카테고리 선택 필요',
            '크롤링할 카테고리를 최소 1개 이상 선택해주세요.',
            ''
        );
        return;
    }

    const crawlBtn = document.getElementById('full-crawl-btn');
    const stopBtn = document.getElementById('full-crawl-stop-btn');
    const statusSection = document.getElementById('full-crawl-status');
    const resultSection = document.getElementById('full-crawl-result');
    const logContent = document.getElementById('full-crawl-log-content');

    // UI 상태 업데이트
    isFullCrawlRunning = true;
    crawlBtn.style.display = 'none';
    stopBtn.style.display = 'inline-flex';
    statusSection.style.display = 'block';
    resultSection.style.display = 'none';
    if (logContent) logContent.innerHTML = '';

    const addLog = createLogAdder(logContent);
    const selectedZone = getSelectedZone();
    const zoneName = getZoneDisplayName(selectedZone);
    const selectedDocTypes = getSelectedDocTypes();
    const docTypeNames = selectedDocTypes.map(dt => getDocTypeDisplayName(dt)).join(', ');

    addLog(`[${zoneName}] 전체 크롤링 시작... (${docTypeNames})`, 'status');

    try {
        // 선택된 문서 유형에 따라 category_id 결정
        // - API 가이드만 선택: 'api'
        // - 사용자 가이드만 선택 또는 둘 다: 'guide' (백엔드에서 doc_type별로 재분기)
        const categoryId = (selectedDocTypes.length === 1 && selectedDocTypes[0] === 'api_guide')
            ? 'api'
            : 'guide';

        const requestBody = {
            categories: selectedCategories,
            category_id: categoryId,
            zone: selectedZone,
            doc_types: selectedDocTypes  // 문서 유형 배열 추가
        };

        const response = await fetch('api/crawl/all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error('전체 크롤링 요청 실패');
        }

        await processFullCrawlStream(response, addLog);

    } catch (error) {
        addLog(`❌ 오류: ${error.message}`, 'error');
        showErrorMessage(
            '전체 크롤링 실패',
            `크롤링 중 오류가 발생했습니다: ${error.message}`,
            ''
        );
    } finally {
        isFullCrawlRunning = false;
        crawlBtn.style.display = 'inline-flex';
        stopBtn.style.display = 'none';
    }
}

/**
 * 전체 크롤링 스트림 처리
 * @param {Response} response - fetch 응답
 * @param {Function} addLog - 로그 추가 함수
 */
async function processFullCrawlStream(response, addLog) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const progressBar = document.getElementById('full-crawl-progress-bar');
    const progressPercent = document.getElementById('full-crawl-progress-percent');
    const currentService = document.getElementById('full-crawl-current-service');
    const serviceCount = document.getElementById('full-crawl-service-count');
    const resultSection = document.getElementById('full-crawl-result');
    const completedCount = document.getElementById('full-crawl-completed-count');
    const totalPages = document.getElementById('full-crawl-total-pages');
    const errorCount = document.getElementById('full-crawl-error-count');

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.substring(6));

                    switch (data.type) {
                        case 'status':
                            addLog(data.message, 'status');
                            break;

                        case 'progress':
                            addLog(data.message, determineLogType(data.message));
                            break;

                        case 'service_start':
                            currentService.textContent = `📁 ${data.service_name}`;
                            serviceCount.textContent = `(${data.current} / ${data.total} 서비스)`;
                            updateProgressBar(progressBar, progressPercent, data.current, data.total);
                            addLog(`▶️ ${data.service_name} 크롤링 시작`, 'status');
                            break;

                        case 'service_complete':
                            addLog(`✅ ${data.service_name}: ${data.page_count}개 페이지`, 'success');
                            break;

                        case 'service_error':
                            addLog(`❌ ${data.service_name}: ${data.error}`, 'error');
                            break;

                        case 'complete':
                            const status = data.status || data;
                            currentService.textContent = '✅ 크롤링 완료';
                            serviceCount.textContent = '';
                            updateProgressBar(progressBar, progressPercent, 100, 100);

                            // 결과 표시
                            resultSection.style.display = 'block';
                            completedCount.textContent = status.completed_services?.length || 0;
                            totalPages.textContent = status.total_pages || 0;
                            errorCount.textContent = status.errors?.length || 0;

                            addLog(`🎉 전체 크롤링 완료: ${status.completed_services?.length || 0}개 서비스, ${status.total_pages || 0}개 페이지`, 'success');

                            // 문서 목록 새로고침
                            if (onDocumentsLoadCallback) {
                                await onDocumentsLoadCallback();
                            }
                            break;

                        case 'error':
                            addLog(`❌ ${data.message}`, 'error');
                            break;
                    }
                } catch (parseError) {
                    console.error('JSON 파싱 오류:', parseError);
                }
            }
        }
    }
}

/**
 * 프로그레스 바 업데이트
 */
function updateProgressBar(progressBar, progressPercent, current, total) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressPercent) progressPercent.textContent = `${percent}%`;
}

/**
 * 전체 크롤링 중지
 */
export async function stopFullCrawling() {
    if (!isFullCrawlRunning) return;

    try {
        const response = await fetch('api/crawl/all/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            const logContent = document.getElementById('full-crawl-log-content');
            const addLog = createLogAdder(logContent);
            addLog('⏹️ 크롤링 중지 요청됨...', 'status');
        }
    } catch (error) {
        console.error('크롤링 중지 실패:', error);
    }
}
