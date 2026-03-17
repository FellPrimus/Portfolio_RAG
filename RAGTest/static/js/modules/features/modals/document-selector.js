// ===================================================================
// 문서 선택 모달 모듈 (폴더 구조 지원)
// 질의응답 탭에서 활성화할 문서를 선택하는 모달
// 폴더 네비게이션을 통해 계층적으로 문서 탐색
// ===================================================================

import { state, clearModalSelections } from '../../state.js';
import { showLoading, hideLoading } from '../../utils.js';

/**
 * 활성 문서 표시 업데이트 콜백
 * @type {Function|null}
 */
let onDocumentsActivatedCallback = null;

// ==================== 폴더 네비게이션 상태 ====================

/**
 * 현재 보고 있는 폴더 ID (null = 루트)
 * @type {string|null}
 */
let currentModalFolderId = null;

/**
 * 브레드크럼용 경로
 * @type {Array<{id: string|null, name: string}>}
 */
let modalFolderPath = [{ id: null, name: '전체 문서' }];

/**
 * 폴더 데이터 캐시
 * @type {Array}
 */
let modalFoldersCache = [];

/**
 * 문서 활성화 후 콜백 설정
 * @param {Function} callback - 문서 활성화 후 호출될 콜백
 */
export function setDocumentsActivatedCallback(callback) {
    onDocumentsActivatedCallback = callback;
}

/**
 * 문서 선택 모달 열기
 */
export async function openDocumentSelector() {
    console.log('[DEBUG] openDocumentSelector() 호출됨');

    const modal = document.getElementById('document-selector-modal');
    modal.style.display = 'flex';

    // 상태 초기화
    currentModalFolderId = null;
    modalFolderPath = [{ id: null, name: '전체 문서' }];

    // 폴더 데이터 로드
    await loadModalFoldersData();

    // 문서 목록 로드
    await loadModalDocuments();

    // 브레드크럼 렌더링
    renderModalBreadcrumb();

    // 폴더 + 문서 렌더링
    renderModalFolderContents();

    // 검색 이벤트 리스너
    const searchInput = document.getElementById('modal-doc-search');
    searchInput.value = '';
    searchInput.removeEventListener('input', filterModalDocuments);
    searchInput.addEventListener('input', filterModalDocuments);

    // 전체 선택/해제 버튼
    const selectAllBtn = document.getElementById('modal-select-all');
    const clearAllBtn = document.getElementById('modal-clear-all');
    const activateBtn = document.getElementById('modal-activate-btn');

    selectAllBtn.replaceWith(selectAllBtn.cloneNode(true));
    clearAllBtn.replaceWith(clearAllBtn.cloneNode(true));
    activateBtn.replaceWith(activateBtn.cloneNode(true));

    document.getElementById('modal-select-all').addEventListener('click', selectAllModalDocs);
    document.getElementById('modal-clear-all').addEventListener('click', clearAllModalDocs);
    document.getElementById('modal-activate-btn').addEventListener('click', activateSelectedDocuments);
}

/**
 * 문서 선택 모달 닫기
 */
export function closeDocumentSelector() {
    const modal = document.getElementById('document-selector-modal');
    modal.style.display = 'none';
    state.selectedDocsInModal.clear();
    updateModalSelectedCount();
}

// ==================== 폴더 데이터 관리 ====================

/**
 * 폴더 데이터 로드
 */
async function loadModalFoldersData() {
    try {
        const response = await fetch('api/folders');
        const data = await response.json();

        if (data.success) {
            modalFoldersCache = data.folders;
        }
    } catch (error) {
        console.error('폴더 데이터 로드 실패:', error);
        modalFoldersCache = [];
    }
}

/**
 * 폴더 ID로 폴더 정보 찾기 (재귀)
 * @param {string} folderId - 폴더 ID
 * @param {Array} folders - 검색할 폴더 배열
 * @returns {Object|null}
 */
function findModalFolderById(folderId, folders = modalFoldersCache) {
    for (const folder of folders) {
        if (folder.id === folderId) {
            return folder;
        }
        if (folder.children_data && folder.children_data.length > 0) {
            const found = findModalFolderById(folderId, folder.children_data);
            if (found) return found;
        }
    }
    return null;
}

