import pdfplumber


def extract_text(path: str) -> str:
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    if not parts:
        raise ValueError(f"No text extracted from: {path}")
    return "\n".join(parts)
