import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


EXPECTED_COLUMNS = [
    "Rank",
    "Previous Rank",
    "Track Name",
    "Artist Names",
    "Periods on Chart",
    "Views",
    "Growth",
    "YouTube URL",
]


def youtube_id(url):
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.lstrip("/") or None
    return parse_qs(parsed.query).get("v", [None])[0]


def format_views(value):
    return f"{int(value):,}" if value else None


def convert_file(source, destination):
    with source.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected columns in {source.name}: {reader.fieldnames}"
            )

        data = []
        for row in reader:
            previous_rank = row["Previous Rank"]
            data.append(
                {
                    "ranking": row["Rank"] or None,
                    "title": row["Track Name"] or None,
                    "artist": row["Artist Names"] or None,
                    "image": None,
                    "prev": "-" if previous_rank == "n/a" else previous_rank,
                    "streak": row["Periods on Chart"] or None,
                    "streams": format_views(row["Views"]),
                    "growth": None if row["Growth"] == "n/a" else row["Growth"],
                    "youtubeID": youtube_id(row["YouTube URL"]),
                }
            )

    if len(data) != 100:
        raise ValueError(f"Expected 100 rows in {source.name}, found {len(data)}")
    if any(not item["ranking"] or not item["title"] for item in data):
        raise ValueError(f"Missing rank or title in {source.name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Convert YouTube chart CSV files to JSON")
    parser.add_argument("date", help="Chart folder date in YYYY-MM-DD format")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise ValueError("Date must use YYYY-MM-DD format")

    source_dir = Path("csv") / args.date
    output_dir = Path("youtube") / args.date
    sources = sorted(source_dir.glob("*.csv"))
    if not sources:
        raise FileNotFoundError(f"No CSV files found in {source_dir}")

    for source in sources:
        destination = output_dir / f"{source.stem}.json"
        convert_file(source, destination)

    print(f"Converted {len(sources)} files to {output_dir}")


if __name__ == "__main__":
    main()
