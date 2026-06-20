"""
convertir.py
────────────
Converts files (EPUB, PDF, DOCX, etc.) to clean Markdown using MarkItDown.

For EPUBs, handles two structural types automatically:
  - Text-based EPUBs : HTML chapters with optional image tables/figures
  - Image-based EPUBs: all content stored as page scans (JPG/PNG)

Both types use Gemini Vision for image content extraction.

Requirement for images: GEMINI_API_KEY environment variable

Usage:
    python convertir.py "book.epub"
    python convertir.py "book.epub" -o output.md
    python convertir.py "document.pdf"

Note: Output language always matches the source book.
"""

import re
import os
import sys
import zipfile
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


# ── Constants ──────────────────────────────────────────────────────────────────

# Exact filenames always treated as decorative
DECORATIVE_IMAGES = {
    "arr.jpg", "arrb.jpg", "arrg.jpg",
    "copy.jpg",
    "lineb.jpg", "line.jpg", "linen.jpg",
}

# Alt text keywords that identify decorative images
DECORATIVE_ALT_KEYWORDS = {"ornament", "logo", "next reads", "next-reads"}

SKIP_SECTIONS = {
    "cover.html", "halftitle.html", "copyright.html",
    "contents.html", "reader.html", "title.html",
    "index.html", "toc.html", "nav.html",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Minimum characters of real text to consider an EPUB "text-based"
TEXT_EPUB_MIN_CHARS = 500

# Minimum characters of real text to consider a PDF "text-based"
TEXT_PDF_MIN_CHARS = 500

# Minimum image file size (bytes) to consider a PDF image as content (not decorative)
PDF_IMAGE_MIN_BYTES = 5_000

# Minimum image dimension (pixels) to consider a PDF image as content
PDF_IMAGE_MIN_DIM = 100

VISION_PROMPT = """\
Extract all content from this image as clean Markdown.
Respond in the same language as the text visible in the image.
If the image contains no text, describe it briefly in English.

Rules by image type:
- Data table or training zones  → use Markdown table syntax with | headers |
- Weekly training plan          → preserve the week/day grid as a Markdown table
- Chart or diagram              → describe it accurately in prose, including axis values if visible
- Pace or rate list             → transcribe it completely and exactly
- Full page of prose text       → transcribe the text exactly as written

Output ONLY the Markdown content. No explanations, no preamble."""


# ── Image and link helpers ─────────────────────────────────────────────────────

def is_decorative(fname: str, alt: str) -> bool:
    """
    Returns True if an image is decorative and should be removed silently.
    Works across different EPUB publishers without hardcoding filenames.
    """
    fname_l = fname.lower()
    alt_l   = alt.lower()

    # Explicit filename set
    if fname_l in {d.lower() for d in DECORATIVE_IMAGES}:
        return True

    # Filename patterns common across publishers
    if any([
        "cover"      in fname_l and fname_l.endswith((".jpg", ".png")),
        "title_page" in fname_l,
        "_logo"      in fname_l,
        "next-reads" in fname_l,
        "backad"     in fname_l,
        "globalback" in fname_l,
        re.match(r"000_bar",     fname_l),
        re.match(r"000_section", fname_l),
    ]):
        return True

    # Alt text indicates decorative role
    if any(kw in alt_l for kw in DECORATIVE_ALT_KEYWORDS):
        return True

    return False


def section_header_from_alt(alt: str) -> str | None:
    """
    Some EPUBs use images for section title pages.
    If the alt text looks like a section title, return it as a Markdown header.
    """
    alt = alt.strip()
    if not alt:
        return None
    # Heuristic: short alt text that mentions a section/part
    if len(alt) < 80 and any(kw in alt.lower() for kw in ["section", "part "]):
        return f"\n\n---\n\n## {alt}\n\n"
    return None


def clean_links(text: str) -> str:
    """
    Removes internal EPUB navigation links, keeping only the visible text.
    Handles both .html and .xhtml link targets.
    Example: [Chapter 1](chapter01.xhtml) → Chapter 1
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]*\.xhtml[^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\.html[^)]*\)",  r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\(#[^)]+\)",             r"\1", text)
    return text


def resize_if_needed(image_bytes: bytes, max_px: int = 7900) -> bytes:
    """
    Resizes image bytes if either dimension exceeds max_px.
    Returns the (possibly resized) image as JPEG bytes.
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        if w <= max_px and h <= max_px:
            return image_bytes  # Already within limits
        scale = min(max_px / w, max_px / h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except ImportError:
        print("  WARNING: Pillow not installed — cannot resize large images.")
        print("           Run: pip install Pillow")
        return image_bytes
    except Exception as e:
        print(f"  WARNING: Could not resize image: {e}")
        return image_bytes


def ocr_image(image_bytes: bytes, client, model: str, label: str = "") -> str | None:
    """Sends image bytes to Gemini Vision and returns Markdown text."""
    try:
        from google.genai import types
        image_bytes = resize_if_needed(image_bytes)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=model,
            contents=[image_part, VISION_PROMPT],
            config=types.GenerateContentConfig(max_output_tokens=4096),
        )
        return response.text.strip()
    except Exception as e:
        print(f"  WARNING: Gemini Vision failed{f' for {label}' if label else ''}: {e}")
        return None


def read_image_from_epub(zf: zipfile.ZipFile, entry_path: str) -> bytes | None:
    """Reads image bytes from an open ZipFile."""
    try:
        return zf.read(entry_path)
    except Exception as e:
        print(f"  WARNING: Could not read '{entry_path}': {e}")
        return None


# ── OPF spine parser ───────────────────────────────────────────────────────────

def get_spine_images(epub_path: str) -> list[str]:
    """
    Parses the EPUB OPF manifest and spine to get content images in reading order.
    Returns a list of ZIP entry paths for images that should be processed.
    """
    OPF_NS  = "http://www.idpf.org/2007/opf"
    CONT_NS = "urn:oasis:names:tc:opendocument:xmlns:container"

    with zipfile.ZipFile(epub_path, "r") as zf:
        # 1. Find OPF path from container.xml
        try:
            container_xml = zf.read("META-INF/container.xml")
            container = ET.fromstring(container_xml)
            rootfile = container.find(f".//{{{CONT_NS}}}rootfile")
            opf_path = rootfile.get("full-path") if rootfile is not None else None
        except Exception:
            opf_path = None

        if not opf_path:
            # Fallback: find any .opf file
            opf_path = next((n for n in zf.namelist() if n.endswith(".opf")), None)
        if not opf_path:
            return []

        opf_dir = str(Path(opf_path).parent).replace("\\", "/")
        if opf_dir == ".":
            opf_dir = ""

        # 2. Parse OPF
        try:
            opf_xml = zf.read(opf_path)
            opf = ET.fromstring(opf_xml)
        except Exception as e:
            print(f"  WARNING: Could not parse OPF: {e}")
            return []

        # 3. Build manifest id → {href, media_type}
        manifest = {}
        for item in opf.iter(f"{{{OPF_NS}}}item"):
            item_id = item.get("id")
            href    = item.get("href", "")
            mtype   = item.get("media-type", "")
            if item_id:
                manifest[item_id] = {"href": href, "media_type": mtype}

        # 4. Walk spine in order
        result = []
        all_zip_names_lower = {n.lower(): n for n in zf.namelist()}

        def resolve(href: str) -> str | None:
            """Resolve a relative href to a ZIP entry path."""
            if opf_dir:
                full = f"{opf_dir}/{href}"
            else:
                full = href
            # Normalize
            parts = []
            for p in full.replace("\\", "/").split("/"):
                if p == "..":
                    if parts:
                        parts.pop()
                elif p and p != ".":
                    parts.append(p)
            candidate = "/".join(parts)
            # Case-insensitive lookup
            return all_zip_names_lower.get(candidate.lower())

        for itemref in opf.iter(f"{{{OPF_NS}}}itemref"):
            idref = itemref.get("idref")
            if idref not in manifest:
                continue
            item = manifest[idref]
            mtype = item["media_type"]
            href  = item["href"]

            if mtype.startswith("image/"):
                # Direct image spine item
                entry = resolve(href)
                if entry and Path(entry).name.lower() not in {d.lower() for d in DECORATIVE_IMAGES}:
                    result.append(entry)

            elif "html" in mtype or "xhtml" in mtype:
                # HTML spine item: look for embedded images
                entry = resolve(href)
                if not entry:
                    continue
                try:
                    html_bytes = zf.read(entry)
                    html_text  = html_bytes.decode("utf-8", errors="replace")
                    # Find <img src="..."> references
                    for img_href in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_text, re.IGNORECASE):
                        # Resolve relative to the HTML file's directory
                        html_dir = str(Path(entry).parent).replace("\\", "/")
                        if img_href.startswith("../"):
                            img_href_clean = img_href[3:]
                            if html_dir:
                                parent = str(Path(html_dir).parent).replace("\\", "/")
                                img_full = f"{parent}/{img_href_clean}" if parent and parent != "." else img_href_clean
                            else:
                                img_full = img_href_clean
                        else:
                            img_full = f"{html_dir}/{img_href}" if html_dir and html_dir != "." else img_href
                        img_entry = all_zip_names_lower.get(img_full.lower())
                        if img_entry and Path(img_entry).name.lower() not in {d.lower() for d in DECORATIVE_IMAGES}:
                            if Path(img_entry).suffix.lower() in IMAGE_EXTENSIONS:
                                result.append(img_entry)
                except Exception:
                    pass

    return result


