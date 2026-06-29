import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import List, Tuple
from datetime import datetime
import re
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential
from config import get_settings
from database import ContentChunk, PageLink, engine
from sqlmodel import Session, select, delete

settings = get_settings()
tokenizer = tiktoken.get_encoding("cl100k_base")

# Known page categories for smarter routing
CATEGORY_MAP = {
    "personal-injury": "Claims & Accident Support",
    "serious-injury": "Claims & Accident Support",
    "fatal-injury": "Claims & Accident Support",
    "road-traffic": "Claims & Accident Support",
    "accident-at-work": "Claims & Accident Support",
    "slip-trips": "Claims & Accident Support",
    "taxi-accident": "Claims & Accident Support",
    "24-7-accident": "Claims & Accident Support",
    "criminal-injury": "Claims & Accident Support",
    "clinical-negligence": "Claims & Accident Support",
    "housing-disrepair": "Housing & Property",
    "tenancy-deposit": "Housing & Property",
    "retaliatory-eviction": "Housing & Property",
    "unlawful-eviction": "Housing & Property",
    "property-damage": "Housing & Property",
    "boundary-dispute": "Housing & Property",
    "conveyancing": "Housing & Property",
    "immigration": "Immigration",
    "visa": "Immigration",
    "asylum": "Immigration",
    "employment": "Employment Law",
    "criminal-law": "Criminal Law",
    "police-station": "Criminal Law",
    "driving-offence": "Criminal Law",
    "family-law": "Family Law",
    "wills-trusts": "Wills & Estates",
    "commercial-law": "Commercial Law",
    "mediation": "Dispute Resolution",
    "civil-dispute": "Dispute Resolution",
    "litigation": "Dispute Resolution",
    "ppi": "Financial Claims",
    "data-breach": "Data & Privacy",
    "translation": "Other Services",
    "form-filling": "Other Services",
    "no-win-no-fee": "About Us",
    "why-choose": "About Us",
    "faqs": "About Us",
    "contact": "About Us",
}


def get_category(url: str) -> str:
    url_lower = url.lower()
    for key, cat in CATEGORY_MAP.items():
        if key in url_lower:
            return cat
    return "General"


def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))


def chunk_text(text: str, url: str, title: str, max_tokens: int = 500, overlap_tokens: int = 50) -> List[dict]:
    """Split text into overlapping chunks for better retrieval."""
    words = text.split()
    chunks = []
    chunk_words = []
    current_tokens = 0
    chunk_index = 0

    for word in words:
        word_tokens = count_tokens(word + " ")
        if current_tokens + word_tokens > max_tokens and chunk_words:
            chunk_text_str = " ".join(chunk_words)
            chunks.append({
                "text": chunk_text_str,
                "url": url,
                "title": title,
                "chunk_index": chunk_index,
                "category": get_category(url),
            })
            chunk_index += 1
            # Overlap: keep last ~overlap_tokens worth of words
            overlap_words = []
            overlap_count = 0
            for w in reversed(chunk_words):
                overlap_count += count_tokens(w + " ")
                if overlap_count >= overlap_tokens:
                    break
                overlap_words.insert(0, w)
            chunk_words = overlap_words
            current_tokens = count_tokens(" ".join(chunk_words))

        chunk_words.append(word)
        current_tokens += word_tokens

    if chunk_words:
        chunks.append({
            "text": " ".join(chunk_words),
            "url": url,
            "title": title,
            "chunk_index": chunk_index,
            "category": get_category(url),
        })

    return chunks


