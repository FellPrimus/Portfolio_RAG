// ===================================================================
// 전역 상태 관리 모듈
// ===================================================================

/**
 * 애플리케이션 전역 상태
 * 모든 탭과 컴포넌트에서 공유되는 상태를 중앙 관리
 */
export const state = {
    // 문서 준비 탭: 선택된 파일 경로
    selectedFiles: new Set(),

    // 문서 관리 탭: 모든 벡터DB 문서
    allDocsInManage: [],

    // 모달: 선택 가능한 모든 문서
    allDocsInModal: [],

    // 모달: 선택된 문서 컬렉션
    selectedDocsInModal: new Set(),

    // 카테고리 목록
    categories: [],

    // 질의응답 준비 상태
    isReady: false,

    // 청크 페이지네이션
    pagination: {
        currentPage: 1,
        perPage: 10
    },

    // 현재 청크 모달 데이터
    currentChunksData: {
        filename: '',
        collection: '',
        totalChunks: 0
    }
};

/**
 * 선택된 파일 추가
 * @param {string} filePath - 파일 경로
 */
export function addSelectedFile(filePath) {
    state.selectedFiles.add(filePath);
}

/**
 * 선택된 파일 제거
 * @param {string} filePath - 파일 경로
 */
export function removeSelectedFile(filePath) {
    state.selectedFiles.delete(filePath);
}

/**
 * 선택된 파일 모두 초기화
 */
export function clearSelectedFiles() {
    state.selectedFiles.clear();
}

/**
 * 문서 관리 목록 설정
 * @param {Array} documents - 문서 배열
 */
export function setManageDocuments(documents) {
    state.allDocsInManage = documents;
}

/**
 * 모달 문서 목록 설정
 * @param {Array} documents - 문서 배열
 */
export function setModalDocuments(documents) {
    state.allDocsInModal = documents;
}

/**
 * 모달에서 문서 선택 추가
 * @param {string} collection - 컬렉션 ID
 */
export function addModalSelection(collection) {
    state.selectedDocsInModal.add(collection);
}

/**
 * 모달에서 문서 선택 제거
 * @param {string} collection - 컬렉션 ID
 */
export function removeModalSelection(collection) {
    state.selectedDocsInModal.delete(collection);
}

/**
 * 모달 선택 초기화
 */
export function clearModalSelections() {
    state.selectedDocsInModal.clear();
}

/**
 * 카테고리 목록 설정
 * @param {Array} categories - 카테고리 배열
 */
export function setCategories(categories) {
    state.categories = categories;
}

/**
 * 질의응답 준비 상태 설정
 * @param {boolean} ready - 준비 상태
 */
export function setReady(ready) {
    state.isReady = ready;
}

/**
 * 청크 페이지네이션 설정
 * @param {number} page - 현재 페이지
 */
export function setCurrentPage(page) {
    state.pagination.currentPage = page;
}

/**
 * 청크 모달 데이터 설정
 * @param {string} filename - 파일명
 * @param {string} collection - 컬렉션 ID
 * @param {number} totalChunks - 총 청크 수
 */
export function setChunksData(filename, collection, totalChunks) {
    state.currentChunksData = { filename, collection, totalChunks };
}

/**
 * 상태 초기화 (전체 리셋)
 */
export function resetState() {
    state.selectedFiles.clear();
    state.allDocsInManage = [];
    state.allDocsInModal = [];
    state.selectedDocsInModal.clear();
    state.categories = [];
    state.isReady = false;
    state.pagination.currentPage = 1;
    state.currentChunksData = { filename: '', collection: '', totalChunks: 0 };
}
