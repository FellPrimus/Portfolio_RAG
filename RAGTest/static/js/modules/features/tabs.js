// ===================================================================
// 탭 전환 시스템 모듈
// ===================================================================

/**
 * 탭 전환 콜백 함수 타입
 * @callback TabChangeCallback
 * @param {string} tabName - 전환된 탭 이름
 */

/** @type {TabChangeCallback|null} */
let onTabChangeCallback = null;

/**
 * 탭 전환 콜백 설정
 * @param {TabChangeCallback} callback - 탭 전환 시 호출될 콜백
 */
export function setTabChangeCallback(callback) {
    onTabChangeCallback = callback;
}

/**
 * 탭 네비게이션 초기화
 * 사이드바의 탭 버튼에 클릭 이벤트 리스너 등록
 */
export function initTabNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(nav => {
        nav.addEventListener('click', () => {
            const tabName = nav.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

/**
 * 탭 전환
 * @param {string} tabName - 전환할 탭 이름 (prepare, chat, manage)
 */
export function switchTab(tabName) {
    // 모든 탭 콘텐츠 숨기기
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // 모든 네비게이션 비활성화
    document.querySelectorAll('.nav-item').forEach(nav => {
        nav.classList.remove('active');
    });

    // 선택한 탭 활성화
    const selectedTab = document.getElementById(`tab-${tabName}`);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    const selectedNav = document.querySelector(`[data-tab="${tabName}"]`);
    if (selectedNav) {
        selectedNav.classList.add('active');
    }

    // 탭 전환 콜백 실행
    if (onTabChangeCallback) {
        onTabChangeCallback(tabName);
    }
}

// 전역 함수로 노출 (HTML onclick에서 사용)
window.switchTab = switchTab;
