// ===================================================================
// 문서 관리 탭 모듈 (파일 탐색기 스타일)
// 벡터DB 문서 목록 조회, 삭제, 카테고리 변경 등
// 폴더와 문서를 통합된 리스트로 표시
// ===================================================================

import { state, setManageDocuments, setReady } from '../../state.js';
import { showLoading, hideLoading } from '../../utils.js';
import { openChunksModal } from '../modals/index.js';
import { assignDocumentToFolder, removeDocumentFromFolder } from './folders.js';

/**
 * 통계 업데이트 콜백
 * @type {Function|null}
 */
let onStatsUpdateCallback = null;

/**
 * 사이드바 배지 업데이트 콜백
 * @type {Function|null}
 */
let onSidebarBadgesUpdateCallback = null;

// ==================== 파일 탐색기 상태 ====================
/**
 * 현재 보고 있는 폴더 ID (null = 루트)
 * @type {string|null}
 */
let currentFolderId = null;

/**
 * 브레드크럼용 경로
 * @type {Array<{id: string|null, name: string}>}
 */
let folderPath = [{ id: null, name: '전체 문서' }];

/**
 * 폴더 데이터 캐시
 * @type {Array}
 */
let foldersCache = [];

/**
 * 드래그 중인 문서 ID
 * @type {string|null}
 */
let draggedDocId = null;

/**
 * 통계 업데이트 콜백 설정
 * @param {Function} callback
 */
export function setStatsUpdateCallback(callback) {
    onStatsUpdateCallback = callback;
}

/**
 * 사이드바 배지 업데이트 콜백 설정
 * @param {Function} callback
 */
export function setSidebarBadgesUpdateCallback(callback) {
    onSidebarBadgesUpdateCallback = callback;
}

/**
 * 문서 관리 탭 초기화
 */
export function initManageTab() {
    const refreshBtn = document.getElementById('refresh-docs-btn');
    const deleteAllBtn = document.getElementById('delete-all-docs-btn');
    const searchInput = document.getElementById('manage-doc-search');
    const newFolderBtn = document.getElementById('new-folder-btn');

    refreshBtn.addEventListener('click', loadVectorDBDocuments);
    deleteAllBtn.addEventListener('click', () => deleteAllDocuments());
    searchInput.addEventListener('input', filterManageDocuments);

    // 새 폴더 버튼 이벤트
    if (newFolderBtn) {
        newFolderBtn.addEventListener('click', () => showCreateFolderDialog(currentFolderId));
    }

    // 초기 폴더 데이터 로드
    loadFoldersData();
}

// ==================== 폴더 데이터 관리 ====================

/**
 * 폴더 데이터 로드
 */
async function loadFoldersData() {
    try {
        const response = await fetch('api/folders');
        const data = await response.json();

        if (data.success) {
            foldersCache = data.folders;
        }
    } catch (error) {
        console.error('폴더 데이터 로드 실패:', error);
        foldersCache = [];
    }
}

/**
 * 폴더 ID로 폴더 정보 찾기 (재귀)
 * @param {string} folderId - 폴더 ID
 * @param {Array} folders - 검색할 폴더 배열
 * @returns {Object|null}
 */
function findFolderById(folderId, folders = foldersCache) {
    for (const folder of folders) {
        if (folder.id === folderId) {
            return folder;
        }
        if (folder.children_data && folder.children_data.length > 0) {
            const found = findFolderById(folderId, folder.children_data);
            if (found) return found;
        }
    }
    return null;
}

/**
 * 현재 폴더의 하위 폴더 목록 가져오기
 * @returns {Array}
 */
function getCurrentSubfolders() {
    if (currentFolderId === null) {
        // 루트: 최상위 폴더들 반환
        return foldersCache;
    }

    const currentFolder = findFolderById(currentFolderId);
    if (currentFolder && currentFolder.children_data) {
        return currentFolder.children_data;
    }
    return [];
}

/**
 * 현재 폴더의 문서 목록 가져오기
 * @returns {Array}
 */
function getCurrentFolderDocuments() {
    if (currentFolderId === null) {
        // 루트: 폴더에 속하지 않은 문서들
        const allDocsInFolders = getAllDocsInFoldersSync();
        return state.allDocsInManage.filter(doc => !allDocsInFolders.includes(doc.filename));
    }

    const currentFolder = findFolderById(currentFolderId);
    if (currentFolder && currentFolder.documents) {
        return state.allDocsInManage.filter(doc => currentFolder.documents.includes(doc.filename));
    }
    return [];
}

/**
 * 모든 폴더에 속한 문서 ID 조회 (동기)
 * @returns {string[]}
 */
function getAllDocsInFoldersSync() {
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
    collectDocs(foldersCache);
    return allDocs;
}

// ==================== 폴더 네비게이션 ====================

/**
 * 폴더로 이동
 * @param {string|null} folderId - 이동할 폴더 ID (null = 루트)
 */
async function navigateToFolder(folderId) {
    currentFolderId = folderId;

    // 브레드크럼 경로 업데이트
    if (folderId === null) {
        folderPath = [{ id: null, name: '전체 문서' }];
    } else {
        // 폴더 경로 조회
        try {
            const response = await fetch(`/api/folders/${folderId}/path`);
            const data = await response.json();

            if (data.success && data.path) {
                folderPath = [{ id: null, name: '전체 문서' }, ...data.path];
            }
        } catch (error) {
            console.error('폴더 경로 조회 실패:', error);
        }
    }

    // 폴더 데이터 새로고침 후 렌더링
    await loadFoldersData();
    renderBreadcrumb();
    renderFolderContents();
}

