// ===================================================================
// 스트리밍 질의응답 모듈
// 스트리밍 API를 통한 실시간 답변 처리
// ===================================================================

import { scrollChatToBottom } from '../../utils.js';

// 현재 질문 저장 (재시도용)
let currentQuestion = '';

/**
 * 스트리밍 방식으로 질문 전송 및 답변 수신
 * @param {string} question - 질문 텍스트
 */
export async function askQuestionStream(question) {
    currentQuestion = question;
    let answerContainer = null;

    try {
        // 로딩 컨테이너 먼저 생성
        answerContainer = createStreamingAnswerContainer();
        const contentDiv = answerContainer.querySelector('.message-content');
        const statusTextDiv = answerContainer.querySelector('.loading-status-text');

        const response = await fetch('api/query/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `서버 오류 (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let answerText = '';
        let metadata = null;
        let hasReceivedAnswer = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');

            if (!buffer.endsWith('\n\n')) {
                buffer = lines.pop();
            } else {
                buffer = '';
            }

            for (const chunk of lines) {
                if (!chunk.trim()) continue;

                const { eventType, eventData } = parseSSEChunk(chunk);
                if (!eventType || !eventData) continue;

                try {
                    const data = JSON.parse(eventData);

                    // 첫 번째 answer 청크가 오면 로딩 인디케이터 제거
                    if (eventType === 'answer' && !hasReceivedAnswer) {
                        hasReceivedAnswer = true;
                        removeLoadingIndicator(contentDiv);
                    }

                    handleStreamEvent(eventType, data, {
                        answerContainer,
                        contentDiv,
                        statusTextDiv,
                        answerText: (text) => { answerText = text; return answerText; },
                        getAnswerText: () => answerText,
                        metadata: (m) => { metadata = m; return metadata; },
                        getMetadata: () => metadata
                    });
                } catch (e) {
                    console.error('이벤트 파싱 오류:', e, eventData);
                }
            }
        }
    } catch (error) {
        console.error('질문 처리 오류:', error);
        if (answerContainer) {
            showErrorMessage(answerContainer, error.message);
        } else {
            addErrorMessage(error.message);
        }
    }
}

/**
 * 로딩 인디케이터 제거
 * @param {HTMLElement} contentDiv - 콘텐츠 영역
 */
function removeLoadingIndicator(contentDiv) {
    const loadingStatus = contentDiv.querySelector('.loading-status');
    if (loadingStatus) {
        loadingStatus.remove();
    }
}

/**
 * 에러 메시지 표시 (기존 컨테이너에)
 * @param {HTMLElement} answerContainer - 답변 컨테이너
 * @param {string} errorMessage - 에러 메시지
 */
function showErrorMessage(answerContainer, errorMessage) {
    const contentDiv = answerContainer.querySelector('.message-content');
    contentDiv.innerHTML = `
        <div class="error-message">
            <div class="error-text">
                <span class="error-icon">❌</span>
                <span class="error-detail">${escapeHtml(errorMessage)}</span>
            </div>
            <button class="retry-btn" onclick="window.retryLastQuestion()">🔄 재시도</button>
        </div>
    `;

    // 복사 버튼 숨기기
    const actionsDiv = answerContainer.querySelector('.message-actions');
    if (actionsDiv) actionsDiv.style.display = 'none';
}

/**
 * 에러 메시지 추가 (새 컨테이너로)
 * @param {string} errorMessage - 에러 메시지
 */
