// ===================================================================
// RAG 문서 질의응답 시스템 - 모듈화 버전
// 2700+ 줄 -> 200줄 미만으로 리팩토링 완료
// ===================================================================

import { state } from './modules/state.js';

import {
    initTabNavigation, setTabChangeCallback
} from './modules/features/tabs.js';

import {
    updateActiveDocumentsDisplay, setDocumentsActivatedCallback,
    initTutorial, checkAndShowTutorial
} from './modules/features/modals/index.js';

import {
    initDocumentPrepareTab, setPrepareDocumentsLoadCallback
} from './modules/features/prepare/index.js';

import {
    initChatTab, setSystemReadyCallback
} from './modules/features/chat/index.js';

import {
    initManageTab, loadVectorDBDocuments,
    setStatsUpdateCallback, setSidebarBadgesUpdateCallback
} from './modules/features/manage/index.js';

// ===================================================================
// 초기화
// ===================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 RAG 시스템 초기화 시작');

    // 탭 전환 콜백 설정: 탭 전환 시 상태 업데이트
    setTabChangeCallback((tabName) => {
        if (tabName === 'chat') {
            updateActiveDocumentsDisplay();
        } else if (tabName === 'manage') {
            // 문서 관리 탭 진입 시 자동 새로고침
            loadVectorDBDocuments();
        }
    });

    // 문서 활성화 콜백 설정: 문서 활성화 후 UI 업데이트
    setDocumentsActivatedCallback(updateActiveDocumentsDisplay);

    // 문서 준비 탭에서 문서 로드 후 콜백 설정
    setPrepareDocumentsLoadCallback(loadVectorDBDocuments);

    // 질의응답 탭 시스템 준비 상태 콜백 설정
    setSystemReadyCallback(() => state.isReady);

    // 문서 관리 탭 콜백 설정
    setStatsUpdateCallback(updateStats);
    setSidebarBadgesUpdateCallback(updateSidebarBadges);

    initTabNavigation();
    initDocumentPrepareTab();
    initChatTab();
    initManageTab();
    loadCategories();
    loadSystemStatus();
    loadVectorDBDocuments();

    // 튜토리얼 초기화 및 최초 방문 체크
    initTutorial();
    checkAndShowTutorial();

    console.log('✅ 초기화 완료');
});

// ===================================================================
// 시스템 상태 및 통계
// ===================================================================

async function loadSystemStatus() {
    try {
        // /api/documents/status를 사용하여 ready 상태 확인
        const response = await fetch('api/documents/status');
        const data = await response.json();

        const llmProvider = document.getElementById('llm-provider');
        const statusText = document.getElementById('status-text');
        const statusIndicator = document.getElementById('status-indicator');

        if (llmProvider && data.llm_provider) {
            llmProvider.textContent = data.llm_provider.toUpperCase();
        }

        if (data.ready) {
            statusText.textContent = '준비됨';
            if (statusIndicator) {
                statusIndicator.className = 'status-dot status-ready';
            }

            state.isReady = true;
            document.getElementById('question-input').disabled = false;
            document.getElementById('ask-btn').disabled = false;

            // 활성 문서 표시 업데이트
            await updateActiveDocumentsDisplay();
        } else {
            statusText.textContent = '대기 중';
            if (statusIndicator) {
                statusIndicator.className = 'status-dot';
            }

            state.isReady = false;
            document.getElementById('question-input').disabled = true;
            document.getElementById('ask-btn').disabled = true;

            // 비활성 상태에서도 활성 문서 표시 업데이트
            await updateActiveDocumentsDisplay();
        }
    } catch (error) {
        console.error('상태 로드 실패:', error);
    }
}

function updateStats(documents) {
    const statTotalDocs = document.getElementById('stat-total-docs');
    const statTotalChunks = document.getElementById('stat-total-chunks');
    const statCategories = document.getElementById('stat-categories');

    // 총 문서 수
    const totalDocs = documents.length;
    if (statTotalDocs) {
        statTotalDocs.textContent = totalDocs;
    }

    // 총 청크 수
    const totalChunks = documents.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0);
    if (statTotalChunks) {
        statTotalChunks.textContent = totalChunks;
    }

    // 카테고리 수 (컬렉션 접두사 기준)
    const uniqueCategories = new Set(documents.map(doc => doc.collection.split('_')[0]));
    if (statCategories) {
        statCategories.textContent = uniqueCategories.size || state.categories.length;
    }
}

function updateSidebarBadges() {
    const totalDocsBadge = document.getElementById('total-docs-badge');

    if (totalDocsBadge && state.allDocsInManage.length > 0) {
        totalDocsBadge.textContent = state.allDocsInManage.length;
        totalDocsBadge.style.display = 'inline-block';
    } else if (totalDocsBadge) {
        totalDocsBadge.style.display = 'none';
    }
}

async function loadCategories() {
    try {
        const response = await fetch('api/categories');
        const data = await response.json();

        if (data.success) {
            state.categories = data.categories;
            populateCategorySelector();
        }
    } catch (error) {
        console.error('카테고리 로드 실패:', error);
    }
}

function populateCategorySelector() {
    const selector = document.getElementById('category-select');
    if (!selector) return;

    selector.innerHTML = '';
    state.categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = `${cat.icon} ${cat.name}`;
        selector.appendChild(option);
    });
}

// ===================================================================
// 채팅 초기화 함수
// ===================================================================

function clearChatHistory() {
    if (!confirm('대화 내역을 모두 삭제하시겠습니까?')) {
        return;
    }

    const chatHistory = document.getElementById('chat-history');
    chatHistory.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">👋</div>
            <h2>안녕하세요!</h2>
            <p>문서를 기반으로 질문에 답변해드립니다.</p>
            <p class="welcome-hint">먼저 <strong>"활성화 문서 변경"</strong> 버튼으로 문서를 활성화해주세요.</p>
        </div>
    `;

    console.log('✅ 대화 내역이 초기화되었습니다.');
}

// 전역 함수로 노출
window.clearChatHistory = clearChatHistory;
