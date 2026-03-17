// ===================================================================
// 파일 업로드 및 관리 모듈
// 파일 업로드, 목록 표시, 선택, 삭제 기능
// ===================================================================

import { state } from '../../state.js';
import { formatBytes, getFileTypeInfo, showLoading, hideLoading, showErrorMessage, addProgressLog } from '../../utils.js';

/**
 * 벡터DB 문서 로드 콜백
 * @type {Function|null}
 */
let onDocumentsLoadCallback = null;

/**
 * 문서 로드 콜백 설정
 * @param {Function} callback - 문서 로드 시 호출될 콜백
 */
export function setDocumentsLoadCallback(callback) {
    onDocumentsLoadCallback = callback;
}

/**
 * 파일 업로드 처리
 * @param {File[]} files - 업로드할 파일 배열
 */
export async function handleFileUpload(files) {
    if (files.length === 0) return;

    showLoading('파일 업로드 중...');

    const defaultCategory = 'general';

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', defaultCategory);

        try {
            const response = await fetch('api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                console.log(`✅ 업로드 성공: ${file.name}`);
            } else {
                alert(`업로드 실패: ${file.name} - ${data.error}`);
            }
        } catch (error) {
            alert(`업로드 오류: ${file.name} - ${error.message}`);
        }
    }

    hideLoading();
    loadFileList();
}

/**
 * 파일 카테고리 업데이트
 * @param {string} filename - 파일명
 * @param {string} categoryId - 카테고리 ID
 */
export async function updateFileCategory(filename, categoryId) {
    try {
        const response = await fetch('api/files/category', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                category_id: categoryId
            })
        });

        const data = await response.json();

        if (data.success) {
            console.log(`✅ 카테고리 변경 성공: ${filename} -> ${categoryId}`);
        } else {
            alert(`카테고리 변경 실패: ${data.error}`);
            loadFileList();
        }
    } catch (error) {
        alert(`오류 발생: ${error.message}`);
        loadFileList();
    }
}

/**
 * 파일 목록 로드
 */
export async function loadFileList() {
    showLoading('파일 목록 불러오는 중...');

    try {
        const response = await fetch('api/files');
        const data = await response.json();

        if (data.success) {
            displayFileList(data.files);
        } else {
            alert('파일 목록 불러오기 실패: ' + data.error);
        }
    } catch (error) {
        alert('오류 발생: ' + error.message);
    } finally {
        hideLoading();
    }
}

/**
 * 파일 목록 표시
 * @param {Array} files - 파일 배열
 */
