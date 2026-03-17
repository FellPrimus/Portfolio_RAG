// ===================================================================
// 텍스트 직접 입력 모듈
// 텍스트를 입력받아 의미 기준 청킹 후 벡터DB에 저장
// ===================================================================

import { showLoading, hideLoading } from '../../utils.js';

/**
 * 텍스트 입력 초기화
 */
export function initTextInput() {
    const textContent = document.getElementById('text-content');
    const saveBtn = document.getElementById('text-save-btn');

    // 실시간 글자 수 표시
    textContent?.addEventListener('input', updateTextStats);

    // 저장 버튼
    saveBtn?.addEventListener('click', saveTextToVectorDB);

    // 카테고리 목록 로드
    loadCategoriesForTextInput();
}

/**
 * 텍스트 통계 업데이트
 */
function updateTextStats() {
    const textContent = document.getElementById('text-content');
    const charCount = document.getElementById('text-char-count');

    const length = textContent.value.length;
    charCount.textContent = `${length.toLocaleString()}자 입력됨`;
}

/**
 * 카테고리 목록 로드
 */
async function loadCategoriesForTextInput() {
    try {
        const response = await fetch('api/categories');
        const data = await response.json();

        const select = document.getElementById('text-category');
        if (select && data.success) {
            select.innerHTML = data.categories
                .map(cat => `<option value="${cat.id}">${cat.icon} ${cat.name}</option>`)
                .join('');
        }
    } catch (error) {
        console.error('카테고리 로드 실패:', error);
    }
}

/**
 * 벡터DB에 저장
 */
async function saveTextToVectorDB() {
    const title = document.getElementById('text-doc-title').value.trim();
    const content = document.getElementById('text-content').value.trim();
    const categoryId = document.getElementById('text-category').value;

    // 유효성 검사
    if (!title) {
        alert('문서 제목을 입력해주세요.');
        document.getElementById('text-doc-title').focus();
        return;
    }

    if (!content) {
        alert('텍스트를 입력해주세요.');
        document.getElementById('text-content').focus();
        return;
    }

    if (content.length < 50) {
        alert('텍스트가 너무 짧습니다. 최소 50자 이상 입력해주세요.');
        return;
    }

    showLoading('벡터DB에 저장 중...');

    try {
        const response = await fetch('api/documents/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                content,
                category_id: categoryId
            })
        });

        const data = await response.json();
        hideLoading();

        if (data.success) {
            alert(`저장 완료!\n\n문서: ${title}\n청크: ${data.chunk_count}개\n청킹: 의미 기준`);

            // 입력 필드 초기화
            document.getElementById('text-doc-title').value = '';
            document.getElementById('text-content').value = '';
            updateTextStats();
        } else {
            alert(`저장 실패: ${data.error}`);
        }
    } catch (error) {
        hideLoading();
        alert(`오류: ${error.message}`);
    }
}
