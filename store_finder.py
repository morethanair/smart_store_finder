from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc
import random
import time
import urllib.parse
import re
import pandas as pd
from urllib.parse import quote

# 더 현대적이고 다양한 User-Agent 리스트
USER_AGENTS = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
]

# 전역 변수 선언
driver = None

def setup_driver():
    """웹드라이버 설정"""
    global driver
    
    try:
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        
        # headless 모드 설정
        # options.add_argument('--headless=new')
        
        driver = uc.Chrome(
            options=options,
            driver_executable_path=None,  # 자동으로 적절한 드라이버를 찾도록 설정
            browser_executable_path=None,  # 자동으로 브라우저를 찾도록 설정
            suppress_welcome=True  # 시작 페이지 비활성화
        )
        
        # 창 크기 설정
        driver.maximize_window()
        
        return driver
    except Exception as e:
        print(f"ChromeDriver 초기화 중 오류 발생: {str(e)}")
        if driver:
            driver.quit()
        raise

def determine_store_type(url, store_name_en):
    """URL과 영문 스토어명을 기반으로 스토어 타입을 판단"""
    url_lower = url.lower()
    store_name_lower = store_name_en.lower()
    
    if "smartstore.naver.com" in url_lower:
        return "스마트스토어"
    elif "shopping.naver.com/window-products/" in url_lower:
        return "패션몰"
    elif store_name_lower and store_name_lower in url_lower:
        return "자사몰"
    else:
        return "기타"

def get_final_urls_from_seller_links(driver, seller_links):
    """판매처 링크에서 최종 URL 추출"""
    print("\n[7/7] 판매처 최종 URL 추출 중...")
    
    final_urls = []
    
    for link in seller_links:
        try:
            print(f"\n판매 링크 발견: {link}")
            
            # cr.shopping.naver.com 링크 처리
            if 'cr.shopping.naver.com' in link:
                try:
                    driver.get(link)
                    time.sleep(2)  # 리다이렉션 대기
                    final_url = driver.current_url
                    if final_url and final_url != link:
                        final_urls.append({
                            'type': '일반몰',  # 기본값으로 일반몰 설정
                            'final_url': final_url
                        })
                        print(f"→ 최종 URL: {final_url}")
                except Exception as e:
                    print(f"! 리다이렉션 처리 중 오류: {str(e)}")
                    continue
            else:
                # 일반 링크는 그대로 사용
                final_urls.append({
                    'type': '일반몰',  # 기본값으로 일반몰 설정
                    'final_url': link
                })
                print(f"→ 일반 URL: {link}")
        
        except Exception as e:
            print(f"! URL 처리 중 오류: {str(e)}")
            continue
    
    return final_urls

def get_seller_links_from_product_page(driver, product_url):
    """상품 페이지에서 판매처 링크 리스트 추출"""
    try:
        print(f"\n[6/7] 상품 페이지 접속: {product_url}")
        driver.get(product_url)
        time.sleep(3)  # 페이지 로딩 대기
        
        # 판매처 영역 찾기
        buy_areas = driver.find_elements(By.CSS_SELECTOR, ".productByMall_buy_area__B1VZO")
        seller_links = []

        # 각 판매처 영역에서 링크 찾기
        for buy_area in buy_areas:
            links = buy_area.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute('href')
                if href:
                    seller_links.append(href)
                    print(f"판매 링크 발견: {href}")

        return seller_links
    
    except Exception as e:
        print(f"    ! 상품 페이지 접속 중 오류: {str(e)}")
        return []

