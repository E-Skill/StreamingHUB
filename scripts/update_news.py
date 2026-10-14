import json
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


RSS_URL = "https://www.vg.no/rss/feed/?format=rss"


def main():
    request = urllib.request.Request(
        RSS_URL,
        headers={
            "User-Agent": "Mozilla/5.0 StreamingHUB/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    articles = []

    for item in root.findall(".//item"):
        title_element = item.find("title")
        link_element = item.find("link")
        date_element = item.find("pubDate")

        if title_element is None or link_element is None:
            continue

        title = "".join(title_element.itertext()).strip()
        link = "".join(link_element.itertext()).strip()

        if not title or not link:
            continue

        if not (
            link.startswith("https://www.vg.no/")
            or link.startswith("https://vg.no/")
        ):
            continue

        pub_date = ""

        if date_element is not None and date_element.text:
            raw_date = date_element.text.strip()

            try:
                pub_date = parsedate_to_datetime(raw_date).isoformat()
            except (TypeError, ValueError, OverflowError):
                pub_date = raw_date

        articles.append({
            "title": title,
            "link": link,
            "pubDate": pub_date,
        })

        if len(articles) >= 10:
            break

    if not articles:
        raise RuntimeError(
            "Ingen gyldige artikler funnet i VG RSS-feeden."
        )

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }

    Path("news.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Lagret {len(articles)} VG-artikler.")


if __name__ == "__main__":
    main()