/**
 * 상위 폴더로 이동
 */
function navigateToParent() {
    if (folderPath.length > 1) {
        const parentPath = folderPath[folderPath.length - 2];
        navigateToFolder(parentPath.id);
    }
}

// ==================== 브레드크럼 렌더링 ====================

/**
 * 브레드크럼 렌더링
 */
function renderBreadcrumb() {
    const container = document.getElementById('folder-breadcrumb');
    if (!container) return;

    container.innerHTML = '';

    folderPath.forEach((item, index) => {
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
        if (index === folderPath.length - 1) {
            breadcrumbItem.classList.add('active');
            breadcrumbItem.textContent = `📍 ${item.name}`;
        } else {
            breadcrumbItem.textContent = item.name;
            breadcrumbItem.addEventListener('click', () => navigateToFolder(item.id));
        }

        container.appendChild(breadcrumbItem);
    });
}

/**
 * 벡터DB 문서 목록 로드
 */
export async function loadVectorDBDocuments() {
    try {
        const response = await fetch('api/documents');
        const data = await response.json();

        const deleteAllBtn = document.getElementById('delete-all-docs-btn');

        if (data.success && data.documents.length > 0) {
            setManageDocuments(data.documents);
            deleteAllBtn.style.display = 'block';

            if (onStatsUpdateCallback) {
                onStatsUpdateCallback(state.allDocsInManage);
            }
            if (onSidebarBadgesUpdateCallback) {
                onSidebarBadgesUpdateCallback();
            }
        } else {
            setManageDocuments([]);
            deleteAllBtn.style.display = 'none';

            if (onStatsUpdateCallback) {
                onStatsUpdateCallback([]);
            }
            if (onSidebarBadgesUpdateCallback) {
                onSidebarBadgesUpdateCallback();
            }
        }

        // 폴더 데이터 새로고침 후 통합 렌더링
        await loadFoldersData();
        renderBreadcrumb();
        renderFolderContents();
    } catch (error) {
        console.error('벡터DB 문서 로드 실패:', error);
    }
}

// ==================== 통합 렌더링 (폴더 + 문서) ====================

/**
 * 폴더 컨텐츠 렌더링 (폴더 + 문서 통합)
 */