def get_store_links(driver, store_name_kr, store_name_en):
    """스토어 링크 수집"""
    try:
        print(f"\n'{store_name_kr}' 검색을 시작합니다...")
        
        # store_name_en 정제
        clean_store_name = clean_domain_name(store_name_en)
        print(f"정제된 스토어 이름: {clean_store_name}")
        
        # 검색 URL 설정
        search_url = f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(store_name_kr)}"
        
        # 페이지 로딩
        driver.get(search_url)
        time.sleep(3)  # 페이지 로딩 대기
        
        # 스크롤 다운
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        # 상품 컨테이너 찾기
        print("\n[5/7] 상품 컨테이너 검색 중...")
        try:
            product_containers = driver.find_elements(By.CSS_SELECTOR, 'div.basicList_list_basis__uNBZx')
            if not product_containers:
                print("! 상품 컨테이너를 찾을 수 없습니다")
                return []
            
            # 모든 상품 아이템 찾기
            all_product_items = []
            for container in product_containers:
                items = container.find_elements(By.CSS_SELECTOR, 'div.product_item__MDtDF')
                all_product_items.extend(items)
            
            print(f"→ 총 {len(all_product_items)}개의 상품 아이템 발견")
            
            # 각 상품 분석
            max_li_count = 0
            selected_product_url = None
            selected_product_title = None
            own_mall_url = None  # 자사몰 URL 저장 변수
            
            for idx, product_item in enumerate(all_product_items, 1):
                try:
                    print(f"\n상품 {idx} 분석:")
                    
                    # 상품 제목 찾기
                    product_title = "제목 없음"
                    try:
                        title_element = product_item.find_element(By.CSS_SELECTOR, 'div.product_title__Mmw2K a')
                        product_title = title_element.get_attribute('title')
                        if not product_title:
                            product_title = title_element.text.strip() or "제목 없음"
                    except Exception as e:
                        print(f"! 상품 제목을 찾을 수 없음: {str(e)}")
                        continue
                    
                    # 판매처 목록 찾기
                    try:
                        mall_area = product_item.find_element(By.CSS_SELECTOR, 'div.product_mall_area___f3wo')
                        
                        # 자사몰 찾기
                        has_own_mall = False
                        try:
                            mall_titles = mall_area.find_elements(By.CSS_SELECTOR, 'div.product_mall_title__Xer1m')
                            for mall_title in mall_titles:
                                mall_link = mall_title.find_element(By.TAG_NAME, 'a')
                                mall_url = mall_link.get_attribute('href')
                                if mall_url:
                                    clean_mall_url = clean_domain_name(mall_url)
                                    if clean_store_name and clean_store_name in clean_mall_url:
                                        print(f"→ 자사몰 발견: {mall_url}")
                                        print(f"  정제된 URL: {clean_mall_url}")
                                        has_own_mall = True
                                        own_mall_url = mall_url  # 자사몰 URL 저장
                                        break
                        except Exception as e:
                            print(f"! 자사몰 확인 중 오류: {str(e)}")
                        
                        # 판매처 목록 처리
                        li_elements = mall_area.find_elements(By.TAG_NAME, 'li')
                        li_count = len(li_elements)
                        print(f"→ <li> 요소 개수: {li_count}")
                        
                        # 판매처가 가장 많은 상품 선택
                        if li_count > max_li_count:
                            max_li_count = li_count
                            selected_product_url = product_item.find_element(By.CSS_SELECTOR, 'div.product_info_area__xxCTi a').get_attribute('href')
                            selected_product_title = product_title
                            print(f"→ 현재 최대 <li> 개수 업데이트: {max_li_count}")
                        print(f"(자사몰: {'있음' if has_own_mall else '없음'})")
                    
                    except Exception as e:
                        print(f"! 판매처 목록을 찾을 수 없음: {str(e)}")
                        continue
                    
                except Exception as e:
                    print(f"! 상품 {idx} 처리 중 오류: {str(e)}")
                    continue
            
            if selected_product_url:
                print(f"\n[6/7] 선택된 상품: {selected_product_title}")
                print(f"→ URL: {selected_product_url}")
                
                # 선택된 상품 페이지에서 판매처 링크 추출
                seller_links = get_seller_links_from_product_page(driver, selected_product_url)
                final_urls = []
                if seller_links:
                    # 판매처 링크에서 최종 URL 추출
                    final_urls = get_final_urls_from_seller_links(driver, seller_links)
                    
                if own_mall_url:
                    final_urls.append({
                        'type': '자사몰',
                        'final_url': own_mall_url
                    })

                if final_urls:
                    return final_urls
            
            return []
            
        except Exception as e:
            print(f"! 상품 컨테이너 처리 중 오류: {str(e)}")
            return []
        
    except Exception as e:
        print(f"! 검색 중 오류 발생: {str(e)}")
        return []