# ── Image-based EPUB processing ────────────────────────────────────────────────

def process_image_epub(epub_path: str, client, model: str) -> str:
    """
    Processes an image-based EPUB by OCR-ing each content page in spine order.
    Used when the EPUB has no extractable text (all content is page scans).
    """
    print("  Detected image-based EPUB — reading spine order...")
    spine_images = get_spine_images(epub_path)

    if not spine_images:
        print("  WARNING: Could not determine spine order. Falling back to sorted filenames.")
        with zipfile.ZipFile(epub_path, "r") as zf:
            spine_images = sorted([
                n for n in zf.namelist()
                if Path(n).suffix.lower() in IMAGE_EXTENSIONS
                and Path(n).name.lower() not in {d.lower() for d in DECORATIVE_IMAGES}
            ])

    print(f"  Pages to process: {len(spine_images)}")
    if not client:
        print("  WARNING: No API key — cannot OCR image pages. Output will be empty.")
        return ""

    parts = []
    with zipfile.ZipFile(epub_path, "r") as zf:
        for i, entry in enumerate(spine_images, 1):
            fname = Path(entry).name
            print(f"  [{i}/{len(spine_images)}] {fname}")
            image_bytes = read_image_from_epub(zf, entry)
            if image_bytes:
                text = ocr_image(image_bytes, client, model, label=fname)
                if text:
                    parts.append(text)

    return "\n\n---\n\n".join(parts)


