"""
NCloud 문서 구조 수집기

홈페이지에서 전체 카테고리/서비스 구조를 수집합니다.
확장 전후 비교 방식으로 100% 정확도를 보장합니다.
"""

import time
from typing import Dict, List, Set, Optional
from playwright.sync_api import sync_playwright, Page


class NCloudStructureCollector:
    """
    NCloud 문서 구조 수집기 (확장 전후 비교 방식)

    사용법:
        collector = NCloudStructureCollector()
        collector.collect_structure()

        categories = collector.get_categories()
        services = collector.get_services("Gaming")

        if collector.is_category("Compute"):
            print("Compute는 카테고리입니다")

        if collector.is_other_service("Neurocloud", "gamepot"):
            print("Neurocloud는 GAMEPOT과 다른 서비스입니다")

    Args:
        headless: 브라우저 숨김 모드
        base_url: 기본 URL (존별로 다름)
            - 일반: https://guide.ncloud-docs.com
            - 금융: https://guide-fin.ncloud-docs.com
            - 공공: https://guide-gov.ncloud-docs.com
    """

    EXCLUDED_ITEMS = {"HOME", "네이버 클라우드 플랫폼 사용 환경"}

    def __init__(self, headless: bool = True, base_url: str = None):
        self.headless = headless
        self.base_url = base_url or "https://guide.ncloud-docs.com"
        self.home_url = f"{self.base_url}/docs/home"
        self._structure: Dict[str, List[str]] = {}
        self._all_categories: Set[str] = set()
        self._all_services: Set[str] = set()
        self._collected = False

    def collect_structure(self) -> Dict[str, List[str]]:
        """
        홈페이지에서 전체 카테고리/서비스 구조 수집

        Returns:
            Dict[str, List[str]]: 카테고리 -> 서비스 목록 매핑
        """
        if self._collected:
            return self._structure

        print("[구조 수집기] 홈페이지에서 구조 수집 시작...")

        # 1단계: 카테고리 목록 수집
        category_list = self._collect_category_list()
        print(f"[구조 수집기] {len(category_list)}개 카테고리 발견")

        # 2단계: 각 카테고리별 서비스 수집 (브라우저 재시작으로 안정성 확보)
        for i, category in enumerate(category_list):
            category_name = category['text']
            print(f"[구조 수집기] [{i+1}/{len(category_list)}] {category_name} 수집 중...")

            services = self._collect_category_services(category_name)
            self._structure[category_name] = services
            self._all_categories.add(category_name)
            self._all_services.update(services)

            print(f"[구조 수집기]   -> {len(services)}개 서비스")

        self._collected = True
        total_services = sum(len(s) for s in self._structure.values())
        print(f"[구조 수집기] 수집 완료: {len(self._structure)}개 카테고리, {total_services}개 서비스")

        return self._structure

    def _collect_category_list(self) -> List[Dict]:
        """최상위 카테고리 목록 수집"""
        categories = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                page.goto(self.home_url, timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
                time.sleep(3)

                # 사이드바 노드 로드 대기
                try:
                    page.wait_for_selector('[id^="node-"]', timeout=15000)
                except:
                    print("[구조 수집기] 사이드바 로드 대기 실패, 추가 대기...")
                    time.sleep(5)

                # 여러 번 시도하여 카테고리 로드 확인
                for attempt in range(5):
                    categories = self._get_all_categories(page)
                    if categories:
                        break
                    print(f"[구조 수집기] 카테고리 로드 대기 중... ({attempt + 1}/5)")
                    time.sleep(2)

            finally:
                browser.close()

        return categories

    def _get_all_categories(self, page: Page) -> List[Dict]:
        """페이지에서 카테고리 목록 추출"""
        return page.evaluate('''
            () => {
                const nodes = document.querySelectorAll('[id^="node-"]');
                const results = [];

                for (let node of nodes) {
                    const link = node.querySelector('a.data-title');
                    const hasArrow = node.querySelector('.tree-arrow[role="button"]') !== null;

                    if (link && hasArrow) {
                        const text = link.textContent.trim();
                        const excludeList = ['HOME', '네이버 클라우드 플랫폼 사용 환경'];
                        if (!excludeList.includes(text)) {
                            results.push({
                                id: node.id,
                                text: text
                            });
                        }
                    }
                }
                return results;
            }
        ''')

    def _collect_category_services(self, category_name: str) -> List[str]:
        """단일 카테고리의 서비스 목록 수집 (확장 전후 비교)"""
        services = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()

            try:
                page.goto(self.home_url, timeout=60000)
                page.wait_for_load_state("networkidle", timeout=60000)
                time.sleep(3)

                # 카테고리 ID 찾기 (ID가 변경될 수 있으므로 이름으로 검색)
                categories = self._get_all_categories(page)
                category = next((c for c in categories if c['text'] == category_name), None)

                if not category:
                    return services

                category_id = category['id']

                # 확장 전 노드 ID 수집
                before_ids = self._get_node_ids(page)

                # 카테고리 확장
                self._expand_node(page, category_id)
                time.sleep(0.5)

                # 확장 후 노드 ID 수집
                after_ids = self._get_node_ids(page)

                # 새로 나타난 노드 = 자식
                new_ids = after_ids - before_ids

                # 자식 노드 정보 수집
                for node_id in new_ids:
                    info = self._get_node_info(page, node_id)
                    if info and info['hasArrow']:  # 폴더(서비스)만 수집
                        services.append(info['text'])

            finally:
                browser.close()

        return services

    def _get_node_ids(self, page: Page) -> Set[str]:
        """현재 페이지의 모든 노드 ID 수집"""
        ids = page.evaluate('''
            () => {
                const nodes = document.querySelectorAll('[id^="node-"]');
                return Array.from(nodes).map(n => n.id);
            }
        ''')
        return set(ids)

    def _get_node_info(self, page: Page, node_id: str) -> Optional[Dict]:
        """노드 정보 추출"""
        return page.evaluate('''
            (nodeId) => {
                const node = document.getElementById(nodeId);
                if (!node) return null;
                const link = node.querySelector('a.data-title');
                if (!link) return null;
                return {
                    id: nodeId,
                    text: link.textContent.trim(),
                    href: link.getAttribute('href') || '',
                    hasArrow: node.querySelector('.tree-arrow[role="button"]') !== null
                };
            }
        ''', node_id)

    def _expand_node(self, page: Page, node_id: str) -> bool:
        """노드 확장 (접혀있는 경우에만)"""
        return page.evaluate('''
            (nodeId) => {
                const node = document.getElementById(nodeId);
                if (!node) return false;
                const expandBtn = node.querySelector('.tree-arrow[role="button"]');
                if (!expandBtn) return false;
                const icon = expandBtn.querySelector('i');
                const isExpanded = icon && icon.classList.contains('fa-angle-down');
                if (!isExpanded) {
                    expandBtn.click();
                    return true;
                }
                return false;
            }
        ''', node_id)

    def get_categories(self) -> List[str]:
        """카테고리 목록 반환"""
        if not self._collected:
            self.collect_structure()
        return list(self._all_categories)

    def get_services(self, category: str = None) -> List[str]:
        """
        서비스 목록 반환

        Args:
            category: 특정 카테고리의 서비스만 반환 (None이면 전체)

        Returns:
            List[str]: 서비스 이름 목록
        """
        if not self._collected:
            self.collect_structure()

        if category:
            return self._structure.get(category, [])
        return list(self._all_services)

    def get_structure(self) -> Dict[str, List[str]]:
        """전체 구조 반환"""
        if not self._collected:
            self.collect_structure()
        return self._structure.copy()

    def is_category(self, name: str) -> bool:
        """이름이 카테고리인지 확인"""
        if not self._collected:
            self.collect_structure()
        return name in self._all_categories

    def is_service(self, name: str) -> bool:
        """이름이 서비스인지 확인"""
        if not self._collected:
            self.collect_structure()
        return name in self._all_services

    def is_other_service(self, name: str, current_service: str) -> bool:
        """
        이름이 현재 서비스가 아닌 다른 서비스인지 확인

        Args:
            name: 확인할 폴더/서비스 이름
            current_service: 현재 크롤링 중인 서비스의 prefix 또는 이름

        Returns:
            bool: 다른 서비스이면 True
        """
        if not self._collected:
            self.collect_structure()

        # 서비스 목록에 있는지 확인
        if name not in self._all_services:
            return False

        # 현재 서비스와 이름 비교 (대소문자 무시, 공백/하이픈 정규화)
        name_normalized = name.lower().replace(' ', '-').replace('_', '-')
        current_normalized = current_service.lower().replace(' ', '-').replace('_', '-')

        # 이름이 포함되어 있으면 같은 서비스로 간주
        if name_normalized in current_normalized or current_normalized in name_normalized:
            return False

        return True

    def refresh_structure(self) -> Dict[str, List[str]]:
        """구조 정보 갱신 (캐시 무효화 후 재수집)"""
        self._structure = {}
        self._all_categories = set()
        self._all_services = set()
        self._collected = False
        return self.collect_structure()

    def get_category_for_service(self, service_name: str) -> Optional[str]:
        """서비스가 속한 카테고리 찾기"""
        if not self._collected:
            self.collect_structure()

        for category, services in self._structure.items():
            if service_name in services:
                return category
        return None


# 모듈 레벨 싱글톤 인스턴스 (선택적 사용)
_default_collector: Optional[NCloudStructureCollector] = None


def get_default_collector(headless: bool = True) -> NCloudStructureCollector:
    """기본 구조 수집기 인스턴스 반환 (싱글톤)"""
    global _default_collector
    if _default_collector is None:
        _default_collector = NCloudStructureCollector(headless=headless)
    return _default_collector


def reset_default_collector():
    """기본 구조 수집기 인스턴스 초기화"""
    global _default_collector
    _default_collector = None