def clean_url(url):
    """URL을 정규화하여 비교 가능한 형태로 변환"""
    if pd.isna(url) or not isinstance(url, str):
        return ""
    # http://, https://, www. 제거
    url = re.sub(r'^(https?://)?(www\.)?', '', url.lower())
    # 마지막 슬래시 제거
    url = url.rstrip('/')
    return url

def clean_domain_name(url):
    """URL이나 도메인에서 프로토콜, 특수문자, TLD 등을 제거"""
    # 소문자로 변환
    url = url.lower()
    
    # 프로토콜 제거
    url = re.sub(r'https?://', '', url)
    
    # www 제거
    url = re.sub(r'www\.', '', url)
    
    # TLD 제거 (.com, .co.kr 등)
    url = re.sub(r'\.(com|co\.kr|kr|net|org|shop).*$', '', url)
    
    # 특수문자 제거
    url = re.sub(r'[^a-z0-9]', '', url)
    
    return url

def process_store_csv(csv_path):
    """CSV 파일에서 스토어 정보를 읽어옴"""
    try:
        # CSV 파일 읽기
        df = pd.read_csv(csv_path)
        
        # 필요한 컬럼 확인
        required_columns = ['shop_id', 'name', 'ranking', 'url']
        if not all(col in df.columns for col in required_columns):
            print(f"CSV 파일에 필요한 컬럼이 없습니다. 필요한 컬럼: {required_columns}")
            return None
        
        # NaN 값을 빈 문자열로 변환
        df['url'] = df['url'].fillna('')
        
        # URL 정규화
        df['clean_url'] = df['url'].apply(clean_url)
        
        # 결과를 shop_id 순으로 정렬
        df = df.sort_values('shop_id')
        
        print(f"\n총 {len(df)}개의 스토어를 분석합니다.")
        return df
    except Exception as e:
        print(f"CSV 파일 처리 중 오류 발생: {str(e)}")
        return None

def save_results_to_csv(results, output_path):
    """분석 결과를 CSV 파일로 저장"""
    try:
        # 결과를 DataFrame으로 변환
        df = pd.DataFrame(results)
        
        # 컬럼 순서 지정
        columns = [
            'shop_id',
            'name',
            'ranking',
            'smart_store',
            'own_mall',
            'fashion_mall'
        ]
        
        # 컬럼 순서대로 저장
        df = df[columns]
        
        # CSV 파일로 저장
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n결과가 {output_path}에 저장되었습니다.")
    except Exception as e:
        print(f"결과 저장 중 오류 발생: {str(e)}")

def analyze_store(driver, shop_id, name, ranking, url):
    """주어진 스토어의 유형을 분석"""
    try:
        # NaN 값 처리
        shop_id = int(shop_id) if pd.notna(shop_id) else 0
        name = str(name) if pd.notna(name) else "Unknown"
        ranking = int(ranking) if pd.notna(ranking) else 0
        url = str(url) if pd.notna(url) else ""

        print(f"\n[스토어 분석] {name} (ID: {shop_id}, Ranking: {ranking})")
        
        # 스토어 링크 수집
        final_store_info = get_store_links(driver, name, url)  # 영문명이 없으므로 동일한 이름 사용
        if not final_store_info:
            return {
                'shop_id': shop_id,
                'name': name,
                'ranking': ranking,
                'smart_store': '',
                'zigzag_mall': '',
                'own_mall': '',
                'fashion_mall': ''
            }
        
        # 스토어 유형별 URL 저장
        smart_store_url = ''
        own_mall_url = ''
        fashion_mall_url = ''
        zigzag_mall_url = ''
        
        # 각 URL의 타입에 따라 저장
        for store_info in final_store_info:
            store_type = store_info['type']
            final_url = store_info['final_url']
            if store_type != "자사몰":
                store_type = determine_store_type(final_url, url)
            if store_type == "스마트스토어" and not smart_store_url:
                smart_store_url = final_url
                print(f"스마트스토어 발견: {final_url}")
            elif store_type == "자사몰" and not own_mall_url:
                own_mall_url = final_url
                print(f"자사몰 발견: {final_url}")
            elif store_type == "지그재그":
                zigzag_mall_url = final_url
                print(f"지그재그 발견: {final_url}")
            elif store_type == "패션몰" and not fashion_mall_url:
                fashion_mall_url = final_url
                print(f"패션몰 발견: {final_url}")
        
        return {
            'shop_id': shop_id,
            'name': name,
            'ranking': ranking,
            'smart_store': smart_store_url,
            'own_mall': own_mall_url,
            'zigzag_mall': zigzag_mall_url,
            'fashion_mall': fashion_mall_url
        }
        
    except Exception as e:
        print(f"스토어 분석 중 오류 발생: {str(e)}")
        return None

