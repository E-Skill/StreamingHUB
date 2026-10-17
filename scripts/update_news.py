import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from mimetypes import guess_extension
from pathlib import Path
from urllib.parse import urlsplit


RSS_URL = "https://www.nrk.no/toppsaker.rss"
NEWS_FILE = Path("news.json")
MAX_ARTICLES = 3
STATIC_NEWS_DIR = Path("static/news")
NS = {"media": "http://search.yahoo.com/mrss/"}


def ensure_static_dir():
    try:
        STATIC_NEWS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def filename_for_url(url: str) -> str:
    digest = sha1(url.encode("utf-8")).hexdigest()
    path = urlsplit(url).path
    ext = os.path.splitext(path)[1]
    if ext:
        return f"{digest}{ext}"
    return digest


def download_image(image_url: str) -> str:
    try:
        ensure_static_dir()
        filename = filename_for_url(image_url)
        dest = STATIC_NEWS_DIR / filename
        # If file already exists, return raw.githubusercontent URL
        if dest.exists():
            return f"https://raw.githubusercontent.com/E-Skill/StreamingHUB/main/{dest.as_posix()}"

        request = urllib.request.Request(
            image_url,
            headers={
                "User-Agent": "Mozilla/5.0 StreamingHUB/1.0",
                "Accept": "image/*,*/*;q=0.8",
                "Referer": "https://www.nrk.no/",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
            content_type = response.headers.get_content_type()
            # If destination has no extension, try to guess from content-type
            if not dest.suffix:
                guessed_ext = guess_extension(content_type) or ''
                if guessed_ext:
                    dest = STATIC_NEWS_DIR / f"{filename}{guessed_ext}"

            with open(dest, "wb") as f:
                f.write(data)

        return f"https://raw.githubusercontent.com/E-Skill/StreamingHUB/main/{dest.as_posix()}"
    except Exception:
        # fallback to original URL
        return image_url


def extract_image_from_item(item):
    enclosure = item.find("enclosure")
    if enclosure is not None and enclosure.attrib.get("url"):
        return enclosure.attrib.get("url")

    media = item.find("media:content", NS)
    if media is not None and media.attrib.get("url"):
        return media.attrib.get("url")

    media_group = item.find("media:group", NS)
    if media_group is not None:
        mg_media = media_group.find("media:content", NS)
        if mg_media is not None and mg_media.attrib.get("url"):
            return mg_media.attrib.get("url")

    thumb = item.find("media:thumbnail", NS)
    if thumb is not None and thumb.attrib.get("url"):
        return thumb.attrib.get("url")

    desc = item.find("description")
    if desc is not None and desc.text:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc.text)
        if match:
            return match.group(1)

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

        if not (link.startswith("https://www.nrk.no/") or link.startswith("https://nrk.no/")):
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
            # Attempt to download and cache image; prefer raw.githubusercontent URL after commit
            cached = download_image(image_url)
            article["image"] = cached

        articles.append(article)
        if len(articles) >= MAX_ARTICLES:
            break

    if not articles:
        raise RuntimeError("Ingen gyldige artikler funnet i NRK RSS-feeden. news.json beholdes uendret.")

    existing = {}
    if NEWS_FILE.exists():
        try:
            existing = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    same_articles = existing.get("articles") == articles
    if same_articles and existing.get("updatedAt"):
        print(f"NRK-feeden ble kontrollert. Ingen endringer blant de {len(articles)} øverste artiklene.")
        return

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "articles": articles,
    }
    NEWS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Lagret {len(articles)} NRK-artikler i news.json.")


if __name__ == "__main__":
    main()
