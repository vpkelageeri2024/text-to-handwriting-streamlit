import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import urllib.request
import os
import io
import math
import random
import zipfile

st.set_page_config(page_title="Text to Handwriting", layout="wide", page_icon="📝")

# --- UTILS FOR FONTS ---
FONT_URLS = {
    "Homemade Apple": "https://github.com/google/fonts/raw/main/apache/homemadeapple/HomemadeApple-Regular.ttf",
    "Caveat": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Indie Flower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf",
    "Patrick Hand": "https://github.com/google/fonts/raw/main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "Dancing Script": "https://github.com/google/fonts/raw/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf"
}

@st.cache_resource
def load_font(font_name, size):
    os.makedirs("fonts", exist_ok=True)
    path = f"fonts/{font_name.replace(' ', '_')}.ttf"
    if not os.path.exists(path):
        url = FONT_URLS.get(font_name)
        if url:
            urllib.request.urlretrieve(url, path)
        else:
            return ImageFont.load_default()
    return ImageFont.truetype(path, size)

# --- UTILS FOR BACKGROUNDS ---
def create_background(style, width, height):
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    if style == "Ruled":
        for y in range(100, height, 40):
            draw.line([(0, y), (width, y)], fill="#a6d4fa", width=2)
    elif style == "Yellow Legal":
        img = Image.new("RGBA", (width, height), "#fef08a")
        draw = ImageDraw.Draw(img)
        for y in range(100, height, 40):
            draw.line([(0, y), (width, y)], fill="#cbd5e1", width=2)
        # Margins
        draw.line([(100, 0), (100, height)], fill="#fca5a5", width=3)
        draw.line([(105, 0), (105, height)], fill="#fca5a5", width=3)
    elif style == "Graph":
        for y in range(0, height, 20):
            draw.line([(0, y), (width, y)], fill="#e5e7eb", width=1)
        for x in range(0, width, 20):
            draw.line([(x, 0), (x, height)], fill="#e5e7eb", width=1)
    elif style == "Parchment":
        img = Image.new("RGBA", (width, height), "#fdf6e3")
    
    return img

def render_handwriting(text, font_name, font_size, ink_color, paper_style, messiness):
    width, height = 800, 1131 # A4 ratio scaled
    margin_x, margin_y = 50, 100
    if paper_style == "Yellow Legal":
        margin_x = 120
        
    font = load_font(font_name, font_size)
    images = []
    
    lines = text.split('\n')
    
    current_img = create_background(paper_style, width, height)
    draw = ImageDraw.Draw(current_img)
    
    x, y = margin_x, margin_y
    line_spacing = int(font_size * 1.5)
    
    # Messiness factor
    jitter_amp = 0
    if messiness == "Slight Wobble":
        jitter_amp = 2
    elif messiness == "Messy Wobble":
        jitter_amp = 5

    def add_page():
        images.append(current_img.convert("RGB"))
        return create_background(paper_style, width, height)

    for line in lines:
        words = line.split(' ')
        for word in words:
            # Check bounding box
            # get length of word with a trailing space
            word_w = draw.textlength(word + " ", font=font)
            
            if x + word_w > width - 50:
                x = margin_x
                y += line_spacing
                if y > height - 100:
                    current_img = add_page()
                    draw = ImageDraw.Draw(current_img)
                    y = margin_y
            
            dy = random.uniform(-jitter_amp, jitter_amp)
            
            draw.text((x, y + dy), word, fill=ink_color, font=font)
            x += word_w
        
        # Newline
        x = margin_x
        y += line_spacing
        if y > height - 100:
            current_img = add_page()
            draw = ImageDraw.Draw(current_img)
            y = margin_y
            
    images.append(current_img.convert("RGB"))
    return images

# --- UI ---
st.title("📝 Text to Handwriting (Python Engine)")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Customizations")
    font_choice = st.selectbox("Handwriting Font", list(FONT_URLS.keys()))
    font_size = st.number_input("Font Size", min_value=10, max_value=100, value=30, step=2)
    ink_color = st.color_picker("Ink Color", value="#000f55")
    paper_style = st.selectbox("Paper Style", ["Blank", "Ruled", "Yellow Legal", "Graph", "Parchment"])
    messiness = st.selectbox("Humanizer (Messiness)", ["Perfect", "Slight Wobble", "Messy Wobble"])

with col2:
    st.header("Input Text")
    text_input = st.text_area("Type or paste your text here...", height=200, value="Write something nice here...")
    
    if st.button("Generate Image", use_container_width=True):
        if not text_input.strip():
            st.warning("Please enter some text.")
        else:
            with st.spinner("Generating handwriting..."):
                images = render_handwriting(text_input, font_choice, font_size, ink_color, paper_style, messiness)
                st.session_state['generated_images'] = images

if 'generated_images' in st.session_state:
    images = st.session_state['generated_images']
    st.markdown(f"**Generated Pages: {len(images)}**")
    
    # Display images
    cols = st.columns(min(len(images), 3))
    for i, img in enumerate(images):
        with cols[i % 3]:
            st.image(img, caption=f"Page {i+1}", use_container_width=True)
            
    # Download actions
    st.markdown("---")
    dl_col1, dl_col2 = st.columns(2)
    
    # ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for i, img in enumerate(images):
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            zf.writestr(f"page_{i+1}.png", img_byte_arr.getvalue())
            
    with dl_col1:
        st.download_button(
            label="Download All as ZIP",
            data=zip_buffer.getvalue(),
            file_name="handwritten_notes.zip",
            mime="application/zip",
            use_container_width=True
        )
        
    # PDF
    pdf_buffer = io.BytesIO()
    images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:])
    with dl_col2:
        st.download_button(
            label="Download as PDF",
            data=pdf_buffer.getvalue(),
            file_name="handwritten_notes.pdf",
            mime="application/pdf",
            use_container_width=True
        )
