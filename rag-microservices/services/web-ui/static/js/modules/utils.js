// ===================================================================
// 유틸리티 함수 모듈
// ===================================================================

/**
 * 바이트를 읽기 쉬운 형식으로 변환
 * @param {number} bytes - 바이트 수
 * @returns {string} 포맷된 문자열 (예: "1.5 MB")
 */
export function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * 파일 타입에 따른 아이콘과 색상 반환
 * @param {string} type - 파일 타입 (HTML, PDF, Excel, Word, Unknown)
 * @returns {{icon: string, color: string}} 아이콘과 색상 객체
 */
export function getFileTypeInfo(type) {
    const typeMap = {
        'HTML': { icon: '📄', color: '#e53e3e' },
        'PDF': { icon: '📕', color: '#dd6b20' },
        'Excel': { icon: '📊', color: '#38a169' },
        'Word': { icon: '📘', color: '#2563eb' },
        'Unknown': { icon: '📎', color: '#718096' }
    };
    return typeMap[type] || typeMap['Unknown'];
}

/**
 * 로딩 스피너 표시
 * @param {string} text - 로딩 메시지
 */
export function showLoading(text = '처리 중...') {
    const loading = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');
    if (loadingText) loadingText.textContent = text;
    if (loading) loading.style.display = 'flex';
}

/**
 * 로딩 스피너 숨기기
 */
export function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) loading.style.display = 'none';
}

/**
 * 오류 메시지 표시
 * @param {string} title - 오류 제목
 * @param {string} description - 오류 설명
 * @param {string} solution - 해결 방법
 * @param {Array|null} buttons - 버튼 배열 [{text, action}]
 */
export function showErrorMessage(title, description, solution, buttons = null) {
    const message = `❌ ${title}\n\n${description}\n\n${solution}`;

    if (buttons && buttons.length > 0) {
        const proceed = confirm(message + '\n\n계속하시겠습니까?');
        if (proceed && buttons[0].action) {
            buttons[0].action();
        } else if (!proceed && buttons[1] && buttons[1].action) {
            buttons[1].action();
        }
    } else {
        alert(message);
    }
}

/**
 * 진행 로그 추가
 * @param {string} type - 로그 타입 (info, success, error, status, progress)
 * @param {string} message - 로그 메시지
 */
export function addProgressLog(type, message) {
    const progressLog = document.getElementById('progress-log');
    if (!progressLog) return;

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${type}`;
    logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    progressLog.appendChild(logEntry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

/**
 * 답변 텍스트 가독성 개선
 * @param {string} text - 원본 텍스트
 * @returns {string} 포맷된 텍스트
 */
export function formatAnswerForReadability(text) {
    if (!text) return text;

    let formatted = text;

    // 1. 숫자 리스트 패턴 감지 및 줄바꿈 추가
    formatted = formatted.replace(/([.!?][\)]?)\s+(\d+\.\s)/g, '$1\n\n$2');

    // 2. 연속된 [문서 N] 참조 중복 제거
    formatted = formatted.replace(/(\[문서\s+\d+\])+/g, (match) => {
        const refs = match.match(/\[문서\s+\d+\]/g);
        const uniqueRefs = [...new Set(refs)];
        return uniqueRefs.join('');
    });

    // 3. 문단 시작 부분 앞에 줄바꿈
    formatted = formatted.replace(/\s+(또한|그러나|따라서|단,|다만,)\s+/g, '\n\n$1 ');

    // 4. 긴 문장 후 자동 문단 분리
    const sentences = formatted.split(/(?<=[.!?])\s+/);
    formatted = sentences.map((sentence, idx) => {
        if (idx > 0 && sentences[idx - 1].length > 150 && !/^\d+\./.test(sentence)) {
            return '\n' + sentence;
        }
        return sentence;
    }).join(' ');

    // 5. 과도한 줄바꿈 제거
    formatted = formatted.replace(/\n{3,}/g, '\n\n');

    return formatted;
}

/**
 * 채팅 영역 스크롤을 맨 아래로 이동
 */
export function scrollChatToBottom() {
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

/**
 * 현재 시간을 포맷된 문자열로 반환
 * @returns {string} 포맷된 시간 문자열 (예: "오후 3:45")
 */
export function getFormattedTime() {
    const now = new Date();
    return now.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}
