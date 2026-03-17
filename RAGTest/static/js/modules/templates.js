// ===================================================================
// HTML 템플릿 모듈
// ===================================================================

import { getFileTypeInfo, formatBytes, getFormattedTime } from './utils.js';

/**
 * 문서 관리 탭의 문서 카드 HTML 생성
 * @param {Object} doc - 문서 객체
 * @returns {string} HTML 문자열
 */
export function createDocumentCardHTML(doc) {
    const category = doc.category || { id: 'general', name: '일반', color: '#6366f1', icon: '📄' };

    return `
        <div class="doc-info" style="flex: 1; min-width: 0;">
            <div class="doc-name" style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span style="font-size: 1.25rem;">${category.icon}</span>
                <span style="font-weight: 600; font-size: 0.95rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${doc.filename}</span>
            </div>
            <div class="doc-meta" style="display: flex; flex-wrap: wrap; gap: 12px; font-size: 0.875rem; color: #64748b;">
                <span class="doc-chunks">✂️ ${doc.chunk_count}개 청크</span>
                <span class="doc-date">📅 ${doc.added_at}</span>
                ${doc.method ? `<span class="doc-method" style="background: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}20; color: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">${doc.method === 'semantic' ? '🧠 Semantic' : '📏 Fixed'}</span>` : ''}
                ${doc.embedding_model ? `<span class="doc-embedding" style="background: #f59e0b20; color: #f59e0b; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">🤖 ${doc.embedding_model}</span>` : ''}
                <span class="doc-collection" style="display: none;">📦 ${doc.collection}</span>
                <span style="color: ${category.color}; font-weight: 500;">${category.name}</span>
            </div>
        </div>
        <button class="doc-preview-btn" data-filename="${doc.filename}" data-collection="${doc.collection}" style="padding: 8px 16px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; white-space: nowrap;">📋 미리보기</button>
        <select class="doc-category-select" data-filename="${doc.filename}" data-collection="${doc.collection}" style="padding: 6px 10px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 0.875rem; cursor: pointer; min-width: 130px;">
            <option value="general" ${category.id === 'general' ? 'selected' : ''}>📄 일반</option>
            <option value="api" ${category.id === 'api' ? 'selected' : ''}>🔌 API 문서</option>
            <option value="guide" ${category.id === 'guide' ? 'selected' : ''}>📚 가이드</option>
            <option value="spec" ${category.id === 'spec' ? 'selected' : ''}>📋 기술 스펙</option>
        </select>
        <button class="doc-delete-btn" data-filename="${doc.filename}" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; white-space: nowrap;">🗑️ 삭제</button>
    `;
}

/**
 * 모달의 문서 아이템 HTML 생성
 * @param {Object} doc - 문서 객체
 * @param {boolean} isSelected - 선택 여부
 * @returns {string} HTML 문자열
 */
export function createModalDocItemHTML(doc, isSelected) {
    const category = doc.category || { id: 'general', name: '일반', color: '#6366f1', icon: '📄' };

    return `
        <input type="checkbox" class="modal-doc-checkbox" ${isSelected ? 'checked' : ''}>
        <div class="modal-doc-info">
            <div class="modal-doc-name">
                <span>${category.icon}</span> ${doc.filename}
                <span style="background: ${category.color}20; color: ${category.color}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px;">${category.name}</span>
            </div>
            <div class="modal-doc-meta">
                <span>✂️ ${doc.chunk_count}개 청크</span>
                <span>📅 ${doc.added_at}</span>
                ${doc.method ? `<span style="background: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}20; color: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">${doc.method === 'semantic' ? '🧠 Semantic' : '📏 Fixed'}</span>` : ''}
                ${doc.embedding_model ? `<span style="background: #f59e0b20; color: #f59e0b; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">🤖 ${doc.embedding_model}</span>` : ''}
                <span style="display: none;">컬렉션: ${doc.collection}</span>
            </div>
        </div>
    `;
}

/**
 * 파일 목록 아이템 HTML 생성
 * @param {Object} file - 파일 객체
 * @param {boolean} isDuplicate - 중복 여부
 * @returns {string} HTML 문자열
 */
export function createFileItemHTML(file, isDuplicate) {
    const typeInfo = getFileTypeInfo(file.type);
    const currentCategory = file.category ? file.category.id : 'general';

    return `
        <input type="checkbox" class="file-checkbox" data-path="${file.path}" style="cursor: pointer;">
        <div class="file-info" style="flex: 1; min-width: 0;">
            <div class="file-name" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
                <span class="file-type-badge" style="background-color: ${typeInfo.color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; white-space: nowrap;">
                    ${typeInfo.icon} ${file.type}
                </span>
                ${isDuplicate ? '<span class="duplicate-badge" style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; white-space: nowrap;">⚠️ 이미 저장됨</span>' : ''}
                <span style="font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</span>
            </div>
            <div class="file-size" style="font-size: 0.875rem; color: #718096;">${formatBytes(file.size)}</div>
        </div>
        <select class="file-category-select" data-filename="${file.name}" style="padding: 6px 10px; border: 1px solid #cbd5e0; border-radius: 6px; font-size: 0.875rem; cursor: pointer; min-width: 120px;" onclick="event.stopPropagation();">
            <option value="general" ${currentCategory === 'general' ? 'selected' : ''}>📄 일반</option>
            <option value="api" ${currentCategory === 'api' ? 'selected' : ''}>🔌 API 문서</option>
            <option value="guide" ${currentCategory === 'guide' ? 'selected' : ''}>📚 가이드</option>
            <option value="spec" ${currentCategory === 'spec' ? 'selected' : ''}>📋 기술 스펙</option>
        </select>
        <button class="file-delete-btn" data-filename="${file.name}" title="파일 삭제" style="padding: 6px 12px; background: #ef4444; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem;">🗑️</button>
    `;
}

