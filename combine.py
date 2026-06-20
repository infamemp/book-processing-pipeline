#!/usr/bin/env python3
"""
combine_kb.py — Combines individual KB markdown files into a single kb_final.md.

Usage:
    python combine_kb.py --input ./kb_files --output kb_final.md
    python combine_kb.py --input ./kb_files --output kb_final.md --order "file1.md,file2.md,file3.md"
    python combine_kb.py --input ./kb_files --output kb_final.md --no-prefix
    python combine_kb.py --input ./kb_files --output kb_final.md --no-toc
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "with", "and", "or", "in",
    "on", "by", "at", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "its", "it", "this", "that", "these", "those",
}

EDITION_MAP = {
    "1st": "1e", "2nd": "2e", "3rd": "3e", "4th": "4e",
    "5th": "5e", "6th": "6e", "7th": "7e", "8th": "8e", "9th": "9e",
}

BANNER_WIDTH = 80


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def natural_sort_key(s: str) -> list:
    """Sort correctly: file_002.md before file_010.md."""
    return [int(c) if c.isdigit() else c.lower()
            for c in re.split(r"(\d+)", s)]


def normalize_line_endings(text: str) -> tuple:
    """
    Normalize CRLF and lone CR to LF.
    Returns (normalized_text, had_crlf).
    """
    had_crlf = "\r\n" in text or ("\r" in text and "\n" not in text)
    return text.replace("\r\n", "\n").replace("\r", "\n"), had_crlf


def strip_yaml_frontmatter(text: str) -> tuple:
    """
    If text starts with a YAML block (--- ... ---), extract it.
    Returns (frontmatter_content, body_without_frontmatter).
    Returns ("", text) if no frontmatter is found.
    """
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    frontmatter = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    return frontmatter, body


def extract_h1(text: str) -> str:
    """Return the first H1 heading found in text, or empty string."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Abbreviation auto-detection
# ---------------------------------------------------------------------------

def detect_edition_suffix(text: str) -> str:
    """
    Detect edition number from a title string.
    Only matches editions NOT followed by a year inside the same parentheses.
    Examples:
      '(2nd Edition)'       -> '2e'   (no year: suffix included)
      '(3rd Edition, 2021)' -> ''     (year present: suffix ignored)
    """
    m = re.search(
        r"\(\s*(1st|2nd|3rd|4th|5th|6th|7th|8th|9th)\s+ed(?:ition)?\s*\)",
        text, re.IGNORECASE
    )
    if m:
        return EDITION_MAP.get(m.group(1).lower(), "")
    return ""


def make_abbreviation(h1: str) -> str:
    """
    Auto-generate a short abbreviation from the book's H1 title.

    Logic:
      1. Split on ' — ' separators; take the last non-KB/non-Knowledge-Base segment.
      2. Detect edition suffix (only when no year accompanies the edition).
      3. Remove all parenthetical content from the title segment.
      4. Tokenize by whitespace; filter stop words.
      5. If more than 5 significant tokens, use the last 4
         (series names like "Runner's World" tend to appear first).
      6. Take the first letter of each token, uppercase.
         Hyphenated compounds count as one token (first letter only).
      7. Append edition suffix.
      8. Cap total at 8 characters.
    """
    if not h1:
        return "BK"

    edition = detect_edition_suffix(h1)

    # Isolate book title: last segment after ' — '
    segments = re.split(r"\s+[—–]\s+", h1)
    title = h1
    for seg in reversed(segments):
        if not re.match(r"^(kb|knowledge\s+base)$", seg.strip(), re.IGNORECASE):
            title = seg.strip()
            break

    # Remove parenthetical content
    title = re.sub(r"\(.*?\)", "", title).strip()

    # Tokenize and filter stop words
    tokens = title.split()
    significant = [t for t in tokens if t.lower().rstrip("'s.,!?") not in STOPWORDS]
    if not significant:
        significant = tokens

    # If too many tokens, use the last 4 (series prefix tends to be first)
    if len(significant) > 5:
        significant = significant[-4:]

    # Build abbreviation: first letter of each token
    abbr = ""
    for token in significant:
        clean = re.sub(r"[^a-zA-Z0-9\-]", "", token)
        if clean:
            abbr += clean[0].upper()

    return (abbr + edition)[:8] or "BK"


def resolve_abbreviation_conflicts(parsed: list) -> list:
    """
    If two or more books generate the same abbreviation, append a numeric
    suffix to disambiguate: HMM -> HMM, HMM2, HMM3, ...
    Returns a list of warning strings for any conflicts found.
    """
    seen = {}
    conflict_warnings = []
    for p in parsed:
        base = p["abbr"]
        if base not in seen:
            seen[base] = 1
        else:
            seen[base] += 1
            new_abbr = f"{base}{seen[base]}"
            conflict_warnings.append(
                f"Abbreviation conflict: [{base}] used by multiple books. "
                f"Renamed to [{new_abbr}] for: {p['filename']}"
            )
            p["abbr"] = new_abbr
    return conflict_warnings