/**
 * 현재 폴더의 하위 폴더 목록 가져오기
 * @returns {Array}
 */
function getModalCurrentSubfolders() {
    if (currentModalFolderId === null) {
        return modalFoldersCache;
    }

    const currentFolder = findModalFolderById(currentModalFolderId);
    if (currentFolder && currentFolder.children_data) {
        return currentFolder.children_data;
    }
    return [];
}

/**
 * 현재 폴더의 문서 목록 가져오기
 * @returns {Array}
 */
function getModalCurrentFolderDocuments() {
    if (currentModalFolderId === null) {
        // 루트: 폴더에 속하지 않은 문서들
        const allDocsInFolders = getModalAllDocsInFolders();
        return state.allDocsInModal.filter(doc => !allDocsInFolders.includes(doc.filename));
    }

    const currentFolder = findModalFolderById(currentModalFolderId);
    if (currentFolder && currentFolder.documents) {
        return state.allDocsInModal.filter(doc => currentFolder.documents.includes(doc.filename));
    }
    return [];
}

/**
 * 모든 폴더에 속한 문서 ID 조회
 * @returns {string[]}
 */
function getModalAllDocsInFolders() {
    const allDocs = [];
    const collectDocs = (folders) => {
        for (const folder of folders) {
            if (folder.documents) {
                allDocs.push(...folder.documents);
            }
            if (folder.children_data) {
                collectDocs(folder.children_data);
            }
        }
    };
    collectDocs(modalFoldersCache);
    return allDocs;
}

// ==================== 폴더 네비게이션 ====================

/**
 * 폴더로 이동
 * @param {string|null} folderId - 이동할 폴더 ID (null = 루트)
 */
async function navigateToModalFolder(folderId) {
    currentModalFolderId = folderId;

    // 브레드크럼 경로 업데이트
    if (folderId === null) {
        modalFolderPath = [{ id: null, name: '전체 문서' }];
    } else {
        try {
            const response = await fetch(`/api/folders/${folderId}/path`);
            const data = await response.json();

            if (data.success && data.path) {
                modalFolderPath = [{ id: null, name: '전체 문서' }, ...data.path];
            }
        } catch (error) {
            console.error('폴더 경로 조회 실패:', error);
        }
    }

    // 폴더 데이터 새로고침 후 렌더링
    await loadModalFoldersData();
    renderModalBreadcrumb();
    renderModalFolderContents();
}

/**
 * 상위 폴더로 이동
 */
function navigateToModalParent() {
    if (modalFolderPath.length > 1) {
        const parentPath = modalFolderPath[modalFolderPath.length - 2];
        navigateToModalFolder(parentPath.id);
    }
}

// ==================== 브레드크럼 렌더링 ====================

/**
 * 브레드크럼 렌더링
 */
function renderModalBreadcrumb() {
    const container = document.getElementById('modal-folder-breadcrumb');
    if (!container) return;

    container.innerHTML = '';

    modalFolderPath.forEach((item, index) => {
        // 구분자 추가 (첫 번째 항목 제외)
        if (index > 0) {
            const separator = document.createElement('span');
            separator.className = 'breadcrumb-separator';
            separator.textContent = '›';
            container.appendChild(separator);
        }

        // 브레드크럼 항목
        const breadcrumbItem = document.createElement('span');
        breadcrumbItem.className = 'breadcrumb-item';
        breadcrumbItem.dataset.folderId = item.id || '';

        // 마지막 항목은 active
        if (index === modalFolderPath.length - 1) {
            breadcrumbItem.classList.add('active');
            breadcrumbItem.textContent = `📍 ${item.name}`;
        } else {
            breadcrumbItem.textContent = item.name;
            breadcrumbItem.addEventListener('click', () => navigateToModalFolder(item.id));
        }

        container.appendChild(breadcrumbItem);
    });
}

// ==================== 모달 문서 목록 ====================

/**
 * 모달 문서 목록 로드
 */
