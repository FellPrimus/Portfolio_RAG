// ===================================================================
// 활성화된 문서 목록 모달 모듈
// 현재 질의응답에 활성화된 문서 목록을 표시
// ===================================================================

/**
 * 활성화된 문서 목록 모달 열기
 */
export async function showActiveDocumentsModal() {
    const modal = document.getElementById('active-documents-modal');
    const listContainer = document.getElementById('active-docs-modal-list');

    try {
        const response = await fetch('api/documents/loaded');
        const data = await response.json();

        if (!data.success) {
            alert('활성화된 문서 목록을 가져올 수 없습니다.');
            return;
        }

        if (data.documents && data.documents.length > 0) {
            // 카테고리별로 그룹화
            const categoryGroups = {};
            data.documents.forEach(doc => {
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
            let html = `<div style="color: #64748b; margin-bottom: 1rem; font-size: 0.9rem;">총 ${data.documents.length}개 문서가 활성화되어 있습니다</div>`;

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

            listContainer.innerHTML = html;
        } else {
            listContainer.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: #94a3b8;">
                    활성화된 문서가 없습니다
                </div>
            `;
        }

        modal.style.display = 'flex';
    } catch (error) {
        console.error('활성화된 문서 목록 로드 실패:', error);
        alert('활성화된 문서 목록을 가져오는데 실패했습니다.');
    }
}

/**
 * 활성화된 문서 목록 모달 닫기
 */
export function closeActiveDocumentsModal() {
    const modal = document.getElementById('active-documents-modal');
    modal.style.display = 'none';
}

// 전역 함수로 노출
window.showActiveDocumentsModal = showActiveDocumentsModal;
window.closeActiveDocumentsModal = closeActiveDocumentsModal;
