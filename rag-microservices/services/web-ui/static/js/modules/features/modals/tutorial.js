/**
 * 튜토리얼 모달 모듈
 *
 * 최초 접속 사용자에게 튜토리얼을 표시하고,
 * "사용 방법" 버튼으로 언제든 다시 볼 수 있게 합니다.
 */

const TUTORIAL_STORAGE_KEY = 'ragtest_tutorial_completed';
let currentSlide = 0;
const totalSlides = 7;

/**
 * 튜토리얼 모달 초기화
 * 버튼 이벤트 리스너 등록
 */
export function initTutorial() {
    const prevBtn = document.getElementById('tutorial-prev-btn');
    const nextBtn = document.getElementById('tutorial-next-btn');
    const closeBtn = document.getElementById('tutorial-close-btn');
    const indicators = document.querySelectorAll('.tutorial-indicators .indicator');

    if (prevBtn) prevBtn.addEventListener('click', goToPrevSlide);
    if (nextBtn) nextBtn.addEventListener('click', goToNextSlide);
    if (closeBtn) closeBtn.addEventListener('click', completeTutorial);

    // 인디케이터 클릭 이벤트
    indicators.forEach(indicator => {
        indicator.addEventListener('click', (e) => {
            const slideIndex = parseInt(e.target.dataset.slide);
            if (!isNaN(slideIndex)) {
                goToSlide(slideIndex);
            }
        });
    });
}

/**
 * 최초 접속 시 튜토리얼 자동 표시
 */
export function checkAndShowTutorial() {
    const completed = localStorage.getItem(TUTORIAL_STORAGE_KEY);
    if (!completed) {
        // UI가 완전히 로드된 후 표시
        setTimeout(() => showTutorialModal(), 500);
    }
}

/**
 * 튜토리얼 모달 표시
 */
export function showTutorialModal() {
    currentSlide = 0;
    // 체크박스 초기화
    const checkbox = document.getElementById('tutorial-dont-show-again');
    if (checkbox) checkbox.checked = false;

    updateSlideDisplay();
    document.getElementById('tutorial-modal').style.display = 'flex';
}

/**
 * 튜토리얼 모달 닫기
 * "다시 보지 않기" 체크 상태도 반영
 */
export function closeTutorialModal() {
    const dontShowAgain = document.getElementById('tutorial-dont-show-again');
    if (dontShowAgain && dontShowAgain.checked) {
        localStorage.setItem(TUTORIAL_STORAGE_KEY, 'true');
    }
    document.getElementById('tutorial-modal').style.display = 'none';
}

/**
 * 튜토리얼 완료 처리 ("시작하기" 버튼)
 */
function completeTutorial() {
    closeTutorialModal();
}

/**
 * 다음 슬라이드로 이동
 */
function goToNextSlide() {
    if (currentSlide < totalSlides - 1) {
        goToSlide(currentSlide + 1);
    }
}

/**
 * 이전 슬라이드로 이동
 */
function goToPrevSlide() {
    if (currentSlide > 0) {
        goToSlide(currentSlide - 1);
    }
}

/**
 * 특정 슬라이드로 이동
 */
function goToSlide(slideIndex) {
    currentSlide = slideIndex;
    updateSlideDisplay();
}

/**
 * 슬라이드 표시 상태 업데이트
 */
function updateSlideDisplay() {
    // 슬라이드 활성화
    const slides = document.querySelectorAll('.tutorial-slide');
    slides.forEach((slide, index) => {
        slide.classList.toggle('active', index === currentSlide);
    });

    // 인디케이터 활성화
    const indicators = document.querySelectorAll('.tutorial-indicators .indicator');
    indicators.forEach((indicator, index) => {
        indicator.classList.toggle('active', index === currentSlide);
    });

    // 버튼 상태 업데이트
    const prevBtn = document.getElementById('tutorial-prev-btn');
    const nextBtn = document.getElementById('tutorial-next-btn');
    const closeBtn = document.getElementById('tutorial-close-btn');

    if (prevBtn) prevBtn.style.display = currentSlide > 0 ? 'inline-flex' : 'none';
    if (nextBtn) nextBtn.style.display = currentSlide < totalSlides - 1 ? 'inline-flex' : 'none';
    if (closeBtn) closeBtn.style.display = currentSlide === totalSlides - 1 ? 'inline-flex' : 'none';
}

// 전역 함수로 노출 (HTML onclick에서 사용)
window.showTutorialModal = showTutorialModal;
window.closeTutorialModal = closeTutorialModal;