function addErrorMessage(errorMessage) {
    const chatHistory = document.getElementById('chat-history');
    const welcomeMsg = chatHistory.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message answer';
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-wrapper">
            <div class="message-content">
                <div class="error-message">
                    <div class="error-text">
                        <span class="error-icon">❌</span>
                        <span class="error-detail">${escapeHtml(errorMessage)}</span>
                    </div>
                    <button class="retry-btn" onclick="window.retryLastQuestion()">🔄 재시도</button>
                </div>
            </div>
        </div>
    `;

    chatHistory.appendChild(messageDiv);
    scrollChatToBottom();
}

/**
 * HTML 이스케이프
 * @param {string} text - 원본 텍스트
 * @returns {string} 이스케이프된 텍스트
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 답변 텍스트 포맷팅 (가독성 향상)
 * @param {string} text - 원본 텍스트
 * @returns {string} 포맷팅된 HTML
 */
function formatAnswerText(text) {
    if (!text) return '';

    // 1. HTML 이스케이프
    let formatted = escapeHtml(text);

    // 2. 마크다운 볼드 처리: **text** → <strong>text</strong>
    // LLM이 **text ** 형태로 생성하는 경우도 처리
    formatted = formatted.replace(/\*\*\s*([^*]+?)\s*\*\*/g, '<strong>$1</strong>');

    // 3. 코드 블록 처리: `code` → <code>code</code>
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    // === 줄바꿈 처리 ===

    // 4. 불릿(-) 앞에 줄바꿈 추가 (문장 시작 제외)
    formatted = formatted.replace(/([^-\n])-(<strong>|[가-힣a-zA-Z])/g, '$1\n- $2');

    // 5. 번호 리스트 앞에 줄바꿈: "1. ", "2. " 등
    formatted = formatted.replace(/([^\n\d])(\d+\.\s)/g, '$1\n$2');

    // 6. 연속 줄바꿈 → 문단 구분
    formatted = formatted.replace(/\n\n+/g, '</p><p>');

    // 7. 단일 줄바꿈 → <br>
    formatted = formatted.replace(/\n/g, '<br>');

    // 8. 불릿 스타일링: "- " → "• "
    formatted = formatted.replace(/<br>-\s*/g, '<br>• ');
    formatted = formatted.replace(/^-\s*/g, '• ');

    // 9. 문단 감싸기
    formatted = '<p>' + formatted + '</p>';

    // 10. 빈 문단 제거
    formatted = formatted.replace(/<p>\s*<\/p>/g, '');

    // 11. 연속 <br> 정리
    formatted = formatted.replace(/(<br>){3,}/g, '<br><br>');

    return formatted;
}

/**
 * 마지막 질문 재시도 (전역 함수로 노출)
 */
window.retryLastQuestion = async function() {
    if (!currentQuestion) return;

    // 마지막 에러 메시지 제거
    const chatHistory = document.getElementById('chat-history');
    const lastMessage = chatHistory.querySelector('.message.answer:last-child');
    if (lastMessage && lastMessage.querySelector('.error-message')) {
        lastMessage.remove();
    }

    // 재시도
    const questionInput = document.getElementById('question-input');
    questionInput.disabled = true;
    document.getElementById('ask-btn').disabled = true;

    await askQuestionStream(currentQuestion);

    questionInput.disabled = false;
    document.getElementById('ask-btn').disabled = false;
    questionInput.focus();
};

/**
 * SSE 청크 파싱
 * @param {string} chunk - SSE 청크 문자열
 * @returns {{ eventType: string, eventData: string }}
 */
function parseSSEChunk(chunk) {
    const eventLines = chunk.split('\n');
    let eventType = '';
    let eventData = '';

    for (const line of eventLines) {
        if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
            eventData = line.slice(6).trim();
        }
    }

    return { eventType, eventData };
}

/**
 * 스트림 이벤트 처리
 * @param {string} eventType - 이벤트 타입
 * @param {Object} data - 이벤트 데이터
 * @param {Object} context - 처리 컨텍스트
 */
function handleStreamEvent(eventType, data, context) {
    const { answerContainer, contentDiv, statusTextDiv } = context;

    switch (eventType) {
        case 'status':
            // 로딩 상태 텍스트 업데이트
            if (statusTextDiv) {
                statusTextDiv.textContent = data.message || '처리 중...';
            }
            scrollChatToBottom();
            break;

        case 'answer':
            const newText = context.getAnswerText() + (data.content || '');
            context.answerText(newText);
            // 가독성 향상: 줄바꿈을 <br>로 변환하고, 마크다운 스타일 지원
            contentDiv.innerHTML = formatAnswerText(newText);
            scrollChatToBottom();
            break;

        case 'sources':
            let meta = context.getMetadata() || {};
            meta.sources = data.sources || [];
            context.metadata(meta);
            break;

        case 'done':
            const currentMeta = context.getMetadata() || {};
            const finalMeta = { ...currentMeta, ...data };
            context.metadata(finalMeta);
            if (finalMeta) {
                appendMetadata(answerContainer, finalMeta);
            }
            break;

        case 'error':
            removeLoadingIndicator(contentDiv);
            contentDiv.textContent = '❌ 오류: ' + (data.error || '알 수 없는 오류');
            break;
    }
}

/**
 * 스트리밍 답변 컨테이너 생성
 * @returns {HTMLElement} 생성된 메시지 컨테이너
 */
export function createStreamingAnswerContainer() {
    const chatHistory = document.getElementById('chat-history');

    const welcomeMsg = chatHistory.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message answer';
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-wrapper">
            <div class="message-content">
                <div class="loading-status">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    <span class="loading-status-text">답변 생성 준비 중...</span>
                </div>
            </div>
            <div class="message-actions">
                <button class="copy-btn" title="답변 복사">📋 복사</button>
            </div>
            <div class="message-timestamp">${timeStr}</div>
        </div>
    `;

    // 복사 버튼 이벤트 설정
    const copyBtn = messageDiv.querySelector('.copy-btn');
    const contentDiv = messageDiv.querySelector('.message-content');
    copyBtn.addEventListener('click', () => {
        const text = contentDiv.textContent;
        navigator.clipboard.writeText(text).then(() => {
            copyBtn.textContent = '✅ 복사됨';
            setTimeout(() => {
                copyBtn.textContent = '📋 복사';
            }, 2000);
        }).catch(err => {
            console.error('복사 실패:', err);
            copyBtn.textContent = '❌ 실패';
            setTimeout(() => {
                copyBtn.textContent = '📋 복사';
            }, 2000);
        });
    });

    chatHistory.appendChild(messageDiv);
    scrollChatToBottom();

    return messageDiv;
}

