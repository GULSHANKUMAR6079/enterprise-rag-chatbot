"""
SSRF-Protected Web Scraping and HTML Sanitization Engine.
Safely extracts readable text content from websites for RAG ingestion.
"""
import re
from typing import Optional, Tuple
import bs4
import httpx
from backend.app.core.exceptions import SSRFBlockedException
from backend.app.security.ssrf_protector import ssrf_protector

# Maximum download size for a single webpage (5 MB)
MAX_PAGE_BYTES = 5 * 1024 * 1024


class WebScraper:
    def __init__(self, user_agent: str = "Incerro-Enterprise-Bot/1.0 (+https://incerro.example.com/bot)"):
        self.user_agent = user_agent

    async def scrape_url(self, target_url: str, timeout: float = 12.0) -> Tuple[str, str]:
        """
        Safely fetches and extracts clean readable text from a URL.
        Returns:
            (title, clean_text)
        Raises:
            SSRFBlockedException if URL is dangerous or points to private/metadata IP.
        """
        # 1. SSRF Validation (DNS check, IP classification, scheme check)
        ssrf_protector.validate_url(target_url)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        }

        # 2. Secure HTTP Fetch with size bounds and follow redirects safely
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.get(target_url, headers=headers)

            # Re-validate redirect location if redirect occurred
            if resp.status_code in (301, 302, 303, 307, 308):
                redirect_target = resp.headers.get("Location")
                if not redirect_target:
                    raise SSRFBlockedException("Empty redirect location")
                ssrf_protector.validate_url(redirect_target)
                resp = await client.get(redirect_target, headers=headers)

            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                raise ValueError(f"Unsupported content type: {content_type}. Expected text/html.")

            # Validate Content-Length
            if len(resp.content) > MAX_PAGE_BYTES:
                raise ValueError(f"Page size ({len(resp.content)} bytes) exceeds limit of {MAX_PAGE_BYTES} bytes.")

            raw_html = resp.text

        # 3. Clean and parse HTML using BeautifulSoup
        soup = bs4.BeautifulSoup(raw_html, "html.parser")

        # Extract title
        title = soup.title.string.strip() if (soup.title and soup.title.string) else target_url

        # Extract meaningful image alt / title / asset descriptions (e.g. client logos, partner badges, awards)
        for img in soup.find_all("img"):
            alt = (img.get("alt") or "").strip()
            img_title = (img.get("title") or "").strip()
            aria_label = (img.get("aria-label") or "").strip()
            src = (img.get("src") or "").strip()

            label = alt or img_title or aria_label
            if not label and src:
                # Extract filename from path (e.g., /assets/images/autodesk.svg -> autodesk)
                raw_filename = src.split("/")[-1].split("?")[0].split(".")[0]
                raw_filename = re.sub(r"[-_]+", " ", raw_filename).strip()
                if (
                    raw_filename
                    and not raw_filename.isdigit()
                    and len(raw_filename) > 2
                    and not any(raw_filename.lower().startswith(x) for x in ["image", "img", "icon", "vector"])
                ):
                    label = raw_filename

            if label:
                img.replace_with(f" [Client / Partner / Recognition: {label}] ")

        # Strip only code/rendering scripts and styles, but KEEP footer and semantic content
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator="\n")

        # Clean excessive blank lines and whitespace
        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines = []
        for line in lines:
            if line:
                cleaned_lines.append(line)

        clean_content = "\n\n".join(cleaned_lines)

        if len(clean_content) < 50:
            raise ValueError(f"Extracted content from '{target_url}' was too sparse or empty.")

        return title, clean_content


web_scraper = WebScraper()
