// ===================================================================
// 폴더 관리 모듈
// 문서를 폴더로 정리하는 기능 제공
// ===================================================================

/**
 * 현재 선택된 폴더 ID
 * @type {string|null}
 */
let selectedFolderId = null;

/**
 * 폴더 데이터 캐시
 * @type {Array}
 */
let foldersCache = [];

/**
 * 문서 필터 콜백
 * @type {Function|null}
 */
let onFolderFilterCallback = null;

/**
 * 폴더 필터 콜백 설정
 * @param {Function} callback - 폴더 선택 시 호출될 콜백
 */
export function setFolderFilterCallback(callback) {
    onFolderFilterCallback = callback;
}

/**
 * 폴더 트리 로드 및 렌더링
 */
export async function loadFolders() {
    try {
        const response = await fetch('api/folders');
        const data = await response.json();

        if (data.success) {
            foldersCache = data.folders;
            renderFolderTree(data.folders);
        }
    } catch (error) {
        console.error('폴더 로드 실패:', error);
    }
}

/**
 * 폴더 트리 렌더링
 * @param {Array} folders - 폴더 트리 데이터
 */
function renderFolderTree(folders) {
    const container = document.getElementById('folder-tree');
    if (!container) return;

    container.innerHTML = '';

    // "전체 문서" 항목
    const allItem = createFolderItem({
        id: null,
        name: '전체 문서',
        icon: 'files',
        document_count: getTotalDocumentCount(folders)
    }, true);
    container.appendChild(allItem);

    // 폴더 트리 렌더링
    folders.forEach(folder => {
        const folderElement = createFolderElement(folder, 0);
        container.appendChild(folderElement);
    });

    // "미분류" 항목
    const unassignedItem = createFolderItem({
        id: '_unassigned',
        name: '미분류',
        icon: 'file-question',
        document_count: 0
    }, false);
    container.appendChild(unassignedItem);

    // 새 폴더 버튼
    const addBtn = document.createElement('button');
    addBtn.className = 'folder-add-btn';
    addBtn.innerHTML = '<span>+</span> 새 폴더';
    addBtn.onclick = () => showCreateFolderDialog();
    container.appendChild(addBtn);
}

/**
 * 전체 문서 수 계산
 * @param {Array} folders - 폴더 목록
 * @returns {number}
 */
function getTotalDocumentCount(folders) {
    let total = 0;
    folders.forEach(folder => {
        total += folder.document_count || 0;
        if (folder.children_data) {
            total += getTotalDocumentCount(folder.children_data);
        }
    });
    return total;
}

/**
 * 폴더 요소 생성 (재귀)
 * @param {Object} folder - 폴더 데이터
 * @param {number} depth - 깊이
 * @returns {HTMLElement}
 */
function createFolderElement(folder, depth) {
    const item = createFolderItem(folder, false, depth);

    // 하위 폴더가 있는 경우
    if (folder.children_data && folder.children_data.length > 0) {
        const children = document.createElement('div');
        children.className = 'folder-children';
        children.style.display = 'none';

        folder.children_data.forEach(child => {
            children.appendChild(createFolderElement(child, depth + 1));
        });

        item.appendChild(children);
    }

    return item;
}

/**
 * 폴더 항목 생성
 * @param {Object} folder - 폴더 데이터
 * @param {boolean} isAllDocs - "전체 문서" 항목인지
 * @param {number} depth - 깊이
 * @returns {HTMLElement}
 */
