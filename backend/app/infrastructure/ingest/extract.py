import csv
import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".docx", ".pdf"}
MAX_EXTRACTED_CHARACTERS = 2_000_000


def _decode_text(raw: bytes) -> str:
    """Decode common UTF and Chinese text encodings without silently corrupting data."""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Text encoding is not supported; please save the file as UTF-8")


def _plain_text(path: Path) -> str:
    return _decode_text(path.read_bytes())


def _pdf(path: Path) -> str:
    text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
    if not text:
        raise ValueError(
            "PDF contains no selectable text. Scanned/image PDFs are not supported; "
            "export it as a searchable PDF, TXT, or Markdown file."
        )
    return text


def _docx(path: Path) -> str:
    """Extract OOXML text, including tables, headers, footers, and text boxes."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise ValueError("文件不是有效的 DOCX 文档")
            parts = ["word/document.xml"]
            parts.extend(
                sorted(
                    name
                    for name in names
                    if name.startswith("word/")
                    and name.endswith(".xml")
                    and Path(name).name.startswith(
                        ("header", "footer", "footnotes", "endnotes", "comments")
                    )
                )
            )
            xml_parts = [archive.read(name) for name in parts]
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError("DOCX 文件已损坏或格式不正确") from error

    lines: list[str] = []
    for raw in xml_parts:
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as error:
            raise ValueError("DOCX 内部 XML 无法解析") from error
        for paragraph in (node for node in root.iter() if node.tag.endswith("}p")):
            fragments: list[str] = []
            for node in paragraph.iter():
                local_name = node.tag.rsplit("}", 1)[-1]
                if local_name == "t" and node.text:
                    fragments.append(node.text)
                elif local_name == "tab":
                    fragments.append("\t")
                elif local_name in {"br", "cr"}:
                    fragments.append("\n")
            line = "".join(fragments).strip()
            if line:
                lines.append(line)
    return "\n".join(lines)


def _csv(path: Path) -> str:
    text = _decode_text(path.read_bytes())
    return "\n".join("\t".join(row) for row in csv.reader(io.StringIO(text)))


def extract_text(path: Path) -> str:
    """Extract searchable text with deterministic, non-OCR parsers."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")
    handlers = {
        ".txt": _plain_text,
        ".md": _plain_text,
        ".markdown": _plain_text,
        ".pdf": _pdf,
        ".docx": _docx,
        ".csv": _csv,
    }
    return handlers[suffix](path).replace("\x00", "").strip()[:MAX_EXTRACTED_CHARACTERS]
