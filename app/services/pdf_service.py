import pymupdf


def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file."""

    text_parts = []

    with pymupdf.open(file_path) as pdf:
        for page in pdf:
            text_parts.append(page.get_text())

    return "\n".join(text_parts)