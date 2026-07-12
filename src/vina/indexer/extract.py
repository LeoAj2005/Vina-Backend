from pathlib import Path
import json
from pypdf import PdfReader
from docx import Document

def extract_text(filepath: str) -> str:
    """Extracts text content from a file based on its extension."""
    path = Path(filepath)
    ext = path.suffix.lower()
    
    try:
        if ext == ".pdf":
            reader = PdfReader(str(path))
            # Handle encrypted PDFs (try empty password, which works for owner-restricted PDFs)
            if reader.is_encrypted:
                reader.decrypt("")
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            doc = Document(str(path))
            return "\n".join(para.text for para in doc.paragraphs)
        elif ext == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".json":
            return json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2)
    except Exception as e:
        print(f"[Vina] Warning: Failed to extract {filepath}: {e}")
        return ""
        
    return ""