# ---------------------------------------------------------------------------
# Author extraction
# ---------------------------------------------------------------------------

def extract_authors(h1: str, body: str) -> str:
    """
    Try to extract author names from:
      1. H1 pattern: 'KB — Author Name — Book Title' (middle segment)
      2. Fallback: scan the first 40 lines for an 'Authors:' field.
    """
    segments = re.split(r"\s+[—–]\s+", h1)
    if len(segments) >= 3:
        return segments[1].strip()

    for line in body.split("\n")[:40]:
        m = re.match(r"\*?\*?Authors?\*?\*?[:：]\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".")

    return ""


# ---------------------------------------------------------------------------
# Section heading prefix
# ---------------------------------------------------------------------------

def prefix_section_headings(text: str, prefix: str) -> str:
    """
    Add [PREFIX] to ## N. headings only (level-2 headings that start with a number).
    Level 1, 3, 4... headings are untouched.
    """
    return re.sub(
        r"^(##\s+)(\d+[\.\s])",
        lambda m: f"{m.group(1)}[{prefix}] {m.group(2)}",
        text,
        flags=re.MULTILINE,
    )


def collect_h2_sections(text: str) -> list:
    """Return a list of all ## heading texts found in text."""
    return [m.group(1).strip()
            for m in re.finditer(r"^##\s+(.+)$", text, re.MULTILINE)]


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def make_book_banner(book_num: int, total: int, abbr: str, title: str,
                     authors: str, filename: str, line_count: int,
                     size_kb: float, position: str) -> str:
    """Generate a clearly visible START or END banner for each book block."""
    bar = "#" * BANNER_WIDTH
    if position == "start":
        lines = [
            "",
            bar,
            f"##  BOOK {book_num} / {total}  —  START",
            f"##  [{abbr}]  {title}",
        ]
        if authors:
            lines.append(f"##  Authors: {authors}")
        lines += [
            f"##  File: {filename}  |  {line_count:,} lines  |  {size_kb:.1f} KB",
            bar,
            "",
        ]
    else:
        lines = [
            "",
            bar,
            f"##  BOOK {book_num} / {total}  —  END  —  [{abbr}]",
            bar,
            "",
        ]
    return "\n".join(lines)


def build_toc(parsed: list) -> str:
    """Generate a table of contents listing all ## sections per book."""
    lines = ["## Table of Contents", ""]
    for p in parsed:
        header = f"### [{p['abbr']}]  {p['title']}"
        if p.get("authors"):
            header += f"  ·  {p['authors']}"
        lines.append(header)
        for heading in p["sections"]:
            anchor = re.sub(r"[^\w\s-]", "", heading.lower())
            anchor = re.sub(r"\s+", "-", anchor.strip())
            anchor = re.sub(r"-{2,}", "-", anchor)
            lines.append(f"  - [{heading}](#{anchor})")
        lines.append("")
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """Approximate token count: ~4 characters per token."""
    return len(text) // 4


def build_yaml_frontmatter(parsed: list, now: str, no_prefix: bool) -> str:
    """Build consolidated YAML frontmatter optimized for Claude Projects."""
    books_yaml = "\n".join(
        f'  - abbr: "{p["abbr"]}"\n'
        f'    title: "{p["title"]}"\n'
        f'    authors: "{p["authors"]}"\n'
        f'    file: "{p["filename"]}"'
        for p in parsed
    )
    return (
        "---\n"
        'kb_title: "Combined Knowledge Base"\n'
        f'generated: "{now}"\n'
        f'source_count: {len(parsed)}\n'
        f'books:\n{books_yaml}\n'
        f'prefix_headings: {"false" if no_prefix else "true"}\n'
        "---\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Combines individual KB markdown files into a single kb_final.md.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--input", required=True,
                    help="Folder containing the .md files to combine.")
    ap.add_argument("--output", required=True,
                    help="Output file path. Example: kb_final.md")
    ap.add_argument("--order", default="",
                    help=(
                        "Comma-separated list of filenames in the desired order. "
                        "If omitted, files are sorted automatically (natural sort). "
                        "Recommended when filenames are not numerically ordered."
                    ))
    ap.add_argument("--pattern", default="",
                    help="Optional filename prefix filter. Default: all .md files.")
    ap.add_argument("--no-prefix", action="store_true", default=False,
                    help=(
                        "Disable [ABBR] prefix on section headings. "
                        "By default, prefixes are ON to avoid section number collisions."
                    ))
    ap.add_argument("--no-toc", action="store_true", default=False,
                    help="Skip table of contents generation.")
    args = ap.parse_args()

    if not os.path.isdir(args.input):
        sys.exit(f"ERROR: folder '{args.input}' does not exist.")

    # ── File resolution ──────────────────────────────────────────────────────
    if args.order:
        files = [f.strip() for f in args.order.split(",") if f.strip()]
        missing = [f for f in files
                   if not os.path.isfile(os.path.join(args.input, f))]
        if missing:
            sys.exit(
                f"ERROR: the following files were not found in '{args.input}':\n  " +
                "\n  ".join(missing)
            )
    else:
        all_md = [f for f in os.listdir(args.input) if f.endswith(".md")]
        if args.pattern:
            all_md = [f for f in all_md if f.startswith(args.pattern)]
        files = sorted(all_md, key=natural_sort_key)
        if not files:
            sys.exit(f"ERROR: no .md files found in '{args.input}'.")
        print(
            "\nWARNING: no --order specified. Using automatic (natural) sort.\n"
            "         Verify the sequence is correct before using the output.\n"
        )

    # ── Read and analyze each file ───────────────────────────────────────────
    print(f"Files to combine ({len(files)}):\n")
    total_kb = 0.0
    parsed = []
    warnings = []

    for f in files:
        path = os.path.join(args.input, f)
        size_kb = os.path.getsize(path) / 1024
        total_kb += size_kb

        raw = open(path, encoding="utf-8").read()

        # Normalize line endings
        text, had_crlf = normalize_line_endings(raw)
        if had_crlf:
            warnings.append(
                f"CRLF line endings detected in: {f}  (normalized to LF)"
            )

        # Strip YAML frontmatter
        frontmatter, body = strip_yaml_frontmatter(text)
        if frontmatter:
            warnings.append(
                f"YAML frontmatter found in: {f}  "
                f"(preserved as HTML comment inside its block)"
            )
        body = body.strip()

        # Extract metadata
        h1 = extract_h1(body)
        if not h1:
            warnings.append(
                f"No H1 heading found in: {f}  (filename used as fallback title)"
            )

        authors = extract_authors(h1, body)
        abbr    = make_abbreviation(h1)

        parsed.append({
            "filename":    f,
            "size_kb":     size_kb,
            "line_count":  len(body.splitlines()),
            "frontmatter": frontmatter,
            "body":        body,
            "h1":          h1,
            "authors":     authors,
            "abbr":        abbr,
            "title":       h1 or os.path.splitext(f)[0],
            "sections":    [],
        })

    # Resolve abbreviation conflicts before applying prefixes
    conflict_warnings = resolve_abbreviation_conflicts(parsed)
    warnings.extend(conflict_warnings)

    # Apply section prefixes and collect TOC sections
    for p in parsed:
        if not args.no_prefix:
            p["body"] = prefix_section_headings(p["body"], p["abbr"])
        p["sections"] = collect_h2_sections(p["body"])

    # Print file summary
    for p in parsed:
        print(f"  {p['filename']:<55}  {p['size_kb']:6.1f} KB  [{p['abbr']}]")
    print(f"\n  {'TOTAL':<55}  {total_kb:6.1f} KB")

    # Print warnings
    if warnings:
        print()
        for w in warnings:
            print(f"  ⚠  {w}")

    # ── Write output ─────────────────────────────────────────────────────────
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(args.output, "w", encoding="utf-8", newline="\n") as out:

        # 1. YAML frontmatter (Claude Projects optimized)
        out.write(build_yaml_frontmatter(parsed, now, args.no_prefix))
        out.write("\n")

        # 2. Table of contents
        if not args.no_toc:
            out.write(build_toc(parsed))
            out.write("\n\n")

        # 3. Book blocks
        for i, p in enumerate(parsed, 1):
            start_banner = make_book_banner(
                i, len(parsed), p["abbr"], p["title"],
                p["authors"], p["filename"], p["line_count"],
                p["size_kb"], "start"
            )
            end_banner = make_book_banner(
                i, len(parsed), p["abbr"], p["title"],
                p["authors"], p["filename"], p["line_count"],
                p["size_kb"], "end"
            )

            out.write(start_banner)

            # Preserve original YAML frontmatter as an HTML comment
            if p["frontmatter"]:
                out.write(
                    f"<!--\nORIGINAL FRONTMATTER ({p['filename']}):\n"
                    f"{p['frontmatter']}\n-->\n\n"
                )

            out.write(p["body"])
            out.write(end_banner)

    # ── Final summary ─────────────────────────────────────────────────────────
    final_size  = os.path.getsize(args.output) / 1024
    final_text  = open(args.output, encoding="utf-8").read()
    token_est   = estimate_tokens(final_text)

    print(f"\n{'─' * 60}")
    print(f"  Combined KB saved to : {args.output}")
    print(f"  Size                 : {final_size:.1f} KB")
    print(f"  Estimated tokens     : ~{token_est:,}")
    print(f"  Books combined       : {len(parsed)}")
    print(f"{'─' * 60}")
    print("\n  Abbreviations used:")
    for p in parsed:
        print(f"    [{p['abbr']}]  {p['title']}")
    print()


if __name__ == "__main__":
    main()
