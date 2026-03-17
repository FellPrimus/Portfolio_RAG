// ===================================================================
// 청크 전체 보기 모달 모듈
// 문서의 모든 청크를 페이지네이션으로 조회
// ===================================================================

import { state, setChunksData, setCurrentPage } from '../../state.js';

/**
 * 청크 모달 열기
 * @param {string} filename - 파일명
 * @param {string} collection - 컬렉션 ID
 * @param {number} totalChunks - 총 청크 수
 */
export async function openChunksModal(filename, collection, totalChunks) {
    setChunksData(filename, collection, totalChunks);
    setCurrentPage(1);

    // 모달 생성 (없으면)
    let modal = document.getElementById('chunks-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'chunks-modal';
        modal.style.cssText = `
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 10000;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
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

        document.body.appendChild(modal);
    }

    // 모달 표시
    modal.style.display = 'flex';
    document.getElementById('chunks-modal-filename').textContent = filename;

    // 첫 페이지 로드
    await loadChunksPage(1);
}

/**
 * 청크 모달 닫기
 */
export function closeChunksModal() {
    const modal = document.getElementById('chunks-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * 청크 페이지 로드
 * @param {number} page - 페이지 번호
 */
export async function loadChunksPage(page) {
    const content = document.getElementById('chunks-modal-content');
    const pagination = document.getElementById('chunks-modal-pagination');

    try {
        content.innerHTML = '<div style="text-align: center; color: #64748b; padding: 2rem;">로딩 중...</div>';

        const { filename, collection } = state.currentChunksData;
        const response = await fetch(`api/documents/${encodeURIComponent(filename)}/chunks?collection=${encodeURIComponent(collection)}&page=${page}&per_page=${state.pagination.perPage}`);
        const data = await response.json();

        if (!data.success) {
            content.innerHTML = `<div style="color: #ef4444;">오류: ${data.error}</div>`;
            return;
        }

        // 청크 목록 렌더링
        let chunksHTML = '';
        data.chunks.forEach((chunk) => {
            chunksHTML += `
                <div style="margin-bottom: 16px; padding: 16px; background: #f8fafc; border-radius: 6px; border-left: 4px solid #6366f1;">
                    <div style="margin-bottom: 8px; font-size: 0.875rem; color: #64748b; display: flex; justify-content: space-between;">
                        <strong>청크 #${chunk.chunk_index + 1}</strong>
                        <span>${chunk.length}자</span>
                    </div>
                    <div style="font-size: 0.9375rem; color: #334155; line-height: 1.7; white-space: pre-wrap;">${chunk.content}</div>
                </div>
            `;
        });

        content.innerHTML = chunksHTML;

        // 페이지네이션 렌더링
        const totalPages = data.total_pages;
        state.pagination.currentPage = data.current_page;

        let paginationHTML = '';

        // 이전 버튼
        if (state.pagination.currentPage > 1) {
            paginationHTML += `<button onclick="loadChunksPage(${state.pagination.currentPage - 1})" style="padding: 8px 12px; background: #6366f1; color: white; border: none; border-radius: 4px; cursor: pointer;">← 이전</button>`;
        }

        // 페이지 번호 표시
        const startPage = Math.max(1, state.pagination.currentPage - 2);
        const endPage = Math.min(totalPages, state.pagination.currentPage + 2);

        for (let i = startPage; i <= endPage; i++) {
            const active = i === state.pagination.currentPage ? 'background: #6366f1; color: white;' : 'background: #f1f5f9; color: #334155;';
            paginationHTML += `<button onclick="loadChunksPage(${i})" style="padding: 8px 12px; ${active} border: none; border-radius: 4px; cursor: pointer; min-width: 40px;">${i}</button>`;
        }

        // 다음 버튼
        if (state.pagination.currentPage < totalPages) {
            paginationHTML += `<button onclick="loadChunksPage(${state.pagination.currentPage + 1})" style="padding: 8px 12px; background: #6366f1; color: white; border: none; border-radius: 4px; cursor: pointer;">다음 →</button>`;
        }

        pagination.innerHTML = paginationHTML;

    } catch (error) {
        console.error('청크 로드 실패:', error);
        content.innerHTML = `<div style="color: #ef4444;">청크 로드 실패: ${error.message}</div>`;
    }
}

// 전역 함수로 노출
window.openChunksModal = openChunksModal;
window.closeChunksModal = closeChunksModal;
window.loadChunksPage = loadChunksPage;