async function displayFileList(files) {
    const fileList = document.getElementById('file-list');
    const filesSection = document.getElementById('files-section');
    const processBtn = document.getElementById('process-btn');

    if (files.length === 0) {
        fileList.innerHTML = '<p style="color: #718096; padding: 20px; text-align: center;">문서 파일이 없습니다.</p>';
        filesSection.style.display = 'none';
        return;
    }

    filesSection.style.display = 'block';
    fileList.innerHTML = '';

    // 중복 체크: 벡터DB에 이미 있는 파일 목록
    let existingFiles = new Set();
    try {
        const response = await fetch('api/documents');
        const data = await response.json();
        if (data.success && data.documents.length > 0) {
            existingFiles = new Set(data.documents.map(doc => doc.filename));
        }
    } catch (error) {
        console.error('중복 체크 실패:', error);
    }

    files.forEach(file => {
        const typeInfo = getFileTypeInfo(file.type);
        const currentCategory = file.category ? file.category.id : 'general';
        const isDuplicate = existingFiles.has(file.name);

        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        if (isDuplicate) {
            fileItem.classList.add('file-duplicate');
        }

        fileItem.style.cssText = `display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid ${isDuplicate ? '#f59e0b' : '#e2e8f0'}; border-radius: 8px; margin-bottom: 8px; background: ${isDuplicate ? '#fffbeb' : 'white'};`;
        fileItem.innerHTML = `
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

        // 체크박스 이벤트
        const checkbox = fileItem.querySelector('.file-checkbox');
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedFiles.add(file.path);
                fileItem.classList.add('selected');
                fileItem.style.background = '#f0f9ff';
                fileItem.style.borderColor = '#3b82f6';
            } else {
                state.selectedFiles.delete(file.path);
                fileItem.classList.remove('selected');
                fileItem.style.background = 'white';
                fileItem.style.borderColor = '#e2e8f0';
            }
            processBtn.style.display = state.selectedFiles.size > 0 ? 'block' : 'none';
        });

        // 카테고리 변경 이벤트
        const categorySelect = fileItem.querySelector('.file-category-select');
        categorySelect.addEventListener('change', async (e) => {
            const newCategory = e.target.value;
            const filename = e.target.dataset.filename;
            await updateFileCategory(filename, newCategory);
        });

        // 삭제 버튼 이벤트
        const deleteBtn = fileItem.querySelector('.file-delete-btn');
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const filename = e.target.dataset.filename;
            if (confirm(`파일 "${filename}"을(를) 삭제하시겠습니까?`)) {
                await deleteFile(filename);
            }
        });

        // 파일 아이템 클릭 시 체크박스 토글
        fileItem.addEventListener('click', (e) => {
            if (e.target !== checkbox &&
                !e.target.classList.contains('file-delete-btn') &&
                !e.target.classList.contains('file-category-select')) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
            }
        });

        fileList.appendChild(fileItem);
    });

    processBtn.style.display = 'none';
}

/**
 * 모든 파일 선택
 */
export function selectAllFiles() {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change'));
    });
}

/**
 * 모든 파일 선택 해제
 */
export function clearAllFiles() {
    const checkboxes = document.querySelectorAll('.file-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
        checkbox.dispatchEvent(new Event('change'));
    });
    state.selectedFiles.clear();
    document.getElementById('process-btn').style.display = 'none';
}

/**
 * 파일 삭제
 * @param {string} filename - 삭제할 파일명
 * @param {boolean} includeVectors - 벡터 DB도 함께 삭제할지 여부
 */
export async function deleteFile(filename, includeVectors = true) {
    const message = includeVectors
        ? `"${filename}"을(를) 삭제하시겠습니까?\n\n⚠️ 원본 파일과 벡터 DB 데이터가 모두 삭제됩니다.`
        : `"${filename}"을(를) 삭제하시겠습니까?\n\n📝 원본 파일만 삭제되며, 벡터 DB 데이터는 유지됩니다.`;

    if (!confirm(message)) return;

    showLoading(`파일 "${filename}" 삭제 중...`);

    try {
        const url = `/api/files/${encodeURIComponent(filename)}?include_vectors=${includeVectors}`;
        const response = await fetch(url, { method: 'DELETE' });
        const result = await response.json();

        if (result.success) {
            let successMsg = `파일 "${filename}"이(가) 삭제되었습니다.`;

            if (result.deleted) {
                const deletedItems = [];
                if (result.deleted.original_file) deletedItems.push('원본 파일');
                if (result.deleted.vector_chunks) deletedItems.push('벡터 데이터');
                if (deletedItems.length > 0) {
                    successMsg += `\n\n삭제됨: ${deletedItems.join(', ')}`;
                }
            }

            if (result.details) {
                if (result.details.deleted_chunks) {
                    successMsg += `\n청크: ${result.details.deleted_chunks}개`;
                }
            }

            alert(successMsg);
            await loadFileList();

            // 벡터 DB도 삭제한 경우 문서 목록도 갱신
            if (includeVectors && onDocumentsLoadCallback) {
                await onDocumentsLoadCallback();
            }
        } else {
            alert(`파일 삭제 실패: ${result.error || '알 수 없는 오류'}`);
        }
    } catch (error) {
        alert(`오류 발생: ${error.message}`);
        console.error('파일 삭제 오류:', error);
    } finally {
        hideLoading();
    }
}

/**
 * 파일 벡터DB 저장 처리
 */
export async function processFiles() {
    if (state.selectedFiles.size === 0) {
        showErrorMessage(
            '파일을 선택해주세요',
            '벡터DB에 저장할 파일이 선택되지 않았습니다.',
            '📁 "저장된 파일에서 선택" 버튼을 클릭하여 파일을 선택해주세요.'
        );
        return;
    }

    // 중복 체크
    showLoading('중복 파일 확인 중...');

    try {
        const docsResponse = await fetch('api/documents');
        const docsData = await docsResponse.json();

        const existingFiles = new Set();
        if (docsData.success && docsData.documents.length > 0) {
            docsData.documents.forEach(doc => {
                existingFiles.add(doc.filename);
            });
        }

        // 중복 파일 체크
        const filesToProcess = Array.from(state.selectedFiles);
        const duplicates = filesToProcess.filter(filePath => {
            const filename = filePath.split('\\').pop().split('/').pop();
            return existingFiles.has(filename);
        });

        if (duplicates.length > 0) {
            hideLoading();
            const duplicateNames = duplicates.map(fp => fp.split('\\').pop().split('/').pop()).join('\n  • ');
            const proceed = confirm(
                `⚠️ 다음 파일은 이미 벡터DB에 존재합니다:\n\n  • ${duplicateNames}\n\n` +
                `계속 진행하면 기존 데이터를 덮어쓰게 됩니다.\n계속하시겠습니까?`
            );

            if (!proceed) return;
        }
    } catch (error) {
        console.error('중복 체크 실패:', error);
        showErrorMessage(
            '중복 체크 실패',
            '벡터DB 문서 목록을 조회하는 중 오류가 발생했습니다.',
            '네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.',
            [{ text: '다시 시도', action: () => processFiles() }]
        );
        return;
    }

    hideLoading();

    // 진행률 표시 UI 준비
    const fileItems = [];
    const checkboxes = document.querySelectorAll('.file-checkbox:checked');

    checkboxes.forEach(checkbox => {
        const filePath = checkbox.dataset.path;
        const fileItem = checkbox.closest('[style*="display: flex"]');
        const categorySelect = fileItem?.querySelector('.file-category-select');
        const category = categorySelect?.value || 'general';

        fileItems.push({
            path: filePath,
            category: category
        });
    });

    // 진행 상태 섹션 표시
    const progressSection = document.getElementById('progress-section');
    const filesSection = document.getElementById('files-section');
    const progressBar = document.getElementById('process-progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const progressPercent = document.getElementById('progress-percent');
    const progressCurrentFile = document.getElementById('progress-current-file');
    const progressTimeEstimate = document.getElementById('progress-time-estimate');
    const progressLog = document.getElementById('progress-log');

    // 파일 섹션 숨기고 진행 섹션 표시
    filesSection.style.display = 'none';
    progressSection.style.display = 'block';

    // 초기화
    progressStatus.textContent = `0 / ${fileItems.length}`;
    progressBar.style.width = '0%';
    progressPercent.textContent = '0%';
    progressLog.innerHTML = '';

    const totalFiles = fileItems.length;
    let processedFiles = 0;
    const startTime = Date.now();

    try {
        addProgressLog('info', `📋 ${totalFiles}개 파일 처리를 시작합니다...`);

        for (const item of fileItems) {
            const filename = item.path.split('\\').pop().split('/').pop();
            await updateFileCategory(filename, item.category);
        }

        addProgressLog('success', '✅ 카테고리 정보 업데이트 완료');

        addProgressLog('info', '📦 벡터DB 저장 중...');
        progressCurrentFile.textContent = `${totalFiles}개 파일 처리 중...`;

        const response = await fetch('api/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: fileItems.map(f => f.path) })
        });

        const data = await response.json();

        if (data.success) {
            processedFiles = totalFiles;
            const percent = 100;
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${percent}%`;
            progressStatus.textContent = `${processedFiles} / ${totalFiles}`;

            const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(1);
            progressTimeEstimate.textContent = `완료 (${elapsedTime}초 소요)`;

            const fileCount = data.stats?.files || data.stats?.processed_files || fileItems.length;
            const chunkCount = data.stats?.chunks || data.stats?.total_chunks || 0;

            addProgressLog('success', `✅ 벡터DB 저장 완료: ${fileCount}개 파일, ${chunkCount}개 청크 생성`);

            await new Promise(resolve => setTimeout(resolve, 2000));

            // 완료 상태 표시
            const statusProcessed = document.getElementById('status-processed');
            const statusChunks = document.getElementById('status-chunks');
            const statusSection = document.getElementById('status-section');

            if (statusProcessed) {
                statusProcessed.innerHTML = `저장된 파일: <strong>${fileCount}개</strong>`;
            }
            if (statusChunks) {
                statusChunks.innerHTML = `생성된 청크: <strong>${chunkCount}개</strong>`;
            }

            progressSection.style.display = 'none';
            if (statusSection) {
                statusSection.style.display = 'block';
            }

            state.selectedFiles.clear();

            // 문서 관리 탭 새로고침
            if (onDocumentsLoadCallback) {
                await onDocumentsLoadCallback();
            }

            console.log('✅ 벡터DB 저장 완료');
        } else {
            addProgressLog('error', `❌ 저장 실패: ${data.error}`);
            progressSection.style.display = 'none';
            filesSection.style.display = 'block';

            showErrorMessage(
                '벡터DB 저장 실패',
                `파일을 벡터DB에 저장하는 중 오류가 발생했습니다: ${data.error}`,
                '가능한 원인:\n• 파일 형식이 지원되지 않음\n• 파일이 손상됨\n• 서버 메모리 부족\n\n다른 파일을 선택하거나 파일 형식을 확인해주세요.',
                [
                    { text: '파일 다시 선택', action: () => { filesSection.style.display = 'block'; } },
                    { text: '확인', action: null }
                ]
            );
        }
    } catch (error) {
        console.error('파일 처리 오류:', error);
        addProgressLog('error', `❌ 오류 발생: ${error.message}`);

        progressSection.style.display = 'none';
        filesSection.style.display = 'block';

        showErrorMessage(
            '파일 처리 중 오류 발생',
            `예상치 못한 오류가 발생했습니다: ${error.message}`,
            '가능한 해결 방법:\n• 페이지를 새로고침 후 다시 시도\n• 파일 크기가 너무 큰 경우 분할 처리\n• 브라우저 콘솔에서 자세한 오류 확인',
            [
                { text: '페이지 새로고침', action: () => location.reload() },
                { text: '다시 시도', action: () => processFiles() }
            ]
        );
    }
}
