"""나라별 유튜브 뮤직 차트(주간 Top 100 뮤직비디오) 수집기.

2026-11 부터 charts.youtube.com 페이지가 차트 표를 정적 HTML 로 내려주지 않고
reCAPTCHA 토큰을 요구하는 내부 API 로 바꾸면서(headless 브라우저로 열어도
`ytmc-entry-row` 가 0개, `INNERTUBE_API_KEY` 도 빈 값) Selenium 파싱이 멈췄다.
같은 차트를 공식 내부 API 로 감싼 ytmusicapi 의 `get_charts` / `get_playlist` 로
대체한다. 우회 크롤링(프록시, 캡차 통과)은 하지 않는다.

- 차트 목록: `get_charts(country=<ISO 3166-1 alpha-2>)` 의 `videos` 항목
  (전 세계 차트는 `ZZ`)
- 순위: "Top 100 Music Videos <국가>" 플레이리스트의 트랙 순서 (1번째 = 1위)

저장 경로와 JSON 키는 기존 수집기와 같다: youtube/{slug}/{slug}Top100_{YYYY-MM-DD}.json
주간 조회수(streams) · 지난주 순위(prev) · 연속 주간(streak)은 이 경로에서 알 수 없어
null 로 둔다. 100곡을 채우지 못한 나라는 기존 파일을 덮어쓰지 않고 실패로 기록한다.
"""
from datetime import datetime
import json
import os
import re
import sys
import time

from ytmusicapi import YTMusic

# 현재 날짜를 문자열로 저장
current_date = datetime.now().strftime("%Y-%m-%d")

# 슬러그 → ISO 3166-1 alpha-2 (전 세계 차트는 ZZ). 폴더/파일 이름은 슬러그를 그대로 쓴다.
COUNTRIES = {
    "global": "ZZ",
    "argentina": "AR",
    "australia": "AU",
    "austria": "AT",
    "belgium": "BE",
    "bolivia": "BO",
    "brazil": "BR",
    "canada": "CA",
    "chile": "CL",
    "colombia": "CO",
    "costa-rica": "CR",
    "czechia": "CZ",
    "denmark": "DK",
    "dominican_republic": "DO",
    "ecuador": "EC",
    "egypt": "EG",
    "el-salvador": "SV",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "guatemala": "GT",
    "honduras": "HN",
    "hungary": "HU",
    "iceland": "IS",
    "india": "IN",
    "indonesia": "ID",
    "israel": "IL",
    "italy": "IT",
    "japan": "JP",
    "kenya": "KE",
    "luxembourg": "LU",
    "mexico": "MX",
    "netherlands": "NL",
    "new-zealand": "NZ",
    "nicaragua": "NI",
    "nigeria": "NG",
    "norway": "NO",
    "panama": "PA",
    "paraguay": "PY",
    "peru": "PE",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "russia": "RU",
    "saudi-arabia": "SA",
    "serbia": "RS",
    "south-africa": "ZA",
    "south-korea": "KR",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "tanzania": "TZ",
    "turkey": "TR",
    "uganda": "UG",
    "ukraine": "UA",
    "united-arab-emirates": "AE",
    "united-kingdom": "GB",
    "united-states": "US",
    "uruguay": "UY",
    "zimbabwe": "ZW",
}

# 쉼표로 구분한 국가명으로 일부만 실행할 수 있다. 예: YOUTUBE_COUNTRIES=global,south-korea
country_filter = os.environ.get("YOUTUBE_COUNTRIES")
if country_filter:
    selected = {name.strip() for name in country_filter.split(",") if name.strip()}
    unknown = selected.difference(COUNTRIES)
    if unknown:
        raise ValueError(f"Unknown countries: {', '.join(sorted(unknown))}")
    COUNTRIES = {name: code for name, code in COUNTRIES.items() if name in selected}

folder_path = "youtube"
os.makedirs(folder_path, exist_ok=True)

EXPECTED_TRACKS = 100
# 유튜브 쪽에서 영상이 내려가면 플레이리스트가 99곡처럼 줄어들기도 한다(예: 일본, 케냐).
# 이 경우 0곡으로 만드는 것보다 원본에 있는 만큼 저장하는 편이 낫지만, 응답이 잘린
# 경우와 구분하려고 하한을 둔다. 이보다 적으면 실패로 처리하고 기존 파일을 건드리지 않는다.
MIN_TRACKS = 90
MAX_ATTEMPTS = 3
REQUEST_DELAY = 1.5  # 국가 사이 지연(초)

# 재생 불가 영상은 ytmusicapi 가 videoId 를 비우지만 썸네일 주소에 영상 ID 가 남는다.
THUMBNAIL_VIDEO_ID = re.compile(r"/vi/([A-Za-z0-9_-]{11})/")


def chart_playlist_id(ym, country_code):
    """차트 목록에서 'Top 100 Music Videos' 플레이리스트 ID 를 찾는다."""
    charts = ym.get_charts(country=country_code)
    for chart in charts.get("videos") or []:
        title = chart.get("title") or ""
        if "Top 100 Music Videos" in title and chart.get("playlistId"):
            return chart["playlistId"]
    titles = [chart.get("title") for chart in charts.get("videos") or []]
    raise RuntimeError(
        "no 'Top 100 Music Videos' chart in response "
        f"(got: {', '.join(str(t) for t in titles) or 'nothing'})"
    )