/**
 * 메타데이터 추가 (품질 정보, 참조 문서 등)
 * @param {HTMLElement} answerContainer - 답변 컨테이너
 * @param {Object} metadata - 메타데이터 객체
 */
export function appendMetadata(answerContainer, metadata) {
    const messageWrapper = answerContainer.querySelector('.message-wrapper');

    const qualityScore = metadata.quality_score || 0;
    const confidence = metadata.confidence || 'unknown';
    const processingTime = metadata.processing_time || 0;

    const confidenceColors = {
        'high': '#48bb78',
        'medium': '#ed8936',
        'low': '#f56565'
    };
    const confidenceColor = confidenceColors[confidence] || '#718096';

    const originalQuestion = metadata.original_question || '';
    const searchQueries = metadata.search_queries || [];
    const queryType = metadata.query_type || '';

    const hybridSearchUsed = metadata.hybrid_search_used || false;
    const hallucinationDetected = metadata.hallucination_detected || false;
    const rerankScores = metadata.rerank_scores || null;

    const selfRagVerification = metadata.self_rag_verification || {};
    const hasVerification = Object.keys(selfRagVerification).length > 0;

    const queryTransformHtml = buildQueryTransformHtml(originalQuestion, searchQueries, queryType);
    const selfRagHtml = buildSelfRagHtml(selfRagVerification, hasVerification);
    const rerankHtml = buildRerankHtml(rerankScores);
    const ragFeaturesHtml = buildRagFeaturesHtml(hybridSearchUsed);

    // 품질 정보 HTML
    const qualityHtml = `
        <details class="metadata-toggle">
            <summary>📊 품질 정보</summary>
            <div class="metadata-content">
                <div class="quality-info">
                    <div class="quality-metrics">
                        <div class="metric">
                            <span class="metric-label">처리 시간:</span>
                            <span class="metric-value">${processingTime.toFixed(2)}초</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">사용된 모델:</span>
                            <span class="metric-value" style="font-weight: 600; color: #3182ce">${metadata.used_model || 'N/A'}</span>
                        </div>
                        ${hallucinationDetected ? buildHallucinationWarningHtml() : ''}
                    </div>
                    ${queryTransformHtml}
                    ${rerankHtml}
                    ${selfRagHtml}
                    ${ragFeaturesHtml}
                </div>
            </div>
        </details>
    `;

    const sourcesHtml = buildSourcesHtml(metadata.sources);

    const messageContent = messageWrapper.querySelector('.message-content');
    const timestamp = messageWrapper.querySelector('.message-timestamp');

    if (messageContent && timestamp) {
        messageContent.insertAdjacentHTML('afterend', qualityHtml + sourcesHtml);
    } else {
        messageWrapper.innerHTML += qualityHtml + sourcesHtml;
    }

    scrollChatToBottom();
}