async function loadModalDocuments() {
    try {
        const response = await fetch('api/documents');
        const data = await response.json();

        if (data.success && data.documents.length > 0) {
            state.allDocsInModal = data.documents;
        } else {
            state.allDocsInModal = [];
        }
    } catch (error) {
        console.error('문서 목록 로드 실패:', error);
        state.allDocsInModal = [];
    }
}

/**
 * 폴더 컨텐츠 렌더링 (폴더 + 문서 통합)
 */
function renderModalFolderContents() {
    const modalDocsList = document.getElementById('modal-docs-list');
    if (!modalDocsList) return;

    const subfolders = getModalCurrentSubfolders();
    const documents = getModalCurrentFolderDocuments();

    // 빈 상태 체크
    if (subfolders.length === 0 && documents.length === 0 && state.allDocsInModal.length === 0) {
        modalDocsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <p>벡터DB에 문서가 없습니다</p>
                <p style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.5rem;">
                    먼저 문서 준비 탭에서 문서를 추가해주세요
                </p>
            </div>
        `;
        return;
    }

    modalDocsList.innerHTML = '';

    // 상위 폴더로 이동 행 (루트가 아닌 경우)
    if (currentModalFolderId !== null) {
        const parentItem = createModalParentFolderItem();
        modalDocsList.appendChild(parentItem);
    }

    // 폴더 행들 렌더링
    subfolders.forEach(folder => {
        const folderItem = createModalFolderItem(folder);
        modalDocsList.appendChild(folderItem);
    });

    // 문서 행들 렌더링
    documents.forEach(doc => {
        const docItem = createModalDocumentItem(doc);
        modalDocsList.appendChild(docItem);
    });

    // 빈 폴더 상태
    if (currentModalFolderId !== null && subfolders.length === 0 && documents.length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <div class="empty-icon">📂</div>
            <p>이 폴더는 비어 있습니다</p>
        `;
        modalDocsList.appendChild(emptyState);
    }

    updateModalSelectedCount();
}

/**
 * 상위 폴더 이동 항목 생성
 * @returns {HTMLElement}
 */
function createModalParentFolderItem() {
    const item = document.createElement('div');
    item.className = 'modal-folder-item modal-parent-folder';

    item.innerHTML = `
        <div class="folder-icon">📁</div>
        <div class="folder-info">
            <div class="folder-name">.. (상위 폴더)</div>
        </div>
    `;

    item.addEventListener('click', () => navigateToModalParent());

    return item;
}

/**
 * 폴더 항목 생성
 * @param {Object} folder - 폴더 데이터
 * @returns {HTMLElement}
 */
function createModalFolderItem(folder) {
    const item = document.createElement('div');
    item.className = 'modal-folder-item';
    item.dataset.folderId = folder.id;

    // 아이콘 결정
    let folderIcon = '📁';
    if (folder.icon === 'cloud') folderIcon = '☁️';
    else if (folder.icon === 'building') folderIcon = '🏢';
    else if (folder.icon === 'landmark') folderIcon = '🏛️';
    else if (folder.children_data && folder.children_data.length > 0) folderIcon = '📂';

    // 폴더 내 총 문서 수 계산 (하위 폴더 포함)
    const docCount = countDocsInFolder(folder);

    // 폴더 선택 상태 계산
    const selectionState = calculateFolderSelectionState(folder);

    item.style.borderLeftColor = folder.color || '#6366f1';

    item.innerHTML = `
        <input type="checkbox" class="modal-folder-checkbox" data-folder-id="${folder.id}"
            ${selectionState === 'all' ? 'checked' : ''}>
        <div class="folder-icon">${folderIcon}</div>
        <div class="folder-info">
            <div class="folder-name">${folder.name}</div>
            <div class="folder-meta">${docCount}개 문서</div>
        </div>
        ${folder.is_system ? '<span class="folder-badge">시스템</span>' : ''}
        <div class="folder-nav-arrow">›</div>
    `;

    // 체크박스 indeterminate 상태 설정
    const checkbox = item.querySelector('.modal-folder-checkbox');
    if (selectionState === 'partial') {
        checkbox.indeterminate = true;
    }

    // 체크박스 클릭 이벤트 (이벤트 버블링 방지)
    checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
        handleFolderCheckboxChange(folder, e.target.checked);
    });

    // 폴더 영역 클릭 -> 네비게이션 (체크박스 제외)
    item.addEventListener('click', (e) => {
        if (!e.target.classList.contains('modal-folder-checkbox')) {
            navigateToModalFolder(folder.id);
        }
    });

    return item;
}