function renderFolderContents() {
    const docsList = document.getElementById('docs-list');
    if (!docsList) return;

    const subfolders = getCurrentSubfolders();
    const documents = getCurrentFolderDocuments();

    // 빈 상태 체크
    if (subfolders.length === 0 && documents.length === 0 && state.allDocsInManage.length === 0) {
        docsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <p>벡터DB에 저장된 문서가 없습니다</p>
                <p style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.5rem;">
                    📁 문서 준비 탭에서 파일을 업로드하고 벡터DB에 저장하세요
                </p>
                <button class="btn btn-primary" onclick="switchTab('prepare')">
                    문서 추가하기 →
                </button>
            </div>
        `;
        return;
    }

    // 테이블 컨테이너 생성
    const tableContainer = document.createElement('div');
    tableContainer.style.cssText = `
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    `;

    // 테이블 헤더
    const headerRow = document.createElement('div');
    headerRow.style.cssText = `
        display: grid;
        grid-template-columns: minmax(200px, 1fr) 80px 140px 100px 120px;
        gap: 12px;
        padding: 12px 16px;
        background: #f8fafc;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.75rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    `;
    headerRow.innerHTML = `
        <div>이름</div>
        <div style="text-align: center;">청크/문서</div>
        <div>날짜</div>
        <div>카테고리</div>
        <div style="text-align: center;">액션</div>
    `;
    tableContainer.appendChild(headerRow);

    // 상위 폴더로 이동 행 (루트가 아닌 경우)
    if (currentFolderId !== null) {
        const parentRow = createParentFolderRow();
        tableContainer.appendChild(parentRow);
    }

    // 폴더 행들 렌더링
    subfolders.forEach(folder => {
        const folderRow = createFolderRow(folder);
        tableContainer.appendChild(folderRow);
    });

    // 구분선 (폴더와 파일 사이)
    if (subfolders.length > 0 && documents.length > 0) {
        const separator = document.createElement('div');
        separator.className = 'folder-separator';
        tableContainer.appendChild(separator);
    }

    // 문서 행들 렌더링
    documents.forEach((doc, index) => {
        const docRow = createDocumentRow(doc, index);
        tableContainer.appendChild(docRow);
    });

    // 빈 폴더 상태
    if (subfolders.length === 0 && documents.length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-folder-state';
        emptyState.innerHTML = `
            <div class="empty-icon">📂</div>
            <p>이 폴더는 비어 있습니다</p>
            <p style="font-size: 0.75rem; margin-top: 8px;">파일을 드래그하여 이 폴더에 추가하세요</p>
        `;
        tableContainer.appendChild(emptyState);
    }

    docsList.innerHTML = '';
    docsList.appendChild(tableContainer);
}

/**
 * 상위 폴더 이동 행 생성
 * @returns {HTMLElement}
 */
function createParentFolderRow() {
    const row = document.createElement('div');
    row.className = 'doc-item folder-row parent-folder-row';
    row.style.cssText = `
        display: grid;
        grid-template-columns: minmax(200px, 1fr) 80px 140px 100px 120px;
        gap: 12px;
        padding: 10px 16px;
        align-items: center;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.875rem;
        cursor: pointer;
    `;

    // 상위 폴더 ID 결정 (현재 폴더의 부모)
    const parentFolderId = folderPath.length > 1 ? folderPath[folderPath.length - 2].id : null;

    row.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.25rem;">📁</span>
            <span style="font-weight: 600;">.. (상위 폴더)</span>
            <span style="font-size: 0.75rem; color: #94a3b8; margin-left: 8px;">드롭하여 이동</span>
        </div>
        <div style="text-align: center; color: #64748b;">-</div>
        <div style="color: #64748b;">-</div>
        <div>-</div>
        <div></div>
    `;

    row.addEventListener('click', () => navigateToParent());
    row.addEventListener('dblclick', () => navigateToParent());

    // 드래그 앤 드롭 지원 - 상위 폴더로 이동
    row.addEventListener('dragover', handleDragOver);
    row.addEventListener('dragleave', handleDragLeave);
    row.addEventListener('drop', (e) => handleDropToParent(e, parentFolderId));

    return row;
}

/**
 * 폴더 행 생성
 * @param {Object} folder - 폴더 데이터
 * @returns {HTMLElement}
 */
function createFolderRow(folder) {
    const row = document.createElement('div');
    row.className = 'doc-item folder-row';
    row.dataset.folderId = folder.id;
    row.style.cssText = `
        display: grid;
        grid-template-columns: minmax(200px, 1fr) 80px 140px 100px 120px;
        gap: 12px;
        padding: 10px 16px;
        align-items: center;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.875rem;
        cursor: pointer;
        border-left: 3px solid ${folder.color || '#6366f1'};
    `;

    // 아이콘 결정
    let folderIcon = '📁';
    if (folder.icon === 'cloud') folderIcon = '☁️';
    else if (folder.icon === 'building') folderIcon = '🏢';
    else if (folder.icon === 'landmark') folderIcon = '🏛️';
    else if (folder.children_data && folder.children_data.length > 0) folderIcon = '📂';

    const docCount = folder.document_count || (folder.documents ? folder.documents.length : 0);

    row.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.25rem;">${folderIcon}</span>
            <span style="font-weight: 600;" title="${folder.name}">${folder.name}</span>
            ${folder.is_system ? '<span class="folder-info-chip">시스템</span>' : ''}
        </div>
        <div style="text-align: center; color: #64748b;">${docCount} 문서</div>
        <div style="color: #64748b; font-size: 0.813rem;">${folder.created_at ? folder.created_at.substring(5, 10) : '-'}</div>
        <div>-</div>
        <div style="display: flex; justify-content: center; gap: 4px;">
            ${!folder.is_system ? `
                <button class="folder-menu-btn" data-folder-id="${folder.id}" title="폴더 옵션" style="padding: 6px 8px; background: #64748b; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem;">⋮</button>
            ` : ''}
        </div>
    `;

    // 클릭 이벤트 - 폴더 진입
    row.addEventListener('dblclick', (e) => {
        if (!e.target.classList.contains('folder-menu-btn')) {
            navigateToFolder(folder.id);
        }
    });

    // 단일 클릭도 폴더 진입
    row.addEventListener('click', (e) => {
        if (!e.target.classList.contains('folder-menu-btn')) {
            navigateToFolder(folder.id);
        }
    });

    // 드래그 오버 이벤트 (드롭 대상)
    row.addEventListener('dragover', handleDragOver);
    row.addEventListener('dragleave', handleDragLeave);
    row.addEventListener('drop', (e) => handleDrop(e, folder.id));

    // 폴더 메뉴 버튼 이벤트
    const menuBtn = row.querySelector('.folder-menu-btn');
    if (menuBtn) {
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showFolderContextMenu(e, folder);
        });
    }

    // 우클릭 컨텍스트 메뉴
    if (!folder.is_system) {
        row.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showFolderContextMenu(e, folder);
        });
    }

    return row;
}

/**
 * 문서 행 생성
 * @param {Object} doc - 문서 데이터
 * @param {number} index - 인덱스
 * @returns {HTMLElement}
 */
