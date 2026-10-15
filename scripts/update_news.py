import json
import urllib.request
import xml.etree.ElementTree as ET
import re

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


RSS_URL = "https://www.vg.no/rss/feed/?format=rss"
NEWS_FILE = Path("news.json")
MAX_ARTICLES = 3

# Namespace mapping for common media extensions
NS = {"media": "http://search.yahoo.com/mrss/"}


def extract_image_from_item(item):
    # 1) <enclosure url="..." />
    enclosure = item.find("enclosure")
    if enclosure is not None and enclosure.attrib.get("url"):
        return enclosure.attrib.get("url")

    # 2) <media:content url="..." /> (or inside media:group)
    media = item.find("media:content", NS)
    if media is not None and media.attrib.get("url"):
        return media.attrib.get("url")

    media_group = item.find("media:group", NS)
    if media_group is not None:
        mg_media = media_group.find("media:content", NS)
        if mg_media is not None and mg_media.attrib.get("url"):
            return mg_media.attrib.get("url")

    # 3) <media:thumbnail url="..." />
    thumb = item.find("media:thumbnail", NS)
    if thumb is not None and thumb.attrib.get("url"):
        return thumb.attrib.get("url")

    # 4) Try to find an <img> tag in the description/content
    desc = item.find("description")
    if desc is not None and desc.text:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc.text)
        if m:
            return m.group(1)

    # No image found
    return None


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

        if not (link.startswith("https://www.vg.no/") or link.startswith("https://vg.no/")):
            continue

        pub_date = ""
        if date_element is not None and date_element.text:
            raw_date = date_element.text.strip()
            try:
                pub_date = parsedate_to_datetime(raw_date).isoformat()
            except (TypeError, ValueError, OverflowError):
                pub_date = raw_date

        image_url = extract_image_from_item(item)

        article = {"title": title, "link": link, "pubDate": pub_date}
        if image_url:
            article["image"] = image_url

        articles.append(article)
        if len(articles) >= MAX_ARTICLES:
            break

    if not articles:
        raise RuntimeError("Ingen gyldige artikler funnet i VG RSS-feeden. news.json beholdes uendret.")

    # Oppdater bare news.json når VG faktisk har levert nye/endrede overskrifter.
    # Dette unngår unødvendige commits hvert 15. minutt.
    existing = {}
    if NEWS_FILE.exists():
        try:
            existing = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    same_articles = existing.get("articles") == articles
    if same_articles and existing.get("updatedAt"):
        print(f"VG-feeden ble kontrollert. Ingen endringer blant de {len(articles)} øverste artiklene.")
        return

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }
    NEWS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Lagret {len(articles)} VG-artikler i news.json.")


if __name__ == "__main__":
    main()