/**
 * 폴더 내 문서 수 계산 (하위 폴더 포함)
 * @param {Object} folder - 폴더 객체
 * @returns {number}
 */
function countDocsInFolder(folder) {
    let count = folder.documents ? folder.documents.length : 0;
    if (folder.children_data) {
        folder.children_data.forEach(child => {
            count += countDocsInFolder(child);
        });
    }
    return count;
}

// ==================== 폴더 선택 헬퍼 함수 ====================

/**
 * 폴더와 모든 하위 폴더의 문서 filename 수집
 * @param {Object} folder - 폴더 객체
 * @returns {string[]} filename 배열 (고유 식별자)
 */
function collectAllDocumentsInFolder(folder) {
    const filenames = [];

    // 현재 폴더의 문서들
    if (folder.documents && folder.documents.length > 0) {
        folder.documents.forEach(docId => {
            // filename 또는 collection으로 매칭 시도
            const doc = state.allDocsInModal.find(d =>
                d.filename === docId || d.collection === docId
            );
            if (doc) {
                filenames.push(doc.filename);
            }
        });
    }

    // 하위 폴더의 문서들 (재귀)
    if (folder.children_data && folder.children_data.length > 0) {
        folder.children_data.forEach(child => {
            filenames.push(...collectAllDocumentsInFolder(child));
        });
    }

    return filenames;
}

/**
 * 폴더 선택 상태 계산
 * @param {Object} folder - 폴더 객체
 * @returns {'all' | 'partial' | 'none'} 선택 상태
 */
function calculateFolderSelectionState(folder) {
    const allFilenames = collectAllDocumentsInFolder(folder);

    if (allFilenames.length === 0) {
        return 'none';
    }

    const selectedCount = allFilenames.filter(filename => state.selectedDocsInModal.has(filename)).length;

    if (selectedCount === 0) {
        return 'none';
    } else if (selectedCount === allFilenames.length) {
        return 'all';
    } else {
        return 'partial';
    }
}

/**
 * 폴더 체크박스 변경 핸들러
 * @param {Object} folder - 폴더 객체
 * @param {boolean} isChecked - 체크 상태
 */
function handleFolderCheckboxChange(folder, isChecked) {
    const allFilenames = collectAllDocumentsInFolder(folder);

    if (isChecked) {
        // 폴더 내 모든 문서 선택
        allFilenames.forEach(filename => {
            state.selectedDocsInModal.add(filename);
        });
    } else {
        // 폴더 내 모든 문서 선택 해제
        allFilenames.forEach(filename => {
            state.selectedDocsInModal.delete(filename);
        });
    }

    // UI 동기화
    updateDocumentCheckboxStates();
    updateFolderCheckboxStates();
    updateModalSelectedCount();
}

/**
 * 모든 폴더 체크박스 상태 동기화
 */
function updateFolderCheckboxStates() {
    const folderCheckboxes = document.querySelectorAll('.modal-folder-checkbox');

    folderCheckboxes.forEach(checkbox => {
        const folderId = checkbox.dataset.folderId;
        const folder = findModalFolderById(folderId);

        if (folder) {
            const selectionState = calculateFolderSelectionState(folder);

            checkbox.checked = selectionState === 'all';
            checkbox.indeterminate = selectionState === 'partial';
        }
    });
}

/**
 * 모든 문서 체크박스 상태 동기화
 */
