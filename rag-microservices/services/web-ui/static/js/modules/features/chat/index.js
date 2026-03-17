// ===================================================================
// 질의응답 탭 모듈
// 스트리밍 Q&A 기능 통합
// ===================================================================

import {
    askQuestionStream,
    addMessage
} from './streaming.js';

/**
 * 시스템 준비 상태 체크 콜백
 * @type {Function|null}
 */
let isSystemReadyCallback = null;

/**
 * 시스템 준비 상태 체크 콜백 설정
 * @param {Function} callback - 준비 상태 반환 함수
 */
export function setSystemReadyCallback(callback) {
    isSystemReadyCallback = callback;
}

/**
 * 질의응답 탭 초기화
 */
export function initChatTab() {
    const askBtn = document.getElementById('ask-btn');
    const questionInput = document.getElementById('question-input');

    askBtn.addEventListener('click', askQuestion);
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askQuestion();
        }
    });

    // 채팅 영역 복사 시 줄바꿈 유지 처리
    const chatHistory = document.getElementById('chat-history');
    if (chatHistory) {
        chatHistory.addEventListener('copy', handleChatCopy);
    }
}

/**
 * 채팅 영역 복사 이벤트 처리
 * HTML 요소들 사이의 줄바꿈을 유지하여 복사
 * @param {ClipboardEvent} e - 복사 이벤트
 */
function handleChatCopy(e) {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    // 선택된 영역의 HTML을 가져옴
    const range = selection.getRangeAt(0);
    const container = document.createElement('div');
    container.appendChild(range.cloneContents());

    // HTML을 텍스트로 변환 (줄바꿈 유지)
    const formattedText = convertHtmlToText(container);

    // 클립보드에 포맷된 텍스트 복사
    e.preventDefault();
    e.clipboardData.setData('text/plain', formattedText);
}

/**
 * HTML 요소를 줄바꿈이 유지된 텍스트로 변환
 * @param {HTMLElement} element - 변환할 HTML 요소
 * @returns {string} 줄바꿈이 포함된 텍스트
 */
function convertHtmlToText(element) {
    let result = '';

    for (const node of element.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
            result += node.textContent;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const tagName = node.tagName.toLowerCase();

            // 블록 요소들은 앞뒤로 줄바꿈 추가
            const blockElements = ['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'tr'];
            const isBlock = blockElements.includes(tagName);

            if (tagName === 'br') {
                result += '\n';
            } else if (tagName === 'li') {
                result += '• ' + convertHtmlToText(node) + '\n';
            } else if (isBlock) {
                const text = convertHtmlToText(node).trim();
                if (text) {
                    result += text + '\n\n';
                }
            } else {
                result += convertHtmlToText(node);
            }
        }
    }

    // 연속된 줄바꿈 정리 (3개 이상 → 2개)
    return result.replace(/\n{3,}/g, '\n\n').trim();
}

/**
 * 질문 제출 처리
 */
async function askQuestion() {
    const questionInput = document.getElementById('question-input');
    const question = questionInput.value.trim();

    if (!question) {
        alert('질문을 입력해주세요.');
        return;
    }

    // 시스템 준비 상태 확인
    if (isSystemReadyCallback && !isSystemReadyCallback()) {
        alert('먼저 문서를 활성화해주세요.');
        return;
    }

    // 입력 비활성화
    questionInput.disabled = true;
    document.getElementById('ask-btn').disabled = true;

    // 질문 표시
    addMessage('question', question);
    questionInput.value = '';

    // 스트리밍 답변 처리
    await askQuestionStream(question);

    // 입력 재활성화
    questionInput.disabled = false;
    document.getElementById('ask-btn').disabled = false;
    questionInput.focus();
}

// Re-export for direct access
export { addMessage } from './streaming.js';