function createDocumentRow(doc, index) {
    const category = doc.category || { id: 'general', name: '일반', color: '#6366f1', icon: '📄' };

    const rowWrapper = document.createElement('div');
    rowWrapper.className = 'doc-row-wrapper';

    const docRow = document.createElement('div');
    docRow.className = 'doc-item file-row draggable';
    docRow.dataset.docId = doc.filename;
    docRow.draggable = true;  // 드래그 가능하게 설정
    docRow.style.cssText = `
        display: grid;
        grid-template-columns: minmax(200px, 1fr) 80px 140px 100px 120px;
        gap: 12px;
        padding: 10px 16px;
        align-items: center;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.875rem;
        transition: background 0.15s;
        border-left: 3px solid ${category.color};
    `;

    // 짝수/홀수 행 배경색
    if (index % 2 === 1) {
        docRow.style.background = '#fafbfc';
    }

    // 날짜 포맷 (간소화) - updated_at 우선 사용
    const dateStr = doc.updated_at ? doc.updated_at.substring(5, 16).replace(' ', ' ') :
                    (doc.added_at ? doc.added_at.substring(5, 16).replace(' ', ' ') : '-');

    // 표시 이름: title이 있으면 title 사용, 없으면 filename 사용
    const displayName = doc.title || doc.filename;

    docRow.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
            <span class="drag-handle" title="드래그하여 폴더로 이동">⋮⋮</span>
            <span style="flex-shrink: 0;">${category.icon}</span>
            <span title="${doc.filename}" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500;">${displayName}</span>
        </div>
        <div style="text-align: center; color: #64748b; font-variant-numeric: tabular-nums;">${doc.chunk_count}</div>
        <div style="color: #64748b; font-size: 0.813rem;">${dateStr}</div>
        <div>
            <select class="doc-category-select" data-filename="${doc.filename}" data-collection="${doc.collection}" style="padding: 4px 6px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.75rem; cursor: pointer; background: white; width: 100%;">
                <option value="general" ${category.id === 'general' ? 'selected' : ''}>일반</option>
                <option value="api" ${category.id === 'api' ? 'selected' : ''}>API</option>
                <option value="guide" ${category.id === 'guide' ? 'selected' : ''}>가이드</option>
                <option value="spec" ${category.id === 'spec' ? 'selected' : ''}>기술스펙</option>
            </select>
        </div>
        <div style="display: flex; justify-content: center; gap: 4px;">
            <button class="doc-menu-btn" data-filename="${doc.filename}" data-collection="${doc.collection}" title="문서 옵션" style="padding: 6px 8px; background: #64748b; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; transition: opacity 0.15s;">⋮</button>
            <button class="doc-preview-btn" data-filename="${doc.filename}" data-collection="${doc.collection}" title="청크 미리보기" style="padding: 6px 8px; background: #6366f1; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; transition: opacity 0.15s;">✂️</button>
            <button class="doc-delete-btn" data-filename="${doc.filename}" title="삭제" style="padding: 6px 8px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; transition: opacity 0.15s;">🗑️</button>
        </div>
    `;

    rowWrapper.appendChild(docRow);

    // 미리보기 컨테이너 (행 아래에 숨김)
    const previewContainer = document.createElement('div');
    previewContainer.className = 'chunk-preview-container';
    previewContainer.id = `preview-${doc.collection}-${doc.filename}`;
    previewContainer.style.cssText = `
        display: none;
        padding: 12px 16px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        margin-left: 3px;
    `;
    rowWrapper.appendChild(previewContainer);

    // 드래그 이벤트
    docRow.addEventListener('dragstart', (e) => handleDragStart(e, doc.filename));
    docRow.addEventListener('dragend', handleDragEnd);

    // 문서 메뉴 버튼 이벤트
    const menuBtn = docRow.querySelector('.doc-menu-btn');
    menuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showDocumentContextMenu(e, doc);
    });

    // 미리보기 버튼 이벤트
    const previewBtn = docRow.querySelector('.doc-preview-btn');
    previewBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const filename = e.currentTarget.dataset.filename;
        const collection = e.currentTarget.dataset.collection;
        await toggleChunkPreview(filename, collection);
    });

    // 카테고리 변경 이벤트
    const categorySelect = docRow.querySelector('.doc-category-select');
    categorySelect.addEventListener('change', async (e) => {
        e.stopPropagation();
        const newCategory = e.target.value;
        const filename = e.target.dataset.filename;
        const collection = e.target.dataset.collection;
        await updateDocumentCategory(filename, collection, newCategory);
    });

    // 삭제 버튼 이벤트
    const deleteBtn = docRow.querySelector('.doc-delete-btn');
    deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const filename = e.currentTarget.dataset.filename;
        if (confirm(`문서 "${filename}"을(를) 벡터 DB에서 삭제하시겠습니까?\n\n청킹된 데이터가 영구적으로 삭제됩니다.`)) {
            await deleteDocument(filename);
        }
    });

    // 호버 효과
    const originalBg = index % 2 === 1 ? '#fafbfc' : 'white';
    docRow.addEventListener('mouseenter', () => {
        if (!docRow.classList.contains('dragging')) {
            docRow.style.background = '#f1f5f9';
        }
    });
    docRow.addEventListener('mouseleave', () => {
        if (!docRow.classList.contains('dragging')) {
            docRow.style.background = originalBg;
        }
    });

    // 우클릭 컨텍스트 메뉴
    docRow.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showDocumentContextMenu(e, doc);
    });

    return rowWrapper;
}

// ==================== 드래그 앤 드롭 ====================

/**
 * 드래그 시작 핸들러
 * @param {DragEvent} e
 * @param {string} docId - 문서 ID
 */
function handleDragStart(e, docId) {
    draggedDocId = docId;
    e.currentTarget.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', docId);

    // 모든 폴더 행에 드래그 타겟 표시
    document.querySelectorAll('.folder-row').forEach(row => {
        row.classList.add('drag-target');
    });
}

/**
 * 드래그 종료 핸들러
 * @param {DragEvent} e
 */
function handleDragEnd(e) {
    e.currentTarget.classList.remove('dragging');
    draggedDocId = null;

    // 드래그 타겟 표시 제거
    document.querySelectorAll('.folder-row').forEach(row => {
        row.classList.remove('drag-target');
        row.classList.remove('drag-over');
    });
}

/**
 * 드래그 오버 핸들러 (폴더 위에 있을 때)
 * @param {DragEvent} e
 */
function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
}

/**
 * 드래그 리브 핸들러 (폴더에서 벗어날 때)
 * @param {DragEvent} e
 */
function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

/**
 * 드롭 핸들러 (폴더에 드롭할 때)
 * @param {DragEvent} e
 * @param {string} folderId - 대상 폴더 ID
 */
async function handleDrop(e, folderId) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    const docId = e.dataTransfer.getData('text/plain') || draggedDocId;
    if (!docId || !folderId) return;

    try {
        const success = await assignDocumentToFolder(docId, folderId);
        if (success) {
            // 폴더 데이터 새로고침 후 다시 렌더링
            await loadFoldersData();
            renderFolderContents();
        } else {
            alert('문서를 폴더에 이동하는데 실패했습니다.');
        }
    } catch (error) {
        console.error('폴더 이동 실패:', error);
        alert('문서를 폴더에 이동하는데 실패했습니다.');
    }
}

/**
 * 상위 폴더로 드롭 핸들러
 * @param {DragEvent} e
 * @param {string|null} parentFolderId - 상위 폴더 ID (null이면 루트)
 */
async function handleDropToParent(e, parentFolderId) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');

    const docId = e.dataTransfer.getData('text/plain') || draggedDocId;
    if (!docId) return;

    try {
        // 현재 폴더에서 제거
        if (currentFolderId) {
            await removeDocumentFromFolder(docId, currentFolderId);
        }

        // 상위 폴더가 있으면 그곳에 할당 (루트가 아닌 경우)
        if (parentFolderId) {
            await assignDocumentToFolder(docId, parentFolderId);
        }

        // 폴더 데이터 새로고침 후 다시 렌더링
        await loadFoldersData();
        renderFolderContents();
    } catch (error) {
        console.error('상위 폴더로 이동 실패:', error);
        alert('문서를 상위 폴더로 이동하는데 실패했습니다.');
    }
}

// ==================== 컨텍스트 메뉴 ====================

/**
 * 폴더 컨텍스트 메뉴 표시
 * @param {MouseEvent} e
 * @param {Object} folder
 */
function showFolderContextMenu(e, folder) {
    // 기존 메뉴 제거
    const existingMenu = document.querySelector('.folder-context-menu');
    if (existingMenu) existingMenu.remove();

    const menu = document.createElement('div');
    menu.className = 'folder-context-menu';
    menu.style.left = `${e.pageX}px`;
    menu.style.top = `${e.pageY}px`;

    menu.innerHTML = `
        <div class="context-menu-item" data-action="rename">
            <span>📝</span> 이름 바꾸기
        </div>
        <div class="context-menu-item" data-action="subfolder">
            <span>📁</span> 하위 폴더 추가
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item danger" data-action="delete">
            <span>🗑️</span> 삭제
        </div>
    `;

    document.body.appendChild(menu);

    // 메뉴 항목 이벤트
    menu.querySelector('[data-action="rename"]').addEventListener('click', () => {
        renameFolderPrompt(folder.id, folder.name);
        menu.remove();
    });

    menu.querySelector('[data-action="subfolder"]').addEventListener('click', () => {
        showCreateFolderDialog(folder.id);
        menu.remove();
    });

    menu.querySelector('[data-action="delete"]').addEventListener('click', () => {
        deleteFolderPrompt(folder.id, folder.name);
        menu.remove();
    });

    // 클릭 시 메뉴 닫기
    const closeMenu = () => {
        menu.remove();
        document.removeEventListener('click', closeMenu);
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
}

/**
 * 문서 컨텍스트 메뉴 표시
 * @param {MouseEvent} e
 * @param {Object} doc
 */
function showDocumentContextMenu(e, doc) {
    // 기존 메뉴 제거
    const existingMenu = document.querySelector('.folder-context-menu');
    if (existingMenu) existingMenu.remove();

    const menu = document.createElement('div');
    menu.className = 'folder-context-menu';
    menu.style.left = `${e.pageX}px`;
    menu.style.top = `${e.pageY}px`;

    // 현재 폴더 내에 있는지 확인
    const isInFolder = currentFolderId !== null;

    menu.innerHTML = `
        <div class="context-menu-item" data-action="preview">
            <span>✂️</span> 청크 미리보기
        </div>
        ${isInFolder ? `
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" data-action="move-to-parent">
            <span>📤</span> 상위 폴더로 이동
        </div>
        <div class="context-menu-item" data-action="move-to-root">
            <span>🏠</span> 루트로 이동
        </div>
        ` : ''}
        <div class="context-menu-separator"></div>
        <div class="context-menu-item danger" data-action="delete">
            <span>🗑️</span> 삭제
        </div>
    `;

    document.body.appendChild(menu);

    // 미리보기
    menu.querySelector('[data-action="preview"]')?.addEventListener('click', () => {
        toggleChunkPreview(doc.filename, doc.collection);
        menu.remove();
    });

    // 상위 폴더로 이동
    menu.querySelector('[data-action="move-to-parent"]')?.addEventListener('click', async () => {
        await moveDocumentToParent(doc.filename);
        menu.remove();
    });

    // 루트로 이동
    menu.querySelector('[data-action="move-to-root"]')?.addEventListener('click', async () => {
        await moveDocumentToRoot(doc.filename);
        menu.remove();
    });

    // 삭제
    menu.querySelector('[data-action="delete"]').addEventListener('click', () => {
        if (confirm(`문서 "${doc.filename}"을(를) 삭제하시겠습니까?`)) {
            deleteDocument(doc.filename);
        }
        menu.remove();
    });

    // 클릭 시 메뉴 닫기
    const closeMenu = () => {
        menu.remove();
        document.removeEventListener('click', closeMenu);
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
}

// ==================== 문서 이동 헬퍼 ====================

/**
 * 문서를 상위 폴더로 이동
 * @param {string} docId - 문서 ID
 */
async function moveDocumentToParent(docId) {
    if (!currentFolderId) return;

    try {
        // 현재 폴더에서 제거
        await removeDocumentFromFolder(docId, currentFolderId);

        // 상위 폴더가 있으면 그곳에 할당
        const parentFolderId = folderPath.length > 1 ? folderPath[folderPath.length - 2].id : null;
        if (parentFolderId) {
            await assignDocumentToFolder(docId, parentFolderId);
        }

        // 새로고침
        await loadFoldersData();
        renderFolderContents();
    } catch (error) {
        console.error('상위 폴더로 이동 실패:', error);
        alert('문서를 상위 폴더로 이동하는데 실패했습니다.');
    }
}

/**
 * 문서를 루트로 이동 (모든 폴더에서 제거)
 * @param {string} docId - 문서 ID
 */
async function moveDocumentToRoot(docId) {
    if (!currentFolderId) return;

    try {
        // 현재 폴더에서 제거
        await removeDocumentFromFolder(docId, currentFolderId);

        // 새로고침
        await loadFoldersData();
        renderFolderContents();
    } catch (error) {
        console.error('루트로 이동 실패:', error);
        alert('문서를 루트로 이동하는데 실패했습니다.');
    }
}

// ==================== 폴더 CRUD ====================

/**
 * 새 폴더 생성 다이얼로그
 * @param {string|null} parentId
 */
function showCreateFolderDialog(parentId = null) {
    const name = prompt('새 폴더 이름을 입력하세요:');
    if (!name || !name.trim()) return;

    createFolder(name.trim(), parentId);
}

/**
 * 폴더 생성 API 호출
 * @param {string} name
 * @param {string|null} parentId
 */
async function createFolder(name, parentId = null) {
    try {
        const response = await fetch('api/folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                parent_id: parentId
            })
        });

        const data = await response.json();
        if (data.success) {
            await loadFoldersData();
            renderFolderContents();
        } else {
            alert('폴더 생성 실패: ' + data.error);
        }
    } catch (error) {
        console.error('폴더 생성 실패:', error);
        alert('폴더 생성 중 오류가 발생했습니다.');
    }
}

/**
 * 폴더 이름 변경 프롬프트
 * @param {string} folderId
 * @param {string} currentName
 */
async function renameFolderPrompt(folderId, currentName) {
    const newName = prompt('새 이름을 입력하세요:', currentName);
    if (!newName || newName.trim() === currentName) return;

    try {
        const response = await fetch(`/api/folders/${folderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName.trim() })
        });

        const data = await response.json();
        if (data.success) {
            await loadFoldersData();
            renderBreadcrumb();
            renderFolderContents();
        } else {
            alert('이름 변경 실패: ' + data.error);
        }
    } catch (error) {
        console.error('이름 변경 실패:', error);
    }
}