# ── Text-based EPUB processing ─────────────────────────────────────────────────

def remove_epub_noise(raw_text: str) -> str:
    """
    Removes MarkItDown ZIP-format noise from text-based EPUBs.
    Keeps only HTML sections with real content.
    Falls back to raw text if no HTML sections are found.
    """
    if "## File: " not in raw_text:
        return raw_text  # New EpubConverter format: already clean

    parts = re.split(r"\r?\n## File: ", raw_text)
    kept = []

    for part in parts:
        header_line, _, body = part.partition("\n")
        header = header_line.strip().replace("\\", "/")

        # Keep any .html/.xhtml file regardless of parent directory
        if not (header.endswith(".html") or header.endswith(".xhtml")):
            continue
        if Path(header).name.lower() in SKIP_SECTIONS:
            continue

        # Clean internal EPUB links → keep only visible text
        body = re.sub(r"\[([^\]]+)\]\([^)]*\.html[^)]*\)", r"\1", body)
        body = re.sub(r"\[([^\]]*)\]\(#[^)]+\)", r"\1", body)

        body = body.strip()
        if body:
            kept.append(body)

    if not kept:
        return ""  # Signal empty to caller

    return "\n\n---\n\n".join(kept)


def process_inline_images(text: str, epub_path: str, client, model: str) -> str:
    """
    Replaces inline image references in text-based EPUB Markdown:
    - Decorative images        → removed silently
    - Section title images     → converted to Markdown headers using alt text
    - Content images + Vision  → replaced with Gemini OCR output
    - Content images no Vision → marked as [IMAGE: filename]
    """
    image_cache: dict[str, str] = {}

    def replacer(match: re.Match) -> str:
        alt    = match.group(1)
        img_src = match.group(2)
        fname  = Path(img_src).name

        # Decorative: remove silently
        if is_decorative(fname, alt):
            return ""

        # Section title image: use alt text as a Markdown header
        header = section_header_from_alt(alt)
        if header:
            return header

        # Content image: OCR with Vision or leave placeholder
        if Path(fname).suffix.lower() in IMAGE_EXTENSIONS:
            if client and epub_path:
                if fname not in image_cache:
                    print(f"   Processing image: {fname}")
                    try:
                        with zipfile.ZipFile(epub_path, "r") as zf:
                            entry = next(
                                (n for n in zf.namelist() if Path(n).name == fname),
                                None,
                            )
                            img_bytes = zf.read(entry) if entry else None
                    except Exception:
                        img_bytes = None

                    if img_bytes:
                        result = ocr_image(img_bytes, client, model, label=fname)
                        image_cache[fname] = result if result else f"[IMAGE: {fname}]"
                    else:
                        image_cache[fname] = f"[IMAGE: {fname}]"

                return f"\n{image_cache[fname]}\n"

        return f"[IMAGE: {fname}]"

    # Capture both alt text and src: ![alt text](path/to/image.jpg)
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replacer, text)


