// ===================================================================
// API 서비스 모듈
// 모든 백엔드 API 호출을 중앙화
// ===================================================================

/**
 * API 기본 설정
 */
const BASE_URL = '';  // 같은 도메인

/**
 * 공통 fetch 래퍼
 * @param {string} url - API URL
 * @param {Object} options - fetch 옵션
 * @returns {Promise<Object>} 응답 데이터
 */
async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
}

// ===================================================================
// 파일 관련 API
// ===================================================================

export const filesApi = {
    /**
     * 파일 업로드
     * @param {File} file - 업로드할 파일
     * @param {string} category - 카테고리 ID
     * @returns {Promise<Object>} 업로드 결과
     */
    async upload(file, category = 'general') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', category);

        const response = await fetch('api/upload', {
            method: 'POST',
            body: formData
        });

        return response.json();
    },

    /**
     * 파일 목록 조회
     * @returns {Promise<Object>} 파일 목록
     */
    async list() {
        return fetchJSON('api/files');
    },

    /**
     * 파일 삭제
     * @param {string} filename - 파일명
     * @param {boolean} includeVectors - 벡터 포함 삭제 여부
     * @returns {Promise<Object>} 삭제 결과
     */
    async delete(filename, includeVectors = true) {
        const url = `/api/files/${encodeURIComponent(filename)}?include_vectors=${includeVectors}`;
        const response = await fetch(url, { method: 'DELETE' });
        return response.json();
    },

    /**
     * 파일 카테고리 업데이트
     * @param {string} filename - 파일명
     * @param {string} categoryId - 카테고리 ID
     * @returns {Promise<Object>} 업데이트 결과
     */
    async updateCategory(filename, categoryId) {
        return fetchJSON('api/files/category', {
            method: 'PUT',
            body: JSON.stringify({
                filename: filename,
                category_id: categoryId
            })
        });
    }
};

// ===================================================================
// 문서 관련 API
// ===================================================================

export const documentsApi = {
    /**
     * 벡터DB 문서 목록 조회
     * @returns {Promise<Object>} 문서 목록
     */
    async list() {
        return fetchJSON('api/documents');
    },

    /**
     * 문서 삭제
     * @param {string} filename - 파일명
     * @param {string} scope - 삭제 범위 (all, vector_only, file_only)
     * @param {string|null} collection - 컬렉션명
     * @returns {Promise<Object>} 삭제 결과
     */
    async delete(filename, scope = 'all', collection = null) {
        let url = `/api/documents/${encodeURIComponent(filename)}?scope=${scope}`;
        if (collection) {
            url += `&collection=${encodeURIComponent(collection)}`;
        }
        const response = await fetch(url, { method: 'DELETE' });
        return response.json();
    },

    /**
     * 전체 문서 삭제
     * @param {string} scope - 삭제 범위
     * @returns {Promise<Object>} 삭제 결과
     */
    async deleteAll(scope = 'all') {
        const response = await fetch(`/api/documents?confirm=true&scope=${scope}`, {
            method: 'DELETE'
        });
        return response.json();
    },

    /**
     * 문서 카테고리 업데이트
     * @param {string} filename - 파일명
     * @param {string} collection - 컬렉션명
     * @param {string} categoryId - 카테고리 ID
     * @returns {Promise<Object>} 업데이트 결과
     */
    async updateCategory(filename, collection, categoryId) {
        return fetchJSON('api/documents/category', {
            method: 'PUT',
            body: JSON.stringify({
                filename: filename,
                collection: collection,
                category_id: categoryId
            })
        });
    },

    /**
     * 다중 컬렉션 로드
     * @param {Array<string>} collections - 컬렉션 ID 배열
     * @returns {Promise<Object>} 로드 결과
     */
    async loadMultipleCollections(collections) {
        return fetchJSON('api/documents/load-multiple-collections', {
            method: 'POST',
            body: JSON.stringify({ collections: collections })
        });
    },

    /**
     * 로드된 문서 목록 조회
     * @returns {Promise<Object>} 로드된 문서 목록
     */
    async getLoaded() {
        return fetchJSON('api/loaded-documents');
    },

    /**
     * 로드된 문서 목록 조회 (다른 엔드포인트)
     * @returns {Promise<Object>} 로드된 문서 목록
     */
    async getLoadedDocuments() {
        return fetchJSON('api/documents/loaded');
    },

    /**
     * 문서 상태 조회
     * @returns {Promise<Object>} 상태 정보
     */
    async getStatus() {
        return fetchJSON('api/documents/status');
    },

    /**
     * 청크 미리보기 조회
     * @param {string} filename - 파일명
     * @param {string} collection - 컬렉션명
     * @param {number} limit - 조회할 청크 수
     * @returns {Promise<Object>} 청크 미리보기
     */
    async getChunksPreview(filename, collection, limit = 3) {
        return fetchJSON(
            `/api/documents/${encodeURIComponent(filename)}/chunks/preview?collection=${encodeURIComponent(collection)}&limit=${limit}`
        );
    },

    /**
     * 청크 페이지네이션 조회
     * @param {string} filename - 파일명
     * @param {string} collection - 컬렉션명
     * @param {number} page - 페이지 번호
     * @param {number} perPage - 페이지당 항목 수
     * @returns {Promise<Object>} 청크 목록
     */
    async getChunks(filename, collection, page = 1, perPage = 10) {
        return fetchJSON(
            `/api/documents/${encodeURIComponent(filename)}/chunks?collection=${encodeURIComponent(collection)}&page=${page}&per_page=${perPage}`
        );
    }
};

// ===================================================================
// 처리 관련 API
// ===================================================================

export const processApi = {
    /**
     * 파일을 벡터DB에 저장
     * @param {Array<string>} filePaths - 파일 경로 배열
     * @returns {Promise<Object>} 처리 결과
     */
    async loadFiles(filePaths) {
        return fetchJSON('api/load', {
            method: 'POST',
            body: JSON.stringify({ files: filePaths })
        });
    }
};

// ===================================================================
// 질의응답 관련 API
// ===================================================================

export const queryApi = {
    /**
     * 스트리밍 질의 (ReadableStream 반환)
     * @param {string} question - 질문
     * @param {boolean} secureMode - 보안 모드 여부
     * @returns {Promise<Response>} fetch Response 객체
     */
    async stream(question, secureMode = false) {
        return fetch('api/query/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                secure_mode: secureMode
            })
        });
    }
};

// ===================================================================
// 크롤링 관련 API
// ===================================================================

export const crawlApi = {
    /**
     * 스트리밍 크롤링 (ReadableStream 반환)
     * @param {Object} options - 크롤링 옵션
     * @param {string} options.url - 크롤링 URL
     * @param {boolean} options.headless - 헤드리스 모드
     * @param {number} options.maxPages - 최대 페이지 수 (ncloud만)
     * @param {string} options.categoryId - 카테고리 ID
     * @param {string} options.crawlerType - 크롤러 타입 (ncloud, generic)
     * @returns {Promise<Response>} fetch Response 객체
     */
    async stream(options) {
        return fetch('api/crawl/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(options)
        });
    }
};

// ===================================================================
// 카테고리 관련 API
// ===================================================================

export const categoriesApi = {
    /**
     * 카테고리 목록 조회
     * @returns {Promise<Object>} 카테고리 목록
     */
    async list() {
        return fetchJSON('api/categories');
    }
};

// ===================================================================
// 통합 API 객체
// ===================================================================

export const api = {
    files: filesApi,
    documents: documentsApi,
    process: processApi,
    query: queryApi,
    crawl: crawlApi,
    categories: categoriesApi
};

export default api;