def extract_text_from_html(html: str, url: str) -> Tuple[str, str]:
    """Extract clean text and title from HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Get title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    elif soup.title:
        title = soup.title.string or ""
    title = title.strip()

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header",
                               "noscript", "iframe", "form", "svg", "button"]):
        tag.decompose()

    # Remove elementor navigation and boilerplate
    for cls in ["elementor-nav-menu", "elementor-social-icons", "jet-menu",
                 "elementor-widget-nav-menu", "skip-link"]:
        for el in soup.find_all(class_=cls):
            el.decompose()

    # Extract main content area
    main = soup.find("main") or soup.find(id="content") or soup.find(class_="elementor-section") or soup.body
    if not main:
        main = soup

    text = main.get_text(separator=" ", strip=True)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove very short fragments
    text = re.sub(r"\b\w{1,2}\b\s*", lambda m: m.group() if len(m.group().strip()) > 1 else " ", text)

    return text, title


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_page(client: httpx.AsyncClient, url: str) -> Tuple[str, int]:
    """Fetch a page with retry logic."""
    response = await client.get(url, timeout=30.0)
    return response.text, response.status_code


async def get_sitemap_urls() -> List[str]:
    """Fetch all page URLs from the sitemap."""
    urls = []
    async with httpx.AsyncClient(
        headers={"User-Agent": "LegalAssistBot/1.0 (content indexer)"},
        follow_redirects=True
    ) as client:
        try:
            resp = await client.get(settings.site_sitemap_url, timeout=15.0)
            soup = BeautifulSoup(resp.text, "lxml-xml")
            for loc in soup.find_all("loc"):
                url = loc.text.strip()
                # Skip non-content pages
                if any(skip in url for skip in [
                    "/wp-content/", "/feed/", "/tag/", "/author/",
                    "/wp-json/", "/xmlrpc", "sitemap"
                ]):
                    continue
                urls.append(url)
        except Exception as e:
            print(f"[Scraper] Failed to fetch sitemap: {e}")

    # Add a few key pages not always in sitemap
    fallback_urls = [
        "https://legalassist.co.uk/",
        "https://legalassist.co.uk/services/",
        "https://legalassist.co.uk/contact-us/",
        "https://legalassist.co.uk/faqs-uk-leading-claims-management-company/",
        "https://legalassist.co.uk/no-win-no-fee/",
        "https://legalassist.co.uk/why-choose-us/",
    ]
    for u in fallback_urls:
        if u not in urls:
            urls.append(u)

    return list(set(urls))


async def scrape_and_index() -> dict:
    """Main entry point: scrape all pages and return chunks for embedding."""
    print("[Scraper] Starting website scrape...")
    urls = await get_sitemap_urls()
    print(f"[Scraper] Found {len(urls)} URLs to scrape")

    all_chunks = []
    page_results = []

    # Clear existing page metadata
    with Session(engine) as session:
        session.exec(delete(ContentChunk))
        session.exec(delete(PageLink))
        session.commit()

    async with httpx.AsyncClient(
        headers={"User-Agent": "LegalAssistBot/1.0 (content indexer)"},
        follow_redirects=True
    ) as client:
        # Scrape in batches of 5 to be polite
        for i in range(0, len(urls), 5):
            batch = urls[i:i+5]
            tasks = [fetch_page(client, url) for url in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"[Scraper] Error fetching {url}: {result}")
                    page_results.append({"url": url, "status": "error", "chunks": 0})
                    with Session(engine) as session:
                        session.add(ContentChunk(url=url, title="Error", chunk_count=0, status="error"))
                        session.commit()
                    continue

                html, status_code = result
                if status_code != 200:
                    page_results.append({"url": url, "status": "error", "chunks": 0})
                    continue

                text, title = extract_text_from_html(html, url)

                if len(text) < 100:
                    print(f"[Scraper] Skipping {url} - insufficient content")
                    page_results.append({"url": url, "status": "skipped", "chunks": 0})
                    with Session(engine) as session:
                        session.add(ContentChunk(url=url, title=title or url, chunk_count=0, status="skipped"))
                        session.commit()
                    continue

                chunks = chunk_text(text, url, title)
                all_chunks.extend(chunks)

                print(f"[Scraper] Indexed {url} -> {len(chunks)} chunks")
                page_results.append({"url": url, "title": title, "status": "indexed", "chunks": len(chunks)})

                with Session(engine) as session:
                    session.add(ContentChunk(
                        url=url,
                        title=title,
                        chunk_count=len(chunks),
                        status="indexed",
                        last_scraped=datetime.utcnow()
                    ))
                    session.add(PageLink(
                        url=url,
                        title=title,
                        category=get_category(url),
                        last_updated=datetime.utcnow()
                    ))
                    session.commit()

            await asyncio.sleep(0.5)  # Polite delay between batches

    print(f"[Scraper] Completed. Total chunks: {len(all_chunks)}")
    return {"chunks": all_chunks, "pages": page_results, "total_chunks": len(all_chunks)}
