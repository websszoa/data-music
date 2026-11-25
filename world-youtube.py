from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
import time

# 현재 날짜를 문자열로 저장
current_date = datetime.now().strftime("%Y-%m-%d")

# 국가별 URL 설정
countries = {
    "global": "https://charts.youtube.com/charts/TopSongs/global/weekly",
    "argentina": "https://charts.youtube.com/charts/TopSongs/ar/weekly",
    "australia": "https://charts.youtube.com/charts/TopSongs/au/weekly",
    "austria": "https://charts.youtube.com/charts/TopSongs/at/weekly",
    "belgium": "https://charts.youtube.com/charts/TopSongs/be/weekly",
    "bolivia": "https://charts.youtube.com/charts/TopSongs/bo/weekly",
    "brazil": "https://charts.youtube.com/charts/TopSongs/br/weekly",
    "canada": "https://charts.youtube.com/charts/TopSongs/ca/weekly",
    "chile": "https://charts.youtube.com/charts/TopSongs/cl/weekly",
    "colombia": "https://charts.youtube.com/charts/TopSongs/co/weekly",
    "costa-rica": "https://charts.youtube.com/charts/TopSongs/cr/weekly",
    "czechia": "https://charts.youtube.com/charts/TopSongs/cz/weekly",
    "denmark": "https://charts.youtube.com/charts/TopSongs/dk/weekly",
    "dominican_republic": "https://charts.youtube.com/charts/TopSongs/do/weekly",
    "ecuador": "https://charts.youtube.com/charts/TopSongs/ec/weekly",
    "egypt": "https://charts.youtube.com/charts/TopSongs/eg/weekly",
    "el-salvador": "https://charts.youtube.com/charts/TopSongs/sv/weekly",
    "estonia": "https://charts.youtube.com/charts/TopSongs/ee/weekly",
    "finland": "https://charts.youtube.com/charts/TopSongs/fi/weekly",
    "france": "https://charts.youtube.com/charts/TopSongs/fr/weekly",
    "germany": "https://charts.youtube.com/charts/TopSongs/de/weekly",
    "guatemala": "https://charts.youtube.com/charts/TopSongs/gt/weekly",
    "honduras": "https://charts.youtube.com/charts/TopSongs/hn/weekly",
    "hungary": "https://charts.youtube.com/charts/TopSongs/hu/weekly",
    "iceland": "https://charts.youtube.com/charts/TopSongs/is/weekly",
    "india": "https://charts.youtube.com/charts/TopSongs/in/weekly",
    "indonesia": "https://charts.youtube.com/charts/TopSongs/id/weekly",
    "israel": "https://charts.youtube.com/charts/TopSongs/il/weekly",
    "italy": "https://charts.youtube.com/charts/TopSongs/it/weekly",
    "japan": "https://charts.youtube.com/charts/TopSongs/jp/weekly",
    "kenya": "https://charts.youtube.com/charts/TopSongs/ke/weekly",
    "luxembourg": "https://charts.youtube.com/charts/TopSongs/lu/weekly",
    "mexico": "https://charts.youtube.com/charts/TopSongs/mx/weekly",
    "netherlands": "https://charts.youtube.com/charts/TopSongs/nl/weekly",
    "new-zealand": "https://charts.youtube.com/charts/TopSongs/nz/weekly",
    "nicaragua": "https://charts.youtube.com/charts/TopSongs/ni/weekly",
    "nigeria": "https://charts.youtube.com/charts/TopSongs/ng/weekly",
    "norway": "https://charts.youtube.com/charts/TopSongs/no/weekly",
    "panama": "https://charts.youtube.com/charts/TopSongs/pa/weekly",
    "paraguay": "https://charts.youtube.com/charts/TopSongs/py/weekly",
    "peru": "https://charts.youtube.com/charts/TopSongs/pe/weekly",
    "poland": "https://charts.youtube.com/charts/TopSongs/pl/weekly",
    "portugal": "https://charts.youtube.com/charts/TopSongs/pt/weekly",
    "romania": "https://charts.youtube.com/charts/TopSongs/ro/weekly",
    "russia": "https://charts.youtube.com/charts/TopSongs/ru/weekly",
    "saudi-arabia": "https://charts.youtube.com/charts/TopSongs/sa/weekly",
    "serbia": "https://charts.youtube.com/charts/TopSongs/rs/weekly",
    "south-africa": "https://charts.youtube.com/charts/TopSongs/za/weekly",
    "south-korea": "https://charts.youtube.com/charts/TopSongs/kr/weekly",
    "spain": "https://charts.youtube.com/charts/TopSongs/es/weekly",
    "sweden": "https://charts.youtube.com/charts/TopSongs/se/weekly",
    "switzerland": "https://charts.youtube.com/charts/TopSongs/ch/weekly",
    "tanzania": "https://charts.youtube.com/charts/TopSongs/tz/weekly",
    "turkey": "https://charts.youtube.com/charts/TopSongs/tr/weekly",
    "uganda": "https://charts.youtube.com/charts/TopSongs/ug/weekly",
    "ukraine": "https://charts.youtube.com/charts/TopSongs/ua/weekly",
    "united-arab-emirates": "https://charts.youtube.com/charts/TopSongs/ae/weekly",
    "united-kingdom": "https://charts.youtube.com/charts/TopSongs/gb/weekly",
    "united-states": "https://charts.youtube.com/charts/TopSongs/us/weekly",
    "uruguay": "https://charts.youtube.com/charts/TopSongs/uy/weekly",
    "zimbabwe": "https://charts.youtube.com/charts/TopSongs/zw/weekly"
}

