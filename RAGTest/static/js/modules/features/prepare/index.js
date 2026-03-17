// ===================================================================
// 문서 준비 탭 모듈
// 파일 업로드, 크롤링, 벡터DB 저장 통합
// ===================================================================

import {
    handleFileUpload,
    loadFileList,
    selectAllFiles,
    clearAllFiles,
    processFiles,
    setDocumentsLoadCallback
} from './upload.js';

import {
    startGenericCrawling,
    setCrawlDocumentsLoadCallback,
    loadCrawlCategories,
    setupFullCrawlCategoryButtons,
    setupZoneChangeHandler,
    setupDocTypeChangeHandler,
    startFullCrawling,
    stopFullCrawling
} from './crawling.js';

import { initTextInput } from './text-input.js';

/**
 * 문서 준비 탭 초기화
 */
export function initDocumentPrepareTab() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const loadFilesBtn = document.getElementById('load-files-btn');
    const selectAllBtn = document.getElementById('select-all-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const processBtn = document.getElementById('process-btn');
    const genericCrawlBtn = document.getElementById('generic-crawl-btn');

    // 드래그 앤 드롭
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', async (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        await handleFileUpload(files);
    });

    // 파일 선택
    fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        await handleFileUpload(files);
    });

    // 저장된 파일에서 선택
    loadFilesBtn.addEventListener('click', loadFileList);

    // 모두 선택/해제
    selectAllBtn.addEventListener('click', selectAllFiles);
    clearAllBtn.addEventListener('click', clearAllFiles);

    // 벡터DB에 저장
    processBtn.addEventListener('click', processFiles);

    // 범용 URL 크롤링
    if (genericCrawlBtn) {
        genericCrawlBtn.addEventListener('click', startGenericCrawling);
    }

    // 전체 가이드 크롤링
    const fullCrawlBtn = document.getElementById('full-crawl-btn');
    const fullCrawlStopBtn = document.getElementById('full-crawl-stop-btn');

    if (fullCrawlBtn) {
        fullCrawlBtn.addEventListener('click', startFullCrawling);
    }

    if (fullCrawlStopBtn) {
        fullCrawlStopBtn.addEventListener('click', stopFullCrawling);
    }

    // 카테고리 목록 로드 및 버튼 설정
    loadCrawlCategories();
    setupFullCrawlCategoryButtons();

    // Zone 변경 시 카테고리 재로드 이벤트 설정
    setupZoneChangeHandler();

    // 문서 유형 변경 시 카테고리 재로드 이벤트 설정
    setupDocTypeChangeHandler();

    // 텍스트 직접 입력 초기화
    initTextInput();
}

/**
 * 문서 로드 콜백 설정 (upload와 crawling 모듈에 전달)
 * @param {Function} callback - 문서 로드 시 호출될 콜백
 */
export function setPrepareDocumentsLoadCallback(callback) {
    setDocumentsLoadCallback(callback);
    setCrawlDocumentsLoadCallback(callback);
}

// Re-export for direct access
export {
    handleFileUpload,
    loadFileList,
    selectAllFiles,
    clearAllFiles,
    processFiles,
    startGenericCrawling,
    startFullCrawling,
    stopFullCrawling,
    loadCrawlCategories
};