/**
 * 쿼리 변환 정보 HTML 생성
 */
function buildQueryTransformHtml(originalQuestion, searchQueries, queryType) {
    if (searchQueries.length === 0 || searchQueries[0] === originalQuestion) {
        return '';
    }

    return `
        <div class="metric-section">
            <div class="metric-section-title">🔄 쿼리 변환</div>
            <div class="metric">
                <span class="metric-label">원본 질문:</span>
                <span class="metric-value">${originalQuestion}</span>
            </div>
            ${searchQueries.map((query, idx) => `
                <div class="metric">
                    <span class="metric-label">변환 쿼리 ${idx + 1}:</span>
                    <span class="metric-value">${query}</span>
                </div>
            `).join('')}
            ${queryType ? `
                <div class="metric">
                    <span class="metric-label">쿼리 유형:</span>
                    <span class="metric-value" style="color: #3182ce">${queryType}</span>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Self-RAG 검증 HTML 생성
 */
function buildSelfRagHtml(selfRagVerification, hasVerification) {
    if (!hasVerification) return '';

    const groundingScore = selfRagVerification.raw_scores?.grounding || 0;
    const completenessScore = selfRagVerification.raw_scores?.completeness || 0;
    const accuracyScore = selfRagVerification.raw_scores?.accuracy || 0;
    const hasHallucination = selfRagVerification.has_hallucination || false;
    const feedback = selfRagVerification.feedback || '';

    return `
        <div class="metric-section">
            <div class="metric-section-title">🔍 Self-RAG 검증</div>
            <div class="metric">
                <span class="metric-label">문서 근거성:</span>
                <span class="metric-value">${groundingScore}/5</span>
            </div>
            <div class="metric">
                <span class="metric-label">답변 완결성:</span>
                <span class="metric-value">${completenessScore}/5</span>
            </div>
            <div class="metric">
                <span class="metric-label">정확성:</span>
                <span class="metric-value">${accuracyScore}/5</span>
            </div>
            ${hasHallucination ? `
                <div class="metric">
                    <span class="metric-label">할루시네이션:</span>
                    <span class="metric-value" style="color: #f56565">⚠️ 감지됨</span>
                </div>
            ` : ''}
            ${feedback ? `
                <div class="metric">
                    <span class="metric-label">피드백:</span>
                    <span class="metric-value" style="font-size: 0.9em">${feedback}</span>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Qwen Reranker 정보 HTML 생성
 */
function buildRerankHtml(rerankScores) {
    if (!rerankScores || rerankScores.length === 0) return '';

    const maxScore = Math.max(...rerankScores);
    const minScore = Math.min(...rerankScores);
    const avgScore = rerankScores.reduce((a, b) => a + b, 0) / rerankScores.length;

    return `
        <div class="metric-section">
            <div class="metric-section-title">🎯 Qwen Reranker (${rerankScores.length}개 문서)</div>
            <div class="metric">
                <span class="metric-label">최고 점수:</span>
                <span class="metric-value" style="color: #48bb78; font-weight: 600">${maxScore.toFixed(4)}</span>
            </div>
            <div class="metric">
                <span class="metric-label">평균 점수:</span>
                <span class="metric-value">${avgScore.toFixed(4)}</span>
            </div>
            <div class="metric">
                <span class="metric-label">최저 점수:</span>
                <span class="metric-value">${minScore.toFixed(4)}</span>
            </div>
            <div class="metric" style="margin-top: 8px;">
                <span class="metric-label">개별 점수:</span>
                <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                    ${rerankScores.map((score, idx) => `
                        <span style="
                            background: ${score > 0.7 ? '#48bb7820' : score > 0.5 ? '#ed893620' : '#f5656520'};
                            color: ${score > 0.7 ? '#48bb78' : score > 0.5 ? '#ed8936' : '#f56565'};
                            padding: 2px 6px;
                            border-radius: 3px;
                            font-size: 0.85em;
                            font-weight: 500;
                        ">#${idx + 1}: ${score.toFixed(3)}</span>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
}

/**
 * RAG 기능 정보 HTML 생성
 */
function buildRagFeaturesHtml(hybridSearchUsed) {
    return `
        <div class="metric-section">
            <div class="metric-section-title">⚙️ RAG 기능</div>
            <div class="metric">
                <span class="metric-label">Hybrid Search:</span>
                <span class="metric-value" style="color: ${hybridSearchUsed ? '#48bb78' : '#718096'}">
                    ${hybridSearchUsed ? '✓ 사용됨' : '미사용'}
                </span>
            </div>
        </div>
    `;
}

/**
 * 웹 검색 교차 검증 정보 HTML 생성
 */
function buildWebVerificationHtml(status, confidenceDelta, webSources, verificationDetails = null) {
    if (status === 'skipped' || !status) return '';

    const statusInfo = {
        'confirmed': { icon: '✅', label: '확인됨', color: '#48bb78', bg: '#f0fff4', desc: '웹 검색 결과와 답변 내용이 일치합니다.' },
        'enhanced': { icon: '✨', label: '보강됨', color: '#3182ce', bg: '#ebf8ff', desc: '웹 검색 결과로 답변이 보완되었습니다.' },
        'conflicting': { icon: '⚠️', label: '불일치', color: '#ed8936', bg: '#fffaf0', desc: '웹 검색 결과와 일부 차이가 있습니다.' },
        'no_data': { icon: 'ℹ️', label: '데이터 없음', color: '#718096', bg: '#f7fafc', desc: '관련 웹 검색 결과가 없습니다.' }
    };

    const info = statusInfo[status] || statusInfo['no_data'];

    // 검증 상세 정보 HTML 생성
    let detailsHtml = '';
    if (verificationDetails && (status === 'confirmed' || status === 'enhanced' || status === 'conflicting')) {
        const { matched_keywords = [], unmatched_keywords = [], match_ratio = 0 } = verificationDetails;

        if (status === 'confirmed' || status === 'enhanced') {
            // 확인됨/보강됨: 일치하는 키워드 표시
            if (matched_keywords.length > 0) {
                detailsHtml = `
                    <div class="metric" style="margin-top: 8px; padding: 10px; background: ${status === 'confirmed' ? '#f0fff4' : '#ebf8ff'}; border: 1px solid ${status === 'confirmed' ? '#9ae6b4' : '#90cdf4'}; border-radius: 6px;">
                        <div style="margin-bottom: 6px; font-weight: 600; color: ${status === 'confirmed' ? '#276749' : '#2b6cb0'};">📋 웹에서 확인된 키워드</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            ${matched_keywords.slice(0, 10).map(kw => `
                                <span style="background: ${status === 'confirmed' ? '#c6f6d5' : '#bee3f8'}; color: ${status === 'confirmed' ? '#22543d' : '#2a4365'}; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">${kw}</span>
                            `).join('')}
                            ${matched_keywords.length > 10 ? `<span style="color: ${status === 'confirmed' ? '#276749' : '#2b6cb0'}; font-size: 0.85em;">외 ${matched_keywords.length - 10}개</span>` : ''}
                        </div>
                        <div style="margin-top: 6px; font-size: 0.85em; color: ${status === 'confirmed' ? '#276749' : '#2b6cb0'};">
                            일치율: ${(match_ratio * 100).toFixed(0)}%
                        </div>
                    </div>
                `;
            }
        } else if (status === 'conflicting') {
            // 불일치: 확인되지 않은 키워드 표시
            if (unmatched_keywords.length > 0) {
                detailsHtml = `
                    <div class="metric" style="margin-top: 8px; padding: 10px; background: #fffaf0; border: 1px solid #fed7aa; border-radius: 6px;">
                        <div style="margin-bottom: 6px; font-weight: 600; color: #c05621;">📋 웹에서 확인되지 않은 키워드</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                            ${unmatched_keywords.slice(0, 10).map(kw => `
                                <span style="background: #fed7aa; color: #9a3412; padding: 2px 8px; border-radius: 4px; font-size: 0.85em;">${kw}</span>
                            `).join('')}
                            ${unmatched_keywords.length > 10 ? `<span style="color: #9a3412; font-size: 0.85em;">외 ${unmatched_keywords.length - 10}개</span>` : ''}
                        </div>
                        <div style="margin-top: 6px; font-size: 0.85em; color: #92400e;">
                            일치율: ${(match_ratio * 100).toFixed(0)}%
                        </div>
                    </div>
                `;
            }
        }
    }

    return `
        <div class="metric-section">
            <div class="metric-section-title">🌐 웹 검색 교차 검증</div>
            <div class="metric" style="padding: 8px; background: ${info.bg}; border-left: 3px solid ${info.color}; border-radius: 4px;">
                <span class="metric-label">${info.icon} 검증 결과:</span>
                <span class="metric-value" style="color: ${info.color}; font-weight: 600">${info.label}</span>
            </div>
            <div class="metric" style="font-size: 0.9em; color: #64748b; padding-left: 4px;">
                ${info.desc}
            </div>
            <div class="metric">
                <span class="metric-label">웹 참조:</span>
                <span class="metric-value">${webSources.length}개 소스</span>
            </div>
            ${detailsHtml}
        </div>
    `;
}

/**
 * 웹 소스 목록 HTML 생성
 */
function buildWebSourcesHtml(webSources) {
    if (!webSources || webSources.length === 0) return '';

    return `
        <details class="metadata-toggle">
            <summary>🌐 웹 참조 소스 (${webSources.length}개)</summary>
            <div class="metadata-content">
                <div class="web-sources-section">
                    ${webSources.map((source, idx) => `
                        <a href="${source.url}" target="_blank" rel="noopener noreferrer" class="web-source-item">
                            <div class="source-title">[${idx + 1}] ${source.title || '제목 없음'}</div>
                            ${source.snippet ? `<div class="source-snippet">${source.snippet}</div>` : ''}
                        </a>
                    `).join('')}
                </div>
            </div>
        </details>
    `;
}

/**
 * 할루시네이션 경고 HTML 생성
 */
function buildHallucinationWarningHtml() {
    return `
        <div class="metric" style="margin-top: 8px; padding: 8px; background: #fff5f5; border-left: 3px solid #f56565; border-radius: 4px;">
            <span class="metric-label" style="color: #c53030">⚠️ 할루시네이션 경고:</span>
            <span class="metric-value" style="color: #c53030; font-weight: 600">답변에 문서에 없는 정보가 포함되었을 수 있습니다</span>
        </div>
    `;
}

/**
 * 참조 문서 HTML 생성
 */
function buildSourcesHtml(sources) {
    if (!sources || sources.length === 0) return '';

    return `
        <details class="metadata-toggle">
            <summary>📑 참조 문서 (${sources.length}개)</summary>
            <div class="metadata-content">
                <div class="sources">
                    ${sources.map((source, idx) => {
                        // 백엔드 필드명 호환: filename/source, content_preview/content
                        const filename = source.filename || source.source || 'unknown';
                        const content = source.content_preview || source.content || '';
                        const score = source.score ? ` (유사도: ${(source.score * 100).toFixed(1)}%)` : '';
                        const chunkIdx = source.chunk_index !== undefined ? ` [청크 ${source.chunk_index}]` : '';

                        return `
                            <div class="source-item">
                                <div class="source-file">[${idx + 1}] ${filename}${chunkIdx}${score}</div>
                                <div class="source-content">${content}</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        </details>
    `;
}

/**
 * 채팅 메시지 추가
 * @param {string} type - 'question' 또는 'answer'
 * @param {string} content - 메시지 내용
 */
export function addMessage(type, content) {
    const chatHistory = document.getElementById('chat-history');

    const welcomeMsg = chatHistory.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;

    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    const avatar = type === 'question' ? '👤' : '🤖';
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-wrapper">
            <div class="message-content">${content}</div>
            <div class="message-timestamp">${timeStr}</div>
        </div>
    `;

    chatHistory.appendChild(messageDiv);
    scrollChatToBottom();
}