function updateDocumentCheckboxStates() {
    const docItems = document.querySelectorAll('.modal-doc-item');

    docItems.forEach(item => {
        const filename = item.dataset.filename;
        const checkbox = item.querySelector('.modal-doc-checkbox');
        const isSelected = state.selectedDocsInModal.has(filename);

        if (checkbox) {
            checkbox.checked = isSelected;
        }

        if (isSelected) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
}

/**
 * 문서 항목 생성
 * @param {Object} doc - 문서 데이터
 * @returns {HTMLElement}
 */
function createModalDocumentItem(doc) {
    const docItem = document.createElement('div');
    docItem.className = 'modal-doc-item';
    docItem.dataset.collection = doc.collection;
    docItem.dataset.filename = doc.filename;

    // filename을 고유 식별자로 사용 (collection은 웹 크롤링 문서들이 공유함)
    const isSelected = state.selectedDocsInModal.has(doc.filename);
    if (isSelected) docItem.classList.add('selected');

    // 카테고리 정보
    const category = doc.category || { id: 'general', name: '일반', color: '#6366f1', icon: '📄' };

    docItem.dataset.categoryId = category.id;
    docItem.dataset.categoryName = category.name;
    docItem.dataset.categoryIcon = category.icon;

    docItem.style.cssText = `border-left: 4px solid ${category.color};`;

    // 표시 이름: title이 있으면 title 사용, 없으면 filename 사용
    const displayName = doc.title || doc.filename;

    docItem.innerHTML = `
        <input type="checkbox" class="modal-doc-checkbox" ${isSelected ? 'checked' : ''}>
        <div class="modal-doc-info">
            <div class="modal-doc-name" title="${doc.filename}">
                <span>${category.icon}</span> ${displayName}
                <span style="background: ${category.color}20; color: ${category.color}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px;">${category.name}</span>
            </div>
            <div class="modal-doc-meta">
                <span>✂️ ${doc.chunk_count}개 청크</span>
                <span>📅 ${doc.added_at}</span>
                ${doc.method ? `<span style="background: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}20; color: ${doc.method === 'semantic' ? '#10b981' : '#6366f1'}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">${doc.method === 'semantic' ? '🧠 Semantic' : '📏 Fixed'}</span>` : ''}
            </div>
        </div>
    `;

    // 클릭 이벤트 - filename을 식별자로 사용
    docItem.addEventListener('click', () => {
        const checkbox = docItem.querySelector('.modal-doc-checkbox');
        checkbox.checked = !checkbox.checked;
        toggleDocumentSelection(doc.filename, checkbox.checked, docItem);
    });

    // 체크박스 직접 클릭
    const checkbox = docItem.querySelector('.modal-doc-checkbox');
    checkbox.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDocumentSelection(doc.filename, e.target.checked, docItem);
    });

    return docItem;
}

/**
 * 문서 선택 토글
 * @param {string} filename - 문서 filename (고유 식별자)
 * @param {boolean} isChecked - 체크 상태
 * @param {HTMLElement} docItem - 문서 아이템 요소
 */
function toggleDocumentSelection(filename, isChecked, docItem) {
    if (isChecked) {
        state.selectedDocsInModal.add(filename);
        docItem.classList.add('selected');
    } else {
        state.selectedDocsInModal.delete(filename);
        docItem.classList.remove('selected');
    }
    updateModalSelectedCount();
    // 폴더 체크박스 상태 동기화
    updateFolderCheckboxStates();
}

/**
 * 선택된 문서 수 업데이트
 */
function updateModalSelectedCount() {
    const countElement = document.getElementById('modal-selected-count');
    countElement.textContent = state.selectedDocsInModal.size;
}

/**
 * 모달 문서 필터링 (검색)
 * @param {Event} e - 입력 이벤트
 */
function filterModalDocuments(e) {
    const searchTerm = e.target.value.toLowerCase().trim();

    if (!searchTerm) {
        renderModalFolderContents();
        return;
    }

    // 전체 문서에서 검색 (filename, collection, title 포함)
    const filteredDocs = state.allDocsInModal.filter(doc =>
        doc.filename.toLowerCase().includes(searchTerm) ||
        doc.collection.toLowerCase().includes(searchTerm) ||
        (doc.title && doc.title.toLowerCase().includes(searchTerm))
    );

    renderFilteredModalDocuments(filteredDocs, searchTerm);
}

/**
 * 필터된 문서 렌더링
 * @param {Array} documents - 필터된 문서 목록
 * @param {string} searchTerm - 검색어
 */