/**
 * 폴더 삭제 확인
 * @param {string} folderId
 * @param {string} folderName
 */
async function deleteFolderPrompt(folderId, folderName) {
    if (!confirm(`'${folderName}' 폴더를 삭제하시겠습니까?\n\n하위 폴더와 문서 매핑도 함께 삭제됩니다.`)) return;

    try {
        const response = await fetch(`/api/folders/${folderId}?recursive=true`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.success) {
            // 삭제된 폴더가 현재 폴더면 상위로 이동
            if (currentFolderId === folderId) {
                navigateToParent();
            } else {
                await loadFoldersData();
                renderFolderContents();
            }
        } else {
            alert('삭제 실패: ' + data.error);
        }
    } catch (error) {
        console.error('삭제 실패:', error);
    }
}

/**
 * 청크 미리보기 토글
 * @param {string} filename - 파일명
 * @param {string} collection - 컬렉션명
 */
async function toggleChunkPreview(filename, collection) {
    const previewId = `preview-${collection}-${filename}`;
    const previewContainer = document.getElementById(previewId);

    if (!previewContainer) return;

    if (previewContainer.style.display === 'block') {
        previewContainer.style.display = 'none';
        return;
    }

    try {
        previewContainer.innerHTML = '<div style="text-align: center; color: #64748b;">로딩 중...</div>';
        previewContainer.style.display = 'block';

        const response = await fetch(`/api/documents/${encodeURIComponent(filename)}/chunks/preview?collection=${encodeURIComponent(collection)}&limit=3`);
        const data = await response.json();

        if (!data.success) {
            previewContainer.innerHTML = `<div style="color: #ef4444;">오류: ${data.error}</div>`;
            return;
        }

        let previewHTML = `
            <div style="margin-bottom: 12px; font-weight: 600; color: #334155;">
                📊 총 ${data.total_chunks}개 청크 중 ${data.preview_chunks.length}개 미리보기
            </div>
        `;

        data.preview_chunks.forEach((chunk) => {
            const truncatedContent = chunk.content.length > 200
                ? chunk.content.substring(0, 200) + '...'
                : chunk.content;

            previewHTML += `
                <div style="margin-bottom: 12px; padding: 12px; background: white; border-radius: 4px; border-left: 3px solid #6366f1;">
                    <div style="margin-bottom: 6px; font-size: 0.8125rem; color: #64748b;">
                        <strong>청크 #${chunk.chunk_index + 1}</strong> (${chunk.length}자)
                    </div>
                    <div style="font-size: 0.875rem; color: #334155; line-height: 1.6; white-space: pre-wrap;">${truncatedContent}</div>
                </div>
            `;
        });

        if (data.total_chunks > data.preview_chunks.length) {
            previewHTML += `
                <button class="view-all-chunks-btn" data-filename="${filename}" data-collection="${collection}"
                    style="width: 100%; padding: 10px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; margin-top: 8px;">
                    전체 ${data.total_chunks}개 청크 보기 →
                </button>
            `;
        }

        previewContainer.innerHTML = previewHTML;

        const viewAllBtn = previewContainer.querySelector('.view-all-chunks-btn');
        if (viewAllBtn) {
            viewAllBtn.addEventListener('click', () => {
                openChunksModal(filename, collection, data.total_chunks);
            });
        }

    } catch (error) {
        console.error('청크 미리보기 로드 실패:', error);
        previewContainer.innerHTML = `<div style="color: #ef4444;">미리보기 로드 실패: ${error.message}</div>`;
    }
}

