# -*- coding: utf-8 -*-
"""解析层：按扩展名把 PDF/Word/Excel/PPT/HTML/图片/纯文本 统一提取为文本。

P1 先支持 PDF/Word/HTML/txt/md；Excel/PPT/图片 属 P2，但分发表已就绪。
"""
import logging
import time
from pathlib import Path
from typing import Optional

from server.core.models import ParsedContent

log = logging.getLogger(__name__)

SUPPORTED = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm",
    ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
}


def parse_path(path: str | Path, image_channel: str = "auto") -> ParsedContent:
    """按扩展名分发解析。图片走 vision 双通道（vl/ocr）。"""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"不支持的格式: {ext}（支持 {sorted(SUPPORTED)}）")

    handler = {
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
        ".xlsx": _parse_xlsx,
        ".pptx": _parse_pptx,
        ".html": _parse_html,
        ".htm": _parse_html,
        ".txt": _parse_txt,
        ".md": _parse_txt,
    }.get(ext)

    if handler is None:  # 图片
        from server.core import vision

        text, channel = vision.read_image(p, channel=image_channel)
        return ParsedContent(text=text, source_type="image", title=p.stem,
                             meta={"image_channel": channel})

    content = handler(p)
    content.title = content.title or p.stem
    content.source_type = ext.lstrip(".")
    return content


def parse_url(url: str) -> ParsedContent:
    """网页正文提取（通用：任意链接抓正文；微信文章取 js_content 节点）。"""
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("抓取网页需要 httpx + beautifulsoup4，请检查依赖")
    resp = None
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = httpx.get(url, timeout=60, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"})
            resp.raise_for_status()
            break
        except Exception as e:  # noqa: BLE001 微信等站点偶发限流，重试 3 次
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    if resp is None:
        raise RuntimeError(f"抓取失败（已重试 3 次）：{last_err}")
    soup = BeautifulSoup(resp.text, "html.parser")
    # 优先微信正文 / article / body 作为正文区，避免抓到导航与广告
    content_el = (soup.find("div", id="js_content") or soup.find("article")
                  or soup.body or soup)
    for tag in content_el(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = content_el.get_text(separator="\n")
    text = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    # 标题优先级：微信 h1#activity-name → og:title → h1 → <title> → URL
    title = ""
    an = soup.find("h1", id="activity-name")
    if an:
        title = an.get_text(strip=True)
    if not title:
        og = soup.find("meta", property="og:title")
        title = (og.get("content") or "").strip() if og else ""
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    return ParsedContent(text=text, source_type="html",
                         title=title or url, meta={"url": url})


def _parse_txt(p: Path) -> ParsedContent:
    return ParsedContent(text=p.read_text(encoding="utf-8", errors="ignore"), title=p.stem)


def _parse_pdf(p: Path) -> ParsedContent:
    parts: list[str] = []
    page_no: Optional[int] = None
    try:
        import pymupdf  # PyMuPDF

        doc = pymupdf.open(p)
        for page in doc:
            t = page.get_text("text")
            if t.strip():
                parts.append(f"=== 第{page.number + 1}页 ===\n{t.strip()}")
                page_no = page.number + 1
        doc.close()
    except Exception as e:
        log.warning("PyMuPDF 解析失败 %s: %s，尝试 pdfplumber", p, e)
        import pdfplumber

        with pdfplumber.open(p) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(f"=== 第{i + 1}页 ===\n{t.strip()}")
                    page_no = i + 1
    return ParsedContent(text="\n\n".join(parts), title=p.stem, page=page_no)


def _parse_docx(p: Path) -> ParsedContent:
    import docx

    d = docx.Document(p)
    parts = [para.text for para in d.paragraphs if para.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return ParsedContent(text="\n".join(parts), title=p.stem)


def _parse_xlsx(p: Path) -> ParsedContent:
    import openpyxl

    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"=== sheet: {ws.title} ===")
        for row in ws.iter_rows(values_only=True):
            vals = [str(v) for v in row if v is not None]
            if vals:
                parts.append(" | ".join(vals))
    wb.close()
    return ParsedContent(text="\n".join(parts), title=p.stem)


def _parse_pptx(p: Path) -> ParsedContent:
    from pptx import Presentation

    prs = Presentation(p)
    parts = []
    for i, slide in enumerate(prs.slides):
        parts.append(f"=== 幻灯片 {i + 1} ===")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = "".join(run.text for run in para.runs).strip()
                    if t:
                        parts.append(t)
    return ParsedContent(text="\n".join(parts), title=p.stem)


def _parse_html(p: Path) -> ParsedContent:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return ParsedContent(text=text, title=soup.title.string.strip() if soup.title else p.stem)