def search_products(driver, store_name):
    """네이버 쇼핑에서 스토어 이름으로 검색하여 상품 URL 수집"""
    try:
        # 네이버 쇼핑 검색 URL
        search_url = f"https://search.shopping.naver.com/search/all?query={quote(store_name)}&cat_id=&frm=NVSHATC"
        
        # 검색 페이지로 이동
        driver.get(search_url)
        time.sleep(2)  # 페이지 로딩 대기
        
        # 상품 링크 수집
        product_links = []
        product_elements = driver.find_elements(By.CSS_SELECTOR, "a.product_link__TrAac")
        
        for element in product_elements[:5]:  # 상위 5개 상품만 수집
            href = element.get_attribute('href')
            if href:
                product_links.append(href)
        
        return product_links
    except Exception as e:
        print(f"상품 검색 중 오류 발생: {str(e)}")
        return []

def get_seller_links_from_product_page(driver, product_url):
    """상품 페이지에서 판매처 링크 수집"""
    try:
        driver.get(product_url)
        time.sleep(5)  # 페이지 로딩 대기
        
        seller_links = []
        
        # 판매처 영역 찾기
        buy_areas = driver.find_elements(By.CSS_SELECTOR, ".productByMall_buy_area__B1VZO")

        # 각 판매처 영역에서 링크 찾기
        for buy_area in buy_areas:
            links = buy_area.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute('href')
                if href:
                    seller_links.append(href)
                    print(f"판매 링크 발견: {href}")
        
        return seller_links
    except Exception as e:
        print(f"판매처 링크 수집 중 오류 발생: {str(e)}")
        return []

def determine_store_type(final_url, clean_store_url):
    """URL을 기반으로 스토어 유형 판단"""
    final_url = clean_url(final_url)
    clean_store_url = clean_url(clean_store_url)
    if 'smartstore.naver.com' in final_url:
        return "스마트스토어"
    elif 'zigzag.kr' in final_url:
        return "지그재그"
    elif clean_store_url and clean_store_url in final_url:
        return "자사몰"
    elif any(keyword in final_url for keyword in ['fashion', 'clothing', 'apparel', 'style']):
        return "패션몰"
    
    return "기타"

def main():
    """메인 함수"""
    try:
        # 입력 파일 경로 프롬프트
        input_path = input("분석할 CSV 파일 경로를 입력하세요: ").strip()
        
        # 출력 파일 경로 고정
        output_path = '/Users/khan.nam/Downloads/result.csv'
        
        # CSV 파일 처리
        df = process_store_csv(input_path)
        if df is None:
            return
        
        # Selenium 웹드라이버 초기화 (한 번만 실행)
        driver = setup_driver()
        if not driver:
            return
        
        try:
            # 각 스토어 분석
            results = []
            total_stores = len(df)
            
            for idx, row in df.iterrows():
                print(f"\n[{idx + 1}/{total_stores}] 스토어 분석 중...")
                result = analyze_store(
                    driver=driver,  # 동일한 드라이버 인스턴스 사용
                    shop_id=row['shop_id'],
                    name=row['name'],
                    ranking=row['ranking'],
                    url=row['url']
                )
                if result:
                    results.append(result)
                    print(f"분석 완료: {row['name']}")
                else:
                    print(f"분석 실패: {row['name']}")
            
            # 결과 저장
            if results:
                save_results_to_csv(results, output_path)
                print(f"\n총 {len(results)}/{total_stores}개의 스토어 분석 완료")
            else:
                print("\n분석된 스토어가 없습니다.")
        
        finally:
            # 웹드라이버 종료
            driver.quit()
    
    except Exception as e:
        print(f"\n프로그램 실행 중 오류 발생: {str(e)}")
        if 'driver' in locals():
            driver.quit()

if __name__ == '__main__':
    main()