/**
 * 문서 필터링 (검색)
 * @param {Event} e - 입력 이벤트
 */
function filterManageDocuments(e) {
    const searchTerm = e.target.value.toLowerCase().trim();

    if (!searchTerm) {
        // 검색어 없으면 현재 폴더 컨텐츠 다시 렌더링
        renderFolderContents();
        return;
    }

    // 현재 폴더의 문서에서 검색
    const documents = getCurrentFolderDocuments();
    const subfolders = getCurrentSubfolders();

    // 폴더와 문서 모두 검색
    const filteredFolders = subfolders.filter(folder =>
        folder.name.toLowerCase().includes(searchTerm)
    );

    const filteredDocs = documents.filter(doc =>
        doc.filename.toLowerCase().includes(searchTerm) ||
        doc.collection.toLowerCase().includes(searchTerm)
    );

    // 필터된 결과 렌더링
    renderFilteredContents(filteredFolders, filteredDocs, searchTerm);
}

/**
 * 필터된 컨텐츠 렌더링
 * @param {Array} folders - 필터된 폴더
 * @param {Array} documents - 필터된 문서
 * @param {string} searchTerm - 검색어
 */
function renderFilteredContents(folders, documents, searchTerm) {
    const docsList = document.getElementById('docs-list');
    if (!docsList) return;

    if (folders.length === 0 && documents.length === 0) {
        docsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <p>"${searchTerm}"에 대한 검색 결과가 없습니다</p>
            </div>
        `;
        return;
    }

    // 테이블 컨테이너 생성
    const tableContainer = document.createElement('div');
    tableContainer.style.cssText = `
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    `;

    // 테이블 헤더
    const headerRow = document.createElement('div');
    headerRow.style.cssText = `
        display: grid;
        grid-template-columns: minmax(200px, 1fr) 80px 140px 100px 120px;
        gap: 12px;
        padding: 12px 16px;
        background: #f8fafc;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.75rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    `;
    headerRow.innerHTML = `
        <div>이름 (검색 결과: ${folders.length + documents.length}개)</div>
        <div style="text-align: center;">청크/문서</div>
        <div>날짜</div>
        <div>카테고리</div>
        <div style="text-align: center;">액션</div>
    `;
    tableContainer.appendChild(headerRow);

    // 폴더 결과
    folders.forEach(folder => {
        const folderRow = createFolderRow(folder);
        tableContainer.appendChild(folderRow);
    });

    // 구분선
    if (folders.length > 0 && documents.length > 0) {
        const separator = document.createElement('div');
        separator.className = 'folder-separator';
        tableContainer.appendChild(separator);
    }

    // 문서 결과
    documents.forEach((doc, index) => {
        const docRow = createDocumentRow(doc, index);
        tableContainer.appendChild(docRow);
    });

    docsList.innerHTML = '';
    docsList.appendChild(tableContainer);
}

/**
 * 문서 카테고리 업데이트
 * @param {string} filename - 파일명
 * @param {string} collection - 컬렉션명
 * @param {string} categoryId - 새 카테고리 ID
 */
async function updateDocumentCategory(filename, collection, categoryId) {
    try {
        const response = await fetch('api/documents/category', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                collection: collection,
                category_id: categoryId
            })
        });

        const data = await response.json();

        if (data.success) {
            console.log(`✅ 문서 카테고리 변경 성공: ${filename} -> ${categoryId}`);
            await loadVectorDBDocuments();
        } else {
            alert(`카테고리 변경 실패: ${data.error}`);
            await loadVectorDBDocuments();
        }
    } catch (error) {
        alert(`오류 발생: ${error.message}`);
        await loadVectorDBDocuments();
    }
}