function renderFilteredModalDocuments(documents, searchTerm) {
    const modalDocsList = document.getElementById('modal-docs-list');

    if (documents.length === 0) {
        modalDocsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <p>"${searchTerm}"에 대한 검색 결과가 없습니다</p>
            </div>
        `;
        return;
    }

    modalDocsList.innerHTML = '';

    documents.forEach(doc => {
        const docItem = createModalDocumentItem(doc);
        modalDocsList.appendChild(docItem);
    });

    updateModalSelectedCount();
}

/**
 * 모든 문서 선택 (현재 폴더 + 하위 폴더)
 */
function selectAllModalDocs() {
    const checkboxes = document.querySelectorAll('.modal-doc-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
        const docItem = checkbox.closest('.modal-doc-item');
        const filename = docItem.dataset.filename;
        state.selectedDocsInModal.add(filename);
        docItem.classList.add('selected');
    });
    updateModalSelectedCount();
    // 폴더 체크박스 상태 동기화
    updateFolderCheckboxStates();
}

/**
 * 모든 문서 선택 해제
 */
function clearAllModalDocs() {
    const checkboxes = document.querySelectorAll('.modal-doc-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        const docItem = checkbox.closest('.modal-doc-item');
        docItem.classList.remove('selected');
    });
    state.selectedDocsInModal.clear();
    updateModalSelectedCount();
    // 폴더 체크박스 상태 동기화
    updateFolderCheckboxStates();
}

/**
 * 선택된 문서 활성화
 */
async function activateSelectedDocuments() {
    if (state.selectedDocsInModal.size === 0) {
        alert('활성화할 문서를 선택해주세요.');
        return;
    }

    // 선택된 filename들로부터 고유한 collection ID들 추출
    const selectedFilenames = Array.from(state.selectedDocsInModal);
    const collections = new Set();

    selectedFilenames.forEach(filename => {
        const doc = state.allDocsInModal.find(d => d.filename === filename);
        if (doc) {
            collections.add(doc.collection);
        }
    });

    const uniqueCollections = Array.from(collections);
    const selectedFileCount = selectedFilenames.length;

    console.log('[DEBUG] 선택된 파일 수:', selectedFileCount);
    console.log('[DEBUG] 선택된 파일들:', selectedFilenames);
    console.log('[DEBUG] 활성화할 컬렉션들:', uniqueCollections);

    closeDocumentSelector();
    showLoading(`${selectedFileCount}개 문서 활성화 중...`);

    try {
        const response = await fetch('api/documents/load-multiple-collections', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                collections: uniqueCollections,
                filenames: selectedFilenames  // 선택된 파일명 목록 전달
            })
        });

        const data = await response.json();

        if (data.success) {
            hideLoading();

            // 질의응답 활성화
            state.isReady = true;
            document.getElementById('question-input').disabled = false;
            document.getElementById('ask-btn').disabled = false;

            // 활성 문서 표시 업데이트 콜백 호출
            if (onDocumentsActivatedCallback) {
                await onDocumentsActivatedCallback();
            }

            const failedMessage = data.failed > 0 ? `\n⚠️ 실패: ${data.failed}개` : '';
            alert(`✅ 문서가 활성화되었습니다!\n\n📊 로드 성공: ${data.loaded}개${failedMessage}\n💬 이제 질문을 입력할 수 있습니다.`);
        } else {
            hideLoading();
            alert(`❌ 활성화 실패: ${data.error}`);
        }
    } catch (error) {
        hideLoading();
        alert(`❌ 오류 발생: ${error.message}`);
    }
}

/**
 * 활성 문서 표시 업데이트
 */
export async function updateActiveDocumentsDisplay() {
    try {
        const response = await fetch('api/loaded-documents');
        const data = await response.json();

        const activeDocsText = document.getElementById('active-docs-text');
        const activeDocsBadge = document.getElementById('active-docs-badge');
        const activeDocsBar = document.getElementById('active-docs-bar');
        const activeDocsIcon = document.querySelector('.active-docs-icon');

        if (data.success && data.documents && data.documents.length > 0) {
            activeDocsBar.classList.remove('empty');
            if (activeDocsIcon) {
                activeDocsIcon.classList.remove('pulse');
            }

            // 카테고리별로 문서 그룹화
            const categoryGroups = {};
            data.documents.forEach(doc => {
                const catId = doc.category.id;
                if (!categoryGroups[catId]) {
                    categoryGroups[catId] = {
                        category: doc.category,
                        count: 0
                    };
                }
                categoryGroups[catId].count++;
            });

            // 카테고리별 요약 생성
            const categoryText = Object.values(categoryGroups)
                .map(g => `${g.category.icon} ${g.category.name}(${g.count})`)
                .join(' | ');

            activeDocsText.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 4px;">
                    <div style="font-weight: 600;">${data.documents.length}개 문서 활성화됨</div>
                    <div style="font-size: 0.85rem; color: #64748b;">${categoryText}</div>
                </div>
            `;
            activeDocsBadge.textContent = data.documents.length;
            activeDocsBadge.style.display = 'inline-block';

            // 웹 검증 토글 상태 업데이트 (일반/기술 스펙 카테고리 체크)
            updateWebSearchToggleState(data.documents);
        } else {
            activeDocsBar.classList.add('empty');
            if (activeDocsIcon) {
                activeDocsIcon.textContent = '⚠️';
                activeDocsIcon.classList.add('pulse');
            }

            activeDocsText.innerHTML = '<strong style="color: #d97706;">문서를 먼저 활성화해주세요 →</strong>';
            activeDocsBadge.style.display = 'none';

            // 문서가 없을 때도 웹 검증 토글 상태 초기화
            updateWebSearchToggleState([]);
        }
    } catch (error) {
        console.error('활성 문서 정보 업데이트 실패:', error);
    }
}