def fetch_tracks(ym, playlist_id):
    """플레이리스트 트랙을 순위 순서대로 가져온다."""
    playlist = ym.get_playlist(playlist_id, limit=EXPECTED_TRACKS)
    tracks = (playlist.get("tracks") or [])[:EXPECTED_TRACKS]
    declared = playlist.get("trackCount")
    if declared is not None and declared <= EXPECTED_TRACKS and len(tracks) < declared:
        # 플레이리스트에 있다는 곡을 파서가 덜 가져온 경우: 응답 문제로 보고 재시도한다.
        raise RuntimeError(
            f"playlist says {declared} tracks, but parsed {len(tracks)}"
        )
    if len(tracks) < MIN_TRACKS:
        raise RuntimeError(
            f"expected {EXPECTED_TRACKS} tracks, but got {len(tracks)} "
            f"(below minimum {MIN_TRACKS})"
        )
    return tracks


def resolve_video_id(track):
    """영상 ID 를 얻는다. 재생 불가 곡은 썸네일 주소에서 되살린다."""
    if track.get("videoId"):
        return track["videoId"]
    for thumbnail in track.get("thumbnails") or []:
        match = THUMBNAIL_VIDEO_ID.search(thumbnail.get("url") or "")
        if match:
            return match.group(1)
    return None


def build_rows(tracks):
    """ytmusicapi 트랙 목록을 기존 JSON 스키마로 바꾼다."""
    rows = []
    for index, track in enumerate(tracks, start=1):
        title = (track.get("title") or "").strip() or None
        video_id = resolve_video_id(track)

        artists = [
            artist.get("name", "").strip()
            for artist in track.get("artists") or []
            if artist.get("name")
        ]
        artist = ", ".join(artists) if artists else None

        # i.ytimg.com 의 고정 썸네일 주소. API 가 주는 서명(sqp=) URL 은 만료될 수 있어
        # videoId 로 항상 접근 가능한 주소를 만든다.
        image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None

        if title is None or video_id is None:
            raise RuntimeError(f"track #{index} has no title or videoId")

        rows.append(
            {
                "ranking": str(index),
                "title": title,
                "artist": artist,
                "image": image,
                # 이 경로에서는 알 수 없는 값들
                "prev": None,
                "streak": None,
                "streams": None,
                "youtubeID": video_id,
            }
        )

    if len(rows) < MIN_TRACKS:
        raise RuntimeError(f"Refusing to save incomplete chart ({len(rows)} rows)")
    return rows


def collect_country(ym, slug, country_code, verbose=True):
    """재시도(지수 백오프)를 포함한 국가 한 곳 수집."""
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            playlist_id = chart_playlist_id(ym, country_code)
            tracks = fetch_tracks(ym, playlist_id)
            return build_rows(tracks)
        except Exception as error:  # 네트워크 오류와 응답 구조 변경을 함께 다룬다
            last_error = error
            if verbose:
                print(
                    f"  attempt {attempt}/{MAX_ATTEMPTS} failed: "
                    f"{type(error).__name__}: {error}"
                )
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f"Failed to collect {slug} ({country_code}) after {MAX_ATTEMPTS} attempts: "
        f"{type(last_error).__name__}: {last_error}"
    )


def main():
    ym = YTMusic()
    failures = {}
    saved = []
    partial = {}

    items = list(COUNTRIES.items())
    for index, (slug, country_code) in enumerate(items):
        print(f"Processing {slug} ({country_code})...")

        try:
            rows = collect_country(ym, slug, country_code)
        except Exception as error:
            failures[slug] = str(error)
            print(f"ERROR: {slug}: {error}")
            time.sleep(REQUEST_DELAY)
            continue

        country_folder = os.path.join(folder_path, slug)
        os.makedirs(country_folder, exist_ok=True)
        json_file_name = os.path.join(
            country_folder, f"{slug}Top100_{current_date}.json"
        )

        # 검증을 통과한 데이터만 저장한다. 실패 시 기존 파일을 빈 배열로 덮지 않는다.
        with open(json_file_name, "w", encoding="utf-8") as json_file:
            json.dump(rows, json_file, ensure_ascii=False, indent=4)

        saved.append((slug, len(rows)))
        print(f"Data for {slug} saved in {json_file_name} ({len(rows)} tracks)")
        if len(rows) < EXPECTED_TRACKS:
            partial[slug] = len(rows)
            print(f"NOTE: {slug} has {len(rows)} tracks (source playlist is short)")

        # API 과호출을 피하려고 국가 사이에 짧게 쉰다.
        if index < len(items) - 1:
            time.sleep(REQUEST_DELAY)

    print(
        f"\nSummary: {len(saved)} saved, {len(failures)} failed "
        f"of {len(COUNTRIES)} countries"
    )
    for slug, count in saved:
        print(f"  OK   {slug}: {count}")
    for slug, reason in failures.items():
        print(f"  FAIL {slug}: {reason}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(f"## YouTube Top 100 ({current_date})\n\n")
            summary.write(
                f"- saved: {len(saved)} / failed: {len(failures)} "
                f"of {len(COUNTRIES)}\n"
            )
            if partial:
                summary.write("\n### Short charts (source playlist under 100)\n\n")
                for slug, count in partial.items():
                    summary.write(f"- {slug}: {count}\n")
            if failures:
                summary.write("\n| country | reason |\n| --- | --- |\n")
                for slug, reason in failures.items():
                    summary.write(f"| {slug} | {reason} |\n")

    if partial:
        print(
            "::warning::YouTube chart source had fewer than "
            f"{EXPECTED_TRACKS} tracks for: {', '.join(partial)}"
        )
    if failures:
        # 일부 국가 실패는 경고로만 남긴다. 다음 단계(다른 차트 수집)를 막지 않는다.
        print(
            "::warning::YouTube chart collection failed for "
            f"{len(failures)} countries: {', '.join(failures)}"
        )
    if not saved:
        # 전부 실패했을 때만 액션을 실패로 만든다.
        raise RuntimeError("Collection failed for every country")

    return 0


if __name__ == "__main__":
    sys.exit(main())