/**
 * 문서 삭제
 * @param {string} filename - 삭제할 파일명
 * @param {string} scope - 삭제 범위 ('all', 'vector_only', 'file_only')
 * @param {string} collection - 컬렉션명 (optional)
 */
export async function deleteDocument(filename, scope = 'all', collection = null) {
    const scopeDescriptions = {
        'all': '원본 파일과 벡터 DB 데이터 모두',
        'vector_only': '벡터 DB 데이터만 (원본 파일 유지)',
        'file_only': '원본 파일만 (벡터 DB 유지)'
    };

    const confirmed = confirm(
        `"${filename}"을(를) 삭제하시겠습니까?\n\n` +
        `삭제 범위: ${scopeDescriptions[scope]}\n\n` +
        `⚠️ 이 작업은 되돌릴 수 없습니다.`
    );

    if (!confirmed) return;

    showLoading(`문서 "${filename}" 삭제 중...`);

    try {
        let url = `/api/documents/${encodeURIComponent(filename)}?scope=${scope}`;
        if (collection) {
            url += `&collection=${encodeURIComponent(collection)}`;
        }

        const response = await fetch(url, { method: 'DELETE' });
        const result = await response.json();

        if (result.success) {
            const deletedItems = [];
            if (result.deleted?.original_file) deletedItems.push('원본 파일');
            if (result.deleted?.vector_chunks) deletedItems.push('벡터 데이터');
            if (result.deleted?.file_metadata) deletedItems.push('파일 메타데이터');
            if (result.deleted?.document_metadata) deletedItems.push('문서 메타데이터');

            const message = deletedItems.length > 0
                ? `삭제 완료: ${deletedItems.join(', ')}\n\n${result.message || ''}`
                : result.message || '문서가 삭제되었습니다.';

            if (result.details) {
                let details = '';
                if (result.details.deleted_chunks) {
                    details += `\n삭제된 청크: ${result.details.deleted_chunks}개`;
                }
                if (result.details.collection) {
                    details += `\n컬렉션: ${result.details.collection}`;
                }
                if (details) {
                    console.log('삭제 상세:', result.details);
                }
            }

            alert(message);
            await loadVectorDBDocuments();
        } else {
            let errorMsg = result.error || '삭제 실패';
            if (result.deleted && Object.values(result.deleted).some(v => v)) {
                errorMsg += '\n\n⚠️ 일부만 삭제되었습니다:';
                if (result.deleted.original_file) errorMsg += '\n✓ 원본 파일';
                if (result.deleted.vector_chunks) errorMsg += '\n✓ 벡터 데이터';
                if (result.deleted.file_metadata) errorMsg += '\n✓ 파일 메타데이터';
            }
            if (result.errors && result.errors.length > 0) {
                errorMsg += '\n\n오류:\n' + result.errors.join('\n');
            }
            alert(errorMsg);

            if (result.deleted && Object.values(result.deleted).some(v => v)) {
                await loadVectorDBDocuments();
            }
        }
    } catch (error) {
        alert(`오류 발생: ${error.message}`);
        console.error('삭제 오류:', error);
    } finally {
        hideLoading();
    }
}

