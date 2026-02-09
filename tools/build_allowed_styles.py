import io
import json
import re
import sys
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "manual tagged files.zip"
PDF_PATH = ROOT / "StyleList-Alphabetical_1.1.pdf"
FALLBACK_TAGS = ROOT / "Tags.txt"
OUT_PATH = ROOT / "backend" / "config" / "allowed_styles.json"


def _styles_from_docx_bytes(data: bytes) -> set[str]:
    doc = Document(io.BytesIO(data))
    styles = set()
    for style in doc.styles:
        try:
            if style.type == WD_STYLE_TYPE.PARAGRAPH:
                styles.add(style.name)
        except Exception:
            # If style type lookup fails, still capture the name
            styles.add(style.name)
    return styles


def _styles_from_zip(zip_path: Path) -> set[str]:
    styles = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".docx"):
                continue
            data = zf.read(name)
            styles |= _styles_from_docx_bytes(data)
    return styles


def _styles_from_pdf(pdf_path: Path) -> set[str]:
    try:
        import PyPDF2  # type: ignore
    except Exception:
        return set()

    styles = set()
    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    except Exception:
        return set()

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines:
        # Split by columns or large spaces first
        parts = re.split(r"\s{2,}", line)
        for part in parts:
            token = part.strip().strip(",.;:")
            if not token:
                continue
            # Accept tokens with spaces if they are style-like (e.g., "H2 after H1")
            if re.match(r"^[A-Za-z0-9][A-Za-z0-9\- ]+$", token):
                styles.add(token)
    return styles


def _styles_from_fallback_tags(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {ln.strip() for ln in lines if ln.strip()}


def main() -> int:
    if not ZIP_PATH.exists():
        print(f"Missing manual tagged zip: {ZIP_PATH}", file=sys.stderr)
        return 1

    docx_styles = _styles_from_zip(ZIP_PATH)
    pdf_styles = _styles_from_pdf(PDF_PATH)

    # If PDF parsing fails or yields too few styles, use fallback list
    if len(pdf_styles) < 50:
        fallback = _styles_from_fallback_tags(FALLBACK_TAGS)
        pdf_styles |= fallback

    all_styles = {s.strip() for s in (docx_styles | pdf_styles) if s and s.strip()}
    output = sorted(all_styles)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(output)} styles to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