/**
 * 채팅 메시지 HTML 생성
 * @param {string} type - 메시지 타입 (question, answer)
 * @param {string} content - 메시지 내용
 * @returns {string} HTML 문자열
 */
export function createMessageHTML(type, content) {
    const timeStr = getFormattedTime();
    const avatar = type === 'question' ? '👤' : '🤖';

    return `
        <div class="message-avatar">${avatar}</div>
        <div class="message-wrapper">
            <div class="message-content">${content}</div>
            <div class="message-timestamp">${timeStr}</div>
        </div>
    `;
}

/**
 * 스트리밍 답변 컨테이너 HTML 생성
 * @returns {string} HTML 문자열
 */
export function createStreamingAnswerHTML() {
    const timeStr = getFormattedTime();

    return `
        <div class="message-avatar">🤖</div>
        <div class="message-wrapper">
            <div class="message-content"></div>
            <div class="message-timestamp">${timeStr}</div>
        </div>
    `;
}

/**
 * 품질 메타데이터 HTML 생성
 * @param {Object} metadata - 메타데이터 객체
 * @returns {string} HTML 문자열
 */
export function createMetadataHTML(metadata) {
    const qualityScore = metadata.quality_score || 0;
    const confidence = metadata.confidence || 'unknown';
    const processingTime = metadata.processing_time || 0;
    const hallucinationDetected = metadata.hallucination_detected || false;

    const confidenceColors = {
        'high': '#48bb78',
        'medium': '#ed8936',
        'low': '#f56565'
    };
    const confidenceColor = confidenceColors[confidence] || '#718096';

    // Query Transformation 정보
    const originalQuestion = metadata.original_question || '';
    const searchQueries = metadata.search_queries || [];
    const queryType = metadata.query_type || '';

    // RAG 기능 사용 여부
    const hybridSearchUsed = metadata.hybrid_search_used || false;
    const rerankScores = metadata.rerank_scores || null;

    // Self-RAG 검증 정보
    const selfRagVerification = metadata.self_rag_verification || {};
    const hasVerification = Object.keys(selfRagVerification).length > 0;

    // Query Transformation HTML
    let queryTransformHtml = '';
    if (searchQueries.length > 0 && searchQueries[0] !== originalQuestion) {
        queryTransformHtml = `
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

    // Self-RAG 검증 HTML
    let selfRagHtml = '';
    if (hasVerification) {
        const groundingScore = selfRagVerification.raw_scores?.grounding || 0;
        const completenessScore = selfRagVerification.raw_scores?.completeness || 0;
        const accuracyScore = selfRagVerification.raw_scores?.accuracy || 0;
        const hasHallucination = selfRagVerification.has_hallucination || false;
        const feedback = selfRagVerification.feedback || '';

        selfRagHtml = `
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

    // Qwen Reranker 정보 HTML
    let rerankHtml = '';
    if (rerankScores && rerankScores.length > 0) {
        const maxScore = Math.max(...rerankScores);
        const minScore = Math.min(...rerankScores);
        const avgScore = rerankScores.reduce((a, b) => a + b, 0) / rerankScores.length;

        rerankHtml = `
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

    // RAG 기능 사용 여부 HTML
    const ragFeaturesHtml = `
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

    // 품질 정보 HTML (품질 점수, 신뢰도 제거)
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
                        ${hallucinationDetected ? `
                            <div class="metric" style="margin-top: 8px; padding: 8px; background: #fff5f5; border-left: 3px solid #f56565; border-radius: 4px;">
                                <span class="metric-label" style="color: #c53030">⚠️ 할루시네이션 경고:</span>
                                <span class="metric-value" style="color: #c53030; font-weight: 600">답변에 문서에 없는 정보가 포함되었을 수 있습니다</span>
                            </div>
                        ` : ''}
                    </div>
                    ${queryTransformHtml}
                    ${rerankHtml}
                    ${selfRagHtml}
                    ${ragFeaturesHtml}
                </div>
            </div>
        </details>
    `;

    return qualityHtml;
}

/**
 * 참조 문서 HTML 생성
 * @param {Array} sources - 소스 배열
 * @returns {string} HTML 문자열
 */
export function createSourcesHTML(sources) {
    if (!sources || sources.length === 0) return '';

    return `
        <details class="metadata-toggle">
            <summary>📑 참조 문서 (${sources.length}개)</summary>
            <div class="metadata-content">
                <div class="sources">
                    ${sources.map((source, idx) => `
                        <div class="source-item">
                            <div class="source-file">[${idx + 1}] ${source.source}</div>
                            <div class="source-content">${source.content}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </details>
    `;
}

/**
 * 청크 미리보기 HTML 생성
 * @param {Object} data - 청크 데이터
 * @returns {string} HTML 문자열
 */
export function createChunkPreviewHTML(data) {
    let html = `
        <div style="margin-bottom: 12px; font-weight: 600; color: #334155;">
            📊 총 ${data.total_chunks}개 청크 중 ${data.preview_chunks.length}개 미리보기
        </div>
    `;

    data.preview_chunks.forEach((chunk) => {
        const truncatedContent = chunk.content.length > 200
            ? chunk.content.substring(0, 200) + '...'
            : chunk.content;

        html += `
            <div style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 4px; border-left: 3px solid #6366f1;">
                <div style="margin-bottom: 6px; font-size: 0.8125rem; color: #64748b;">
                    <strong>청크 #${chunk.chunk_index + 1}</strong> (${chunk.length}자)
                </div>
                <div style="font-size: 0.875rem; color: #334155; line-height: 1.6; white-space: pre-wrap;">${truncatedContent}</div>
            </div>
        `;
    });

    return html;
}

/**
 * 청크 모달 HTML 생성
 * @returns {string} HTML 문자열
 */
export function createChunksModalHTML() {
    return `
        <div style="background: white; border-radius: 12px; max-width: 900px; width: 90%; max-height: 90vh; display: flex; flex-direction: column; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);">
            <div style="padding: 24px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0; font-size: 1.25rem; color: #1e293b;">청크 전체 보기</h2>
                    <p id="chunks-modal-filename" style="margin: 8px 0 0 0; font-size: 0.875rem; color: #64748b;"></p>
                </div>
                <button onclick="closeChunksModal()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 4px;">✕</button>
            </div>
            <div id="chunks-modal-content" style="flex: 1; overflow-y: auto; padding: 24px;"></div>
            <div id="chunks-modal-pagination" style="padding: 16px 24px; border-top: 1px solid #e2e8f0; display: flex; justify-content: center; gap: 8px; align-items: center;"></div>
        </div>
    `;
}

/**
 * 활성 문서 모달 목록 HTML 생성
 * @param {Array} documents - 문서 배열
 * @returns {string} HTML 문자열
 */
export function createActiveDocsListHTML(documents) {
    if (!documents || documents.length === 0) {
        return `
            <div style="text-align: center; padding: 2rem; color: #94a3b8;">
                활성화된 문서가 없습니다
            </div>
        `;
    }

    // 카테고리별로 그룹화
    const categoryGroups = {};
    documents.forEach(doc => {
        const catId = doc.category.id;
        if (!categoryGroups[catId]) {
            categoryGroups[catId] = {
                category: doc.category,
                docs: []
            };
        }
        categoryGroups[catId].docs.push(doc);
    });

    // HTML 생성
    let html = `<div style="color: #64748b; margin-bottom: 1rem; font-size: 0.9rem;">총 ${documents.length}개 문서가 활성화되어 있습니다</div>`;

    Object.values(categoryGroups).forEach(group => {
        html += `
            <div style="margin-bottom: 1.5rem;">
                <div style="font-weight: 600; margin-bottom: 0.5rem; color: ${group.category.color};">
                    ${group.category.icon} ${group.category.name} (${group.docs.length}개)
                </div>
                <ul style="list-style: none; padding: 0; margin: 0;">
        `;

        group.docs.forEach(doc => {
            html += `
                <li style="padding: 0.5rem; margin: 0.25rem 0; background: #f8fafc; border-radius: 4px; font-size: 0.9rem;">
                    📄 ${doc.filename}
                </li>
            `;
        });

        html += `</ul></div>`;
    });

    return html;
}

/**
 * 빈 상태 HTML 생성
 * @param {string} icon - 아이콘
 * @param {string} message - 메시지
 * @param {string} hint - 힌트 (선택적)
 * @returns {string} HTML 문자열
 */
export function createEmptyStateHTML(icon, message, hint = '') {
    return `
        <div class="empty-state">
            <div class="empty-icon">${icon}</div>
            <p>${message}</p>
            ${hint ? `<p style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.5rem;">${hint}</p>` : ''}
        </div>
    `;
}

/**
 * 환영 메시지 HTML 생성
 * @returns {string} HTML 문자열
 */
export function createWelcomeMessageHTML() {
    return `
        <div class="welcome-message">
            <div class="welcome-icon">👋</div>
            <h2>안녕하세요!</h2>
            <p>문서를 기반으로 질문에 답변해드립니다.</p>
            <p class="welcome-hint">먼저 <strong>"활성화 문서 변경"</strong> 버튼으로 문서를 활성화해주세요.</p>
        </div>
    `;
}