/**
 * 전체 문서 삭제
 * @param {string} scope - 삭제 범위 ('all', 'vector_only', 'file_only')
 */
export async function deleteAllDocuments(scope = 'all') {
    const scopeDescriptions = {
        'all': '원본 파일, 벡터 DB, 메타데이터 모두',
        'vector_only': '벡터 DB 데이터만 (원본 파일 유지)',
        'file_only': '원본 파일만 (벡터 DB 유지)'
    };

    const confirmed = confirm(
        '⚠️ 경고: 모든 문서를 삭제하시겠습니까?\n\n' +
        `삭제 범위: ${scopeDescriptions[scope]}\n\n` +
        '이 작업은 되돌릴 수 없습니다.\n' +
        '계속하려면 확인을 누르세요.'
    );

    if (!confirmed) return;

    const doubleConfirm = confirm(
        '정말로 모든 문서를 삭제하시겠습니까?\n\n' +
        '마지막 확인입니다.'
    );

    if (!doubleConfirm) return;

    showLoading('문서 데이터 삭제 중...');

    try {
        const response = await fetch(
            `/api/documents?confirm=true&scope=${scope}`,
            { method: 'DELETE' }
        );
        const result = await response.json();

        if (result.success) {
            const counts = result.deleted_count || {};
            let message = '삭제 완료!\n\n';
            if (counts.original_files > 0) {
                message += `• 원본 파일: ${counts.original_files}개\n`;
            }
            if (counts.html_files > 0) {
                message += `• HTML 파일: ${counts.html_files}개\n`;
            }
            if (counts.collections > 0) {
                message += `• 컬렉션: ${counts.collections}개\n`;
            }

            alert(message || '모든 문서가 삭제되었습니다.');

            await loadVectorDBDocuments();

            // 질의응답 상태 초기화
            setReady(false);
            document.getElementById('question-input').disabled = true;
            document.getElementById('ask-btn').disabled = true;
            document.getElementById('active-docs-text').textContent = '활성화된 문서가 없습니다';

            // 채팅 히스토리 초기화
            const chatHistory = document.getElementById('chat-history');
            chatHistory.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">👋</div>
                    <h2>안녕하세요!</h2>
                    <p>문서를 기반으로 질문에 답변해드립니다.</p>
                    <p class="welcome-hint">먼저 <strong>"활성화 문서 변경"</strong> 버튼으로 문서를 활성화해주세요.</p>
                </div>
            `;
        } else {
            let errorMsg = result.error || '삭제 실패';
            if (result.errors && result.errors.length > 0) {
                errorMsg += '\n\n오류:\n' + result.errors.join('\n');
            }
            if (result.deleted_count) {
                errorMsg += '\n\n일부 삭제됨:';
                const counts = result.deleted_count;
                if (counts.original_files > 0) errorMsg += `\n• 파일: ${counts.original_files}개`;
                if (counts.collections > 0) errorMsg += `\n• 컬렉션: ${counts.collections}개`;
            }
            alert(errorMsg);
        }
    } catch (error) {
        alert('오류 발생: ' + error.message);
        console.error('전체 삭제 오류:', error);
    } finally {
        hideLoading();
    }
}