# 쉼표로 구분한 국가명으로 일부만 실행할 수 있다. 예: YOUTUBE_COUNTRIES=global,us
country_filter = os.environ.get("YOUTUBE_COUNTRIES")
if country_filter:
    selected = {name.strip() for name in country_filter.split(",") if name.strip()}
    unknown = selected.difference(countries)
    if unknown:
        raise ValueError(f"Unknown countries: {', '.join(sorted(unknown))}")
    countries = {name: url for name, url in countries.items() if name in selected}

# 파일 이름 설정
folder_path = "youtube"
os.makedirs(folder_path, exist_ok=True) 

# 웹드라이버 설정 및 페이지 로드
options = ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
options.add_argument("--lang=en-US")

EXPECTED_ROWS = 100
WAIT_SECONDS = 60
MAX_ATTEMPTS = 3


def wait_for_chart(browser):
    """차트 앱의 비동기 데이터 요청이 끝나고 100개 행이 그려질 때까지 대기한다."""
    WebDriverWait(browser, WAIT_SECONDS).until(
        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "ytmc-entry-row"))
        >= EXPECTED_ROWS
    )
    return browser.page_source


def load_chart(browser, country, url):
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            browser.get(url)
            html = wait_for_chart(browser)
            rows = BeautifulSoup(html, "html.parser").select("ytmc-entry-row")
            if len(rows) != EXPECTED_ROWS:
                raise RuntimeError(
                    f"expected {EXPECTED_ROWS} rows, but parsed {len(rows)}"
                )
            return rows
        except (TimeoutException, WebDriverException, RuntimeError) as error:
            last_error = error
            found = len(browser.find_elements(By.CSS_SELECTOR, "ytmc-entry-row"))
            print(
                f"  Attempt {attempt}/{MAX_ATTEMPTS} failed "
                f"({found} rows): {type(error).__name__}"
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 5)

    raise RuntimeError(
        f"Failed to load {country} chart after {MAX_ATTEMPTS} attempts"
    ) from last_error


def parse_rows(rows):
    data = []

    for row in rows:
        # 랭킹 추출
        rank_element = row.find('span', {'id': 'rank'})
        ranking = rank_element.text.strip() if rank_element else None

        # 제목 추출
        title_element = row.find('div', {'id': 'entity-title'})
        title = title_element.text.strip() if title_element else None

        # 가수 추출
        artist_elements = row.select("div#artist-names span.artistName")
        artist = ", ".join(
            element.get_text(" ", strip=True) for element in artist_elements
        ) or None

        # 이미지 URL 추출
        img_element = row.select_one("div.thumbnail-container > img#thumbnail")
        image = img_element['src'] if img_element else None

        # 지난주 랭킹 추출
        prev_element = row.select_one("div.data-table-container > div:nth-child(4)")
        prev = prev_element.text.strip() if prev_element else None

        # 지속 기간 추출
        streak_element = row.select_one("div.data-table-container > div:nth-child(5)")
        streak = streak_element.text.strip() if streak_element else None

        # 주간 조회수 추출
        streams_element = row.select_one("div.data-table-container > div:nth-child(6)")
        streams = streams_element.text.strip() if streams_element else None

        # YouTube ID 추출
        youtube_element = row.select_one("div.thumbnail-container > img#thumbnail")

        if youtube_element and "endpoint" in youtube_element.attrs:
            # endpoint 속성에서 URL을 추출
            endpoint = youtube_element["endpoint"]
            # watch?v= 이후의 값을 추출
            youtubeID = endpoint.split("watch?v=")[-1].split('"')[0] if "watch?v=" in endpoint else None
        else:
            youtubeID = None

        # 데이터 저장
        data.append({
            "ranking": ranking,
            "title": title,
            "artist": artist,
            "image": image,
            "prev": prev,
            "streak": streak,
            "streams": streams,
            "youtubeID": youtubeID,
        })

    if len(data) != EXPECTED_ROWS:
        raise RuntimeError(f"Refusing to save incomplete chart ({len(data)} rows)")
    if any(not item["ranking"] or not item["title"] for item in data):
        raise RuntimeError("Refusing to save chart with missing ranks or titles")
    return data


browser = webdriver.Chrome(options=options)
failures = []

try:
    # 나라별 데이터 수집
    for country, url in countries.items():
        print(f"Processing {country}...")

        try:
            rows = load_chart(browser, country, url)
            data = parse_rows(rows)
        except Exception as error:
            failures.append(country)
            print(f"ERROR: {country}: {error}")
            # 전 국가가 같은 차트 앱을 사용하므로 구조/인증 실패 시 반복 실행하지 않는다.
            break

        # 국가별 폴더 생성
        country_folder = os.path.join(folder_path, country)
        os.makedirs(country_folder, exist_ok=True)

        # 국가별 JSON 파일 경로 설정
        json_file_name = os.path.join(country_folder, f"{country}Top100_{current_date}.json")

        # 검증을 통과한 데이터만 저장한다. 실패 시 기존 파일을 빈 배열로 덮지 않는다.
        with open(json_file_name, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

        print(f"Data for {country} saved in {json_file_name}")
finally:
    browser.quit()

if failures:
    raise RuntimeError(
        f"Collection failed for {len(failures)} countries: {', '.join(failures)}"
    )