def process_text_epub(epub_path: str, raw_text: str, client, model: str) -> str:
    """Processes a text-based EPUB: removes noise, cleans links, handles images."""
    text = remove_epub_noise(raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # clean_links runs always: handles .xhtml and .html internal links
    # regardless of whether remove_epub_noise ran or passed through
    text = clean_links(text)
    text = process_inline_images(text, epub_path, client, model)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ── PDF Vision processing ──────────────────────────────────────────────────────

def process_scanned_pdf(pdf_path: str, client, model: str) -> str:
    """
    Processes a fully scanned PDF by rendering each page as an image
    and sending it to Gemini Vision. Used when the PDF has no extractable text.
    """
    try:
        import fitz
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
        return ""

    doc = fitz.open(pdf_path)
    total = len(doc)
    print(f"  Scanned PDF detected — pages to process: {total}")

    parts = []
    mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR quality

    for page_num in range(total):
        label = f"page {page_num + 1}/{total}"
        print(f"  [{page_num + 1}/{total}] Rendering {label}...")
        try:
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            image_bytes = pix.tobytes("jpeg")
            text = ocr_image(image_bytes, client, model, label=label)
            if text:
                parts.append(text)
        except Exception as e:
            print(f"  WARNING: Could not process {label}: {e}")

    doc.close()
    return "\n\n---\n\n".join(parts)


def extract_pdf_images(pdf_path: str, client, model: str) -> str:
    """
    Extracts embedded content images from a text-based PDF and OCRs them
    with Gemini Vision. Skips decorative images (too small in size or dimensions).
    Deduplicates images that appear on multiple pages (e.g. repeated logos).
    Returns a Markdown string with all OCR results, to be appended at the end.
    """
    try:
        import fitz
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
        return ""

    doc = fitz.open(pdf_path)
    parts = []
    seen_xrefs: set[int] = set()
    total_found = 0
    total_processed = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]

            # Skip duplicates (same image on multiple pages)
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                width       = base_image["width"]
                height      = base_image["height"]

                # Skip decorative images by size and dimensions
                if len(image_bytes) < PDF_IMAGE_MIN_BYTES:
                    continue
                if width < PDF_IMAGE_MIN_DIM or height < PDF_IMAGE_MIN_DIM:
                    continue

                total_found += 1
                label = f"page {page_num + 1}, image {total_found}"
                print(f"  Processing image: {label} ({width}x{height}px)")

                text = ocr_image(image_bytes, client, model, label=label)
                if text:
                    parts.append(f"<!-- Image — {label} -->\n{text}")
                    total_processed += 1

            except Exception as e:
                print(f"  WARNING: Could not extract image on page {page_num + 1}: {e}")

    doc.close()

    if not parts:
        return ""

    print(f"  Extracted {total_processed} content image(s) from PDF.")
    return "\n\n---\n\n".join(parts)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def convert(input_path: str, output_path: str, model: str) -> None:
    try:
        from markitdown import MarkItDown
    except ImportError:
        print("ERROR: MarkItDown not installed. Run: pip install markitdown")
        sys.exit(1)

    is_epub = input_path.lower().endswith(".epub")
    is_pdf  = input_path.lower().endswith(".pdf")

    # Initialize Gemini client (EPUB and PDF)
    client = None
    if is_epub or is_pdf:
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                print(f"Gemini Vision active — model: {model}")
            except ImportError:
                print("WARNING: 'google-genai' not installed.")
                print("         Run: pip install google-genai")
                print("         Images will be skipped.")
        else:
            print("WARNING: GEMINI_API_KEY not found.")
            print("         Set it with: $env:GEMINI_API_KEY = 'AIza...'")
            print("         Images will be skipped.")

    print(f"Converting '{input_path}'...")
    md = MarkItDown()
    result = md.convert(input_path)
    raw_text = result.text_content

    if is_epub:
        # Determine EPUB type: text-based or image-based
        text_content = remove_epub_noise(raw_text)

        if len(text_content.strip()) >= TEXT_EPUB_MIN_CHARS:
            # Text-based EPUB (e.g. Hansons First Marathon)
            print("  Text-based EPUB detected.")
            final_text = process_text_epub(input_path, raw_text, client, model)
        else:
            # Image-based EPUB (e.g. Run Less Run Faster)
            final_text = process_image_epub(input_path, client, model)

    elif is_pdf and client:
        if len(raw_text.strip()) < TEXT_PDF_MIN_CHARS:
            # Scanned PDF — no extractable text
            final_text = process_scanned_pdf(input_path, client, model)
        else:
            # Text-based PDF — extract text + append embedded images
            print("  Text-based PDF detected.")
            image_text = extract_pdf_images(input_path, client, model)
            if image_text:
                final_text = (
                    raw_text.rstrip()
                    + "\n\n---\n\n## Imágenes extraídas\n\n"
                    + image_text
                )
            else:
                final_text = raw_text

    else:
        final_text = raw_text

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_text)

    size = len(final_text)
    if size == 0:
        print(f"WARNING: Output file is empty.")
    else:
        print(f"Saved as '{output_path}' ({size:,} characters)")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Converts files to Markdown using MarkItDown + Gemini Vision for images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convertir.py "Hansons First Marathon.epub"
  python convertir.py "Run Less Run Faster.epub"
  python convertir.py "book.epub" -o kb/book.md
  python convertir.py "document.pdf"
        """,
    )
    parser.add_argument("input", help="Input file (epub, pdf, docx, etc.)")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output .md file (default: same name as input with .md extension)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        metavar="MODEL",
        help="Gemini model for Vision OCR (default: gemini-2.5-flash)",
    )
    args = parser.parse_args()

    output = args.output or str(Path(args.input).with_suffix(".md"))

    try:
        convert(args.input, output, args.model)
    except FileNotFoundError:
        print(f"ERROR: File not found: '{args.input}'")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
