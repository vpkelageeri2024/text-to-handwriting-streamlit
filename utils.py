import docx
import fitz  # PyMuPDF
import streamlit as st
from typing import Any

def extract_formatted_text_from_pdf(uploaded_file: Any) -> str:
    """Reads PDF via PyMuPDF dict structure and returns formatted Markdown text with # and ** markup."""
    if uploaded_file is None:
        return ""
        
    try:
        # Open PDF
        uploaded_file.seek(0)
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            # 1. Collect all font sizes to determine body text font size
            sizes = []
            for page in doc:
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") == 0:  # text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if span.get("text", "").strip():
                                    sizes.append(round(span["size"], 1))
            
            # Use the most common font size as base size, default to 11.0 if empty
            if sizes:
                base_size = max(set(sizes), key=sizes.count)
            else:
                base_size = 11.0

            # 2. Extract and format text block-by-block, line-by-line, span-by-span
            document_text = []
            for page in doc:
                page_blocks = []
                for block in page.get_text("dict").get("blocks", []):
                    if block.get("type") == 0:  # text block
                        block_lines = []
                        for line in block.get("lines", []):
                            span_strs = []
                            is_header = False
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                if not text.strip():
                                    span_strs.append(text)
                                    continue
                                
                                # Check if header (size >= base_size * 1.2)
                                span_size = span.get("size", 0)
                                if span_size >= base_size * 1.2:
                                    is_header = True
                                
                                # Check if bold
                                font_name = span.get("font", "").lower()
                                flags = span.get("flags", 0)
                                is_bold = bool((flags & 16) or ("bold" in font_name) or ("black" in font_name) or ("heavy" in font_name))
                                
                                left_spaces = text[:len(text) - len(text.lstrip())]
                                right_spaces = text[len(text.rstrip()):]
                                clean_text = text.strip()
                                
                                if is_bold:
                                    span_strs.append(f"{left_spaces}**{clean_text}**{right_spaces}")
                                else:
                                    span_strs.append(text)
                            
                            line_str = "".join(span_strs)
                            if is_header and line_str.strip():
                                line_str = f"# {line_str.strip()}"
                            block_lines.append(line_str)
                            
                        if block_lines:
                            page_blocks.append("\n".join(block_lines))
                if page_blocks:
                    document_text.append("\n\n".join(page_blocks))
            return "\n\n".join(document_text)
            
    except Exception as e:
        st.error(f"Failed to extract formatted text from PDF. Error: {e}")
        return ""

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
            return extract_formatted_text_from_pdf(uploaded_file)
            
    except Exception as e:
        st.error(f"Failed to extract text from {uploaded_file.name}. Error: {e}")
        return ""
        
    return ""

