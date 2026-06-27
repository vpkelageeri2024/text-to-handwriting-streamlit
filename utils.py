import docx
import fitz  # PyMuPDF
import streamlit as st
from typing import Any

def extract_text_from_file(uploaded_file: Any) -> str:
    """Extracts text from various file formats (.txt, .docx, .pdf)."""
    if uploaded_file is None:
        return ""
        
    name = uploaded_file.name.lower()
    
    try:
        if name.endswith('.txt'):
            return uploaded_file.getvalue().decode('utf-8', errors='ignore')
            
        elif name.endswith('.docx'):
            doc = docx.Document(uploaded_file)
            return '\n'.join([para.text for para in doc.paragraphs])
            
        elif name.endswith('.pdf'):
            # PyMuPDF is much better at extracting tables, columns, and formatting
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                text = []
                for page in doc:
                    text.append(page.get_text("text"))
                return "\n".join(text)
            
    except Exception as e:
        st.error(f"Failed to extract text from {uploaded_file.name}. Error: {e}")
        return ""
        
    return ""