function createFolderItem(folder, isAllDocs = false, depth = 0) {
    const item = document.createElement('div');
    item.className = 'folder-item';
    if (selectedFolderId === folder.id) {
        item.classList.add('selected');
    }
    item.style.paddingLeft = `${12 + depth * 16}px`;
    item.dataset.folderId = folder.id;

    const hasChildren = folder.children_data && folder.children_data.length > 0;

    // 폴더 아이콘
    const icon = getIconForFolder(folder, hasChildren);

    item.innerHTML = `
        <span class="folder-toggle ${hasChildren ? '' : 'hidden'}" onclick="event.stopPropagation(); toggleFolder('${folder.id}')">
            ${hasChildren ? '▶' : ''}
        </span>
        <span class="folder-icon" style="color: ${folder.color || '#6366f1'}">${icon}</span>
        <span class="folder-name">${folder.name}</span>
        <span class="folder-count">${folder.document_count || 0}</span>
    `;

    // 클릭 이벤트
    item.onclick = (e) => {
        if (!e.target.classList.contains('folder-toggle')) {
            selectFolder(folder.id);
        }
    };

    // 우클릭 컨텍스트 메뉴 (시스템 폴더 제외)
    if (!isAllDocs && folder.id !== '_unassigned' && !folder.is_system) {
        item.oncontextmenu = (e) => {
            e.preventDefault();
            showFolderContextMenu(e, folder);
        };
    }

    return item;
}

/**
 * 폴더 아이콘 반환
 * @param {Object} folder - 폴더 데이터
 * @param {boolean} hasChildren - 하위 폴더 여부
 * @returns {string}
 */
function getIconForFolder(folder, hasChildren) {
    if (folder.icon === 'files') return '📑';
    if (folder.icon === 'file-question') return '📄';
    if (folder.icon === 'cloud') return '☁️';
    if (folder.icon === 'building') return '🏢';
    if (folder.icon === 'landmark') return '🏛️';
    return hasChildren ? '📂' : '📁';
}

/**
 * 폴더 펼침/접기
 * @param {string} folderId - 폴더 ID
 */
export function toggleFolder(folderId) {
    const item = document.querySelector(`.folder-item[data-folder-id="${folderId}"]`);
    if (!item) return;

    const children = item.querySelector('.folder-children');
    const toggle = item.querySelector('.folder-toggle');

    if (children) {
        const isOpen = children.style.display !== 'none';
        children.style.display = isOpen ? 'none' : 'block';
        toggle.textContent = isOpen ? '▶' : '▼';
    }
}
window.toggleFolder = toggleFolder;

/**
 * 폴더 선택
 * @param {string|null} folderId - 폴더 ID (null이면 전체)
 */
export function selectFolder(folderId) {
    // 이전 선택 해제
    document.querySelectorAll('.folder-item.selected').forEach(el => {
        el.classList.remove('selected');
    });

    // 새 선택
    selectedFolderId = folderId;
    const item = document.querySelector(`.folder-item[data-folder-id="${folderId}"]`);
    if (item) {
        item.classList.add('selected');
    }

    // 콜백 호출
    if (onFolderFilterCallback) {
        onFolderFilterCallback(folderId);
    }
}

/**
 * 현재 선택된 폴더 ID 반환
 * @returns {string|null}
 */
export function getSelectedFolderId() {
    return selectedFolderId;
}

/**
 * 새 폴더 생성 다이얼로그
 * @param {string|null} parentId - 부모 폴더 ID
 */
export function showCreateFolderDialog(parentId = null) {
    const name = prompt('새 폴더 이름을 입력하세요:');
    if (!name || !name.trim()) return;

    createFolder(name.trim(), parentId);
}

/**
 * 폴더 생성 API 호출
 * @param {string} name - 폴더 이름
 * @param {string|null} parentId - 부모 폴더 ID
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
            loadFolders();
        } else {
            alert('폴더 생성 실패: ' + data.error);
        }
    } catch (error) {
        console.error('폴더 생성 실패:', error);
        alert('폴더 생성 중 오류가 발생했습니다.');
    }
}

/**
 * 폴더 컨텍스트 메뉴 표시
 * @param {MouseEvent} e - 마우스 이벤트
 * @param {Object} folder - 폴더 데이터
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
        <div class="context-menu-item" onclick="renameFolderPrompt('${folder.id}', '${folder.name}')">
            <span>📝</span> 이름 바꾸기
        </div>
        <div class="context-menu-item" onclick="showCreateFolderDialogWithParent('${folder.id}')">
            <span>📁</span> 하위 폴더 추가
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item danger" onclick="deleteFolderPrompt('${folder.id}', '${folder.name}')">
            <span>🗑️</span> 삭제
        </div>
    `;

    document.body.appendChild(menu);

    // 클릭 시 메뉴 닫기
    const closeMenu = () => {
        menu.remove();
        document.removeEventListener('click', closeMenu);
    };
    setTimeout(() => document.addEventListener('click', closeMenu), 0);
}

/**
 * 폴더 이름 변경 프롬프트
 * @param {string} folderId - 폴더 ID
 * @param {string} currentName - 현재 이름
 */