// ==================== 웹 검증 토글 상태 관리 ====================

/**
 * 웹 검증 비활성화 대상 카테고리
 * "일반" (general) 및 "기술 스펙" (spec) 카테고리 문서는 웹 검증 제외
 */
const WEB_SEARCH_DISABLED_CATEGORIES = ['general', 'spec'];

/**
 * 로드된 문서 카테고리에 따라 웹 검증 토글 상태 업데이트
 * @param {Array} documents - 로드된 문서 목록
 */
function updateWebSearchToggleState(documents) {
    const webSearchCheckbox = document.getElementById('web-search-checkbox');
    const webSearchToggle = webSearchCheckbox?.closest('.web-search-toggle');

    if (!webSearchCheckbox || !webSearchToggle) {
        return;
    }

    // 문서가 없으면 웹 검증 비활성화
    if (!documents || documents.length === 0) {
        webSearchCheckbox.checked = false;
        webSearchCheckbox.disabled = true;
        webSearchToggle.classList.add('disabled');
        webSearchToggle.title = '🚫 웹 검증 불가: 활성화된 문서가 없습니다';
        return;
    }

    // 비활성화 대상 카테고리 문서가 있는지 확인
    const hasDisabledCategory = documents.some(doc =>
        WEB_SEARCH_DISABLED_CATEGORIES.includes(doc.category?.id)
    );

    // 비활성화 대상 카테고리 이름 수집
    const disabledCategoryNames = [...new Set(
        documents
            .filter(doc => WEB_SEARCH_DISABLED_CATEGORIES.includes(doc.category?.id))
            .map(doc => doc.category?.name)
    )];

    if (hasDisabledCategory) {
        // 웹 검증 비활성화
        webSearchCheckbox.checked = false;
        webSearchCheckbox.disabled = true;
        webSearchToggle.classList.add('disabled');
        webSearchToggle.title = `🚫 웹 검증 불가: ${disabledCategoryNames.join(', ')} 카테고리 문서가 포함되어 있습니다. 이 카테고리는 내부 전용 문서로 웹 검색 교차 검증이 불가능합니다.`;
    } else {
        // 웹 검증 활성화
        webSearchCheckbox.disabled = false;
        webSearchToggle.classList.remove('disabled');
        webSearchToggle.title = '🌐 웹 검증: 웹 검색으로 답변을 교차 검증하여 정확도를 향상시킵니다';
    }
}

// 전역 함수로 노출
window.openDocumentSelector = openDocumentSelector;
window.closeDocumentSelector = closeDocumentSelector;
