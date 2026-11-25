"""Fetching a help article from a web address, safely.

SSRF protection: the server would otherwise fetch any address it is given, including ones on its own
network (a router page, a cloud metadata service). So only http and https are allowed, the host
name is resolved first and every address it resolves to must be public, and each redirect is
checked the same way before it is followed. Pages are limited in size and time.
Limit: a host that changes its DNS answer between the check and the fetch could still slip past.
"""
from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class UnsafeAddress(ValueError):
    pass


def check_address(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeAddress("Use a full web address starting with http:// or https://.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeAddress("That web address could not be found.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeAddress("That address points to a private network, so it is not fetched.")


class _Text(HTMLParser):
    """Keeps the readable text of a page: headings, paragraphs and list items, without menus or scripts."""

    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "button"}
    BLOCK = {"p", "div", "section", "article", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol", "ul"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n- " if tag == "li" else "\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).split("\n")]
    return "\n".join(line for line in lines if line and line != "-")


def fetch_article(url: str, client: httpx.Client | None = None) -> str:
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False,
                                    headers={"User-Agent": "HelpVisualAI/1.0 (article import)"})
    try:
        for _ in range(MAX_REDIRECTS + 1):
            check_address(url)
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                if response.status_code >= 400:
                    raise ValueError(f"The page answered with error {response.status_code}.")
                kind = response.headers.get("content-type", "")
                if "html" not in kind and "text/plain" not in kind:
                    raise ValueError("That address is not a web page or text file.")
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise ValueError("That page is larger than 2 MB.")
                text = body.decode(response.encoding or "utf-8", errors="replace")
                return html_to_text(text) if "html" in kind else text
        raise ValueError("That address redirects too many times.")
    finally:
        if own:
            client.close()