window.renameFolderPrompt = async function(folderId, currentName) {
    const newName = prompt('새 이름을 입력하세요:', currentName);
    if (!newName || newName.trim() === currentName) return;

    try {
        const response = await fetch(`api/folders/${folderId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName.trim() })
        });

        const data = await response.json();
        if (data.success) {
            loadFolders();
        } else {
            alert('이름 변경 실패: ' + data.error);
        }
    } catch (error) {
        console.error('이름 변경 실패:', error);
    }
};

/**
 * 하위 폴더 생성 다이얼로그
 * @param {string} parentId - 부모 폴더 ID
 */
window.showCreateFolderDialogWithParent = function(parentId) {
    showCreateFolderDialog(parentId);
};

/**
 * 폴더 삭제 확인
 * @param {string} folderId - 폴더 ID
 * @param {string} folderName - 폴더 이름
 */
window.deleteFolderPrompt = async function(folderId, folderName) {
    if (!confirm(`'${folderName}' 폴더를 삭제하시겠습니까?`)) return;

    try {
        const response = await fetch(`api/folders/${folderId}?recursive=true`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.success) {
            if (selectedFolderId === folderId) {
                selectFolder(null);
            }
            loadFolders();
        } else {
            alert('삭제 실패: ' + data.error);
        }
    } catch (error) {
        console.error('삭제 실패:', error);
    }
};

/**
 * 문서를 폴더에 할당
 * @param {string} docId - 문서 ID
 * @param {string} folderId - 폴더 ID
 * @param {string} collection - 컬렉션명 (기본값: documents)
 */
export async function assignDocumentToFolder(docId, folderId, collection = 'documents') {
    try {
        const response = await fetch(`api/folders/${folderId}/documents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ doc_id: docId, collection: collection })
        });

        const data = await response.json();
        if (data.success) {
            loadFolders();
            return true;
        }
        return false;
    } catch (error) {
        console.error('폴더 할당 실패:', error);
        return false;
    }
}

/**
 * 문서를 폴더에서 제거
 * @param {string} docId - 문서 ID
 * @param {string} folderId - 폴더 ID
 */
export async function removeDocumentFromFolder(docId, folderId) {
    try {
        const response = await fetch(`api/folders/${folderId}/documents/${encodeURIComponent(docId)}`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.success) {
            loadFolders();
            return true;
        }
        return false;
    } catch (error) {
        console.error('폴더에서 제거 실패:', error);
        return false;
    }
}

/**
 * 문서의 폴더 정보 조회
 * @param {string} docId - 문서 ID
 * @returns {Promise<Object|null>}
 */
export async function getDocumentFolder(docId) {
    try {
        const response = await fetch(`api/folders/document/${encodeURIComponent(docId)}`);
        const data = await response.json();

        if (data.success) {
            return data.folder;
        }
        return null;
    } catch (error) {
        console.error('문서 폴더 조회 실패:', error);
        return null;
    }
}

/**
 * 폴더 내 문서 ID 목록 조회
 * @param {string} folderId - 폴더 ID
 * @param {boolean} includeSubfolders - 하위 폴더 포함 여부
 * @returns {Promise<string[]>}
 */
export async function getDocumentsInFolder(folderId, includeSubfolders = false) {
    try {
        const url = `api/folders/${folderId}/documents?include_subfolders=${includeSubfolders}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            return data.documents;
        }
        return [];
    } catch (error) {
        console.error('폴더 문서 조회 실패:', error);
        return [];
    }
}
