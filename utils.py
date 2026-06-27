import docx
import pypdf
import streamlit as st

def extract_text_from_file(uploaded_file):
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
            reader = pypdf.PdfReader(uploaded_file)
            return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            
    except Exception as e:
        st.error(f"Failed to extract text from {uploaded_file.name}. Error: {e}")
        return ""
        
    return ""
