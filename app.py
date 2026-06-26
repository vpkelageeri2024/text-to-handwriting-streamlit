import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import urllib.request
import os
import io
import math
import random
import zipfile
import numpy as np
import docx
import pypdf
import razorpay
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="Text to Handwriting", layout="wide", page_icon="📝")

# Disable right click and dragging on preview images
st.markdown("""
<style>
    img {
        pointer-events: none;
        user-select: none;
        -webkit-user-select: none;
    }
</style>
""", unsafe_allow_html=True)

# --- RAZORPAY SETUP ---
try:
    RAZORPAY_KEY_ID = st.secrets.get("RAZORPAY_KEY_ID", "rzp_test_YOUR_KEY_ID_HERE")
    RAZORPAY_KEY_SECRET = st.secrets.get("RAZORPAY_KEY_SECRET", "YOUR_KEY_SECRET_HERE")
except Exception:
    RAZORPAY_KEY_ID = "rzp_test_YOUR_KEY_ID_HERE"
    RAZORPAY_KEY_SECRET = "YOUR_KEY_SECRET_HERE"

def create_payment_link(amount_paise, description):
    try:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        payment_data = {
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "customer": {"name": "User", "email": "user@example.com"},
            "notify": {"email": False, "sms": False},
            "reminder_enable": False
        }
        payment_link = rzp_client.payment_link.create(payment_data)
        return payment_link['id'], payment_link['short_url']
    except Exception as e:
        st.error("Razorpay Error: Please verify your API keys.")
        return None, None

def check_payment_status(link_id):
    try:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        link = rzp_client.payment_link.fetch(link_id)
        return link.get('status') == 'paid'
    except Exception:
        return False

# --- UTILS FOR FONTS ---
FONT_URLS = {
    # Latin / English
    "Homemade Apple": "https://github.com/google/fonts/raw/main/apache/homemadeapple/HomemadeApple-Regular.ttf",
    "Caveat (Latin/Cyrillic)": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Indie Flower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf",
    "Patrick Hand": "https://github.com/google/fonts/raw/main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "Dancing Script": "https://github.com/google/fonts/raw/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
    "Amatic SC": "https://github.com/google/fonts/raw/main/ofl/amaticsc/AmaticSC-Regular.ttf",
    "Shadows Into Light": "https://github.com/google/fonts/raw/main/ofl/shadowsintolight/ShadowsIntoLight-Regular.ttf",
    "Architects Daughter": "https://github.com/google/fonts/raw/main/ofl/architectsdaughter/ArchitectsDaughter-Regular.ttf",
    "Pacifico": "https://github.com/google/fonts/raw/main/ofl/pacifico/Pacifico-Regular.ttf",
    
    # Multilingual & International
    "Kalam (Latin/Devanagari)": "https://github.com/google/fonts/raw/main/ofl/kalam/Kalam-Regular.ttf",
    "Tillana (Devanagari/Hindi)": "https://github.com/google/fonts/raw/main/ofl/tillana/Tillana-Regular.ttf",
    "Yatra One (Devanagari/Hindi)": "https://github.com/google/fonts/raw/main/ofl/yatraone/YatraOne-Regular.ttf",
    "Aref Ruqaa (Arabic)": "https://github.com/google/fonts/raw/main/ofl/arefruqaa/ArefRuqaa-Regular.ttf",
    "Nanum Pen Script (Korean)": "https://github.com/google/fonts/raw/main/ofl/nanumpenscript/NanumPenScript-Regular.ttf",
    "Zhi Mang Xing (Chinese)": "https://github.com/google/fonts/raw/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf",
    "Yuji Boku (Japanese)": "https://github.com/google/fonts/raw/main/ofl/yujiboku/YujiBoku-Regular.ttf",
    "Neucha (Cyrillic/Russian)": "https://github.com/google/fonts/raw/main/ofl/neucha/Neucha.ttf",
    "Bad Script (Cyrillic/Russian)": "https://github.com/google/fonts/raw/main/ofl/badscript/BadScript-Regular.ttf",
    
    # Indian Languages
    "Kavivanar (Tamil)": "https://github.com/google/fonts/raw/main/ofl/kavivanar/Kavivanar-Regular.ttf",
    "Chilanka (Malayalam)": "https://github.com/google/fonts/raw/main/ofl/chilanka/Chilanka-Regular.ttf",
    "Galada (Bengali)": "https://github.com/google/fonts/raw/main/ofl/galada/Galada-Regular.ttf",
    "Peddana (Telugu)": "https://github.com/google/fonts/raw/main/ofl/peddana/Peddana-Regular.ttf",
    "Mogra (Gujarati)": "https://github.com/google/fonts/raw/main/ofl/mogra/Mogra-Regular.ttf",
    "Hubballi (Kannada)": "https://github.com/google/fonts/raw/main/ofl/hubballi/Hubballi-Regular.ttf"
}

@st.cache_resource
def load_font(font_name, size):
    os.makedirs("fonts", exist_ok=True)
    path = f"fonts/{font_name.replace(' ', '_')}.ttf"
    if not os.path.exists(path):
        url = FONT_URLS.get(font_name)
        if url:
            try:
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                st.error(f"Failed to download font '{font_name}': {e}")
                return ImageFont.load_default()
        else:
            return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        st.error(f"Failed to load font '{font_name}': {e}")
        return ImageFont.load_default()

def load_custom_font(font_bytes, size):
    try:
        return ImageFont.truetype(io.BytesIO(font_bytes), size)
    except Exception as e:
        st.error(f"Failed to load custom font: {e}")
        return ImageFont.load_default()

# --- UTILS FOR BACKGROUNDS ---
def create_background(style, width, height, custom_bg=None, line_spacing=40, margin_top=100, font_size=30):
    if custom_bg:
        try:
            img = Image.open(io.BytesIO(custom_bg)).convert("RGBA")
            return img.resize((width, height))
        except Exception:
            pass # Fallback to standard style if custom bg fails

    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    if style in ["Ruled", "College Ruled"]:
        offset = int((line_spacing - font_size) / 2)
        for y in range(margin_top, height + line_spacing, line_spacing):
            line_y = y - offset
            if 0 <= line_y < height:
                draw.line([(0, line_y), (width, line_y)], fill="#a6d4fa", width=2)
        if style == "College Ruled":
            draw.line([(80, 0), (80, height)], fill="#fca5a5", width=2)
            
    elif style == "Yellow Legal":
        img = Image.new("RGBA", (width, height), "#fef08a")
        draw = ImageDraw.Draw(img)
        offset = int((line_spacing - font_size) / 2)
        for y in range(margin_top, height + line_spacing, line_spacing):
            line_y = y - offset
            if 0 <= line_y < height:
                draw.line([(0, line_y), (width, line_y)], fill="#cbd5e1", width=2)
        draw.line([(100, 0), (100, height)], fill="#fca5a5", width=3)
        draw.line([(105, 0), (105, height)], fill="#fca5a5", width=3)
    elif style == "Dot Grid":
        for y in range(20, height, 20):
            for x in range(20, width, 20):
                draw.ellipse([x-1, y-1, x+1, y+1], fill="#cbd5e1")
    elif style == "Graph":
        for y in range(0, height, 20):
            draw.line([(0, y), (width, y)], fill="#e5e7eb", width=1)
        for x in range(0, width, 20):
            draw.line([(x, 0), (x, height)], fill="#e5e7eb", width=1)
    elif style == "Parchment":
        img = Image.new("RGBA", (width, height), "#fdf6e3")
    
    return img

def extract_text_from_file(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith('.txt'):
        return uploaded_file.getvalue().decode('utf-8', errors='ignore')
    elif name.endswith('.docx'):
        doc = docx.Document(uploaded_file)
        return '\n'.join([para.text for para in doc.paragraphs])
    elif name.endswith('.pdf'):
        reader = pypdf.PdfReader(uploaded_file)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return ""

def render_handwriting(text, font_obj, font_size, ink_color, paper_style, custom_bg, messiness, margins, page_size, line_spacing_factor, apply_texture):
    width, height = page_size
    margin_top, margin_bottom, margin_left, margin_right = margins
    
    # Strictly enforce left margins for papers with drawn margin lines
    if paper_style == "College Ruled":
        margin_left = max(margin_left, 85)
    elif paper_style == "Yellow Legal":
        margin_left = max(margin_left, 110)
        
    images = []
    lines = text.split('\n')
    line_spacing = int(font_size * line_spacing_factor)
    
    current_bg = create_background(paper_style, width, height, custom_bg, line_spacing, margin_top, font_size)
    text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_layer)
    
    x, y = margin_left, margin_top
    
    jitter_amp = 0
    if messiness == "Slight Wobble":
        jitter_amp = 2
    elif messiness == "Messy Wobble":
        jitter_amp = 5

    def add_page():
        nonlocal text_layer, current_bg
        if apply_texture:
            arr = np.array(text_layer)
            alpha = arr[:,:,3]
            mask = alpha > 0
            if mask.any():
                noise = np.random.randint(150, 255, size=alpha.shape)
                arr[:,:,3] = np.where(mask, (alpha.astype(np.float32) * (noise / 255.0)).astype(np.uint8), alpha)
                text_layer = Image.fromarray(arr, mode="RGBA")
        
        out = Image.alpha_composite(current_bg.convert("RGBA"), text_layer)
        images.append(out.convert("RGB"))
        current_bg = create_background(paper_style, width, height, custom_bg, line_spacing, margin_top, font_size)
        text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        return draw

    for line in lines:
        words = line.split(' ')
        for word in words:
            word_w = draw.textlength(word + " ", font=font_obj)
            
            if word_w > (width - margin_left - margin_right):
                chars = list(word + " ")
                for char in chars:
                    char_w = draw.textlength(char, font=font_obj)
                    if x + char_w > width - margin_right:
                        x = margin_left
                        y += line_spacing
                        if y + font_size > height - margin_bottom:
                            add_page()
                            draw = ImageDraw.Draw(text_layer)
                            y = margin_top
                    dy = random.uniform(-jitter_amp, jitter_amp) if jitter_amp > 0 else 0
                    dx = random.uniform(-jitter_amp/2, jitter_amp/2) if jitter_amp > 0 else 0
                    draw.text((x + dx, y + dy), char, fill=ink_color, font=font_obj)
                    x += char_w
                continue

            if x + word_w > width - margin_right:
                x = margin_left
                y += line_spacing
                if y + font_size > height - margin_bottom:
                    add_page()
                    draw = ImageDraw.Draw(text_layer)
                    y = margin_top
            
            dy = random.uniform(-jitter_amp, jitter_amp) if jitter_amp > 0 else 0
            dx = random.uniform(-jitter_amp/2, jitter_amp/2) if jitter_amp > 0 else 0
            
            draw.text((x + dx, y + dy), word, fill=ink_color, font=font_obj)
            x += word_w
        
        x = margin_left
        y += line_spacing
        if y + font_size > height - margin_bottom:
            add_page()
            draw = ImageDraw.Draw(text_layer)
            y = margin_top

    # Handle the final page
    if apply_texture:
        arr = np.array(text_layer)
        alpha = arr[:,:,3]
        mask = alpha > 0
        if mask.any():
            noise = np.random.randint(150, 255, size=alpha.shape)
            arr[:,:,3] = np.where(mask, (alpha.astype(np.float32) * (noise / 255.0)).astype(np.uint8), alpha)
            text_layer = Image.fromarray(arr, mode="RGBA")
            
    out = Image.alpha_composite(current_bg.convert("RGBA"), text_layer)
    images.append(out.convert("RGB"))
    return images, y

# --- UI ---
st.markdown("<h1 style='text-align: center;'>Text to Handwriting ✨</h1>", unsafe_allow_html=True)

st.header("1. Input Document or Text")
col_upload, col_text = st.columns([1, 1])

text_input = ""
with col_upload:
    uploaded_file = st.file_uploader("Upload a document (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
    if uploaded_file is not None:
        text_input = extract_text_from_file(uploaded_file)
        
with col_text:
    manual_input = st.text_area("Or type/paste your text here...", height=150, value="Write something nice here..." if not text_input else "")
    if manual_input:
        if text_input:
            text_input += "\n" + manual_input
        else:
            text_input = manual_input

estimated_pages = math.ceil(len(text_input) / 1500) if text_input else 0
st.info(f"📄 Estimated Output Pages: ~{estimated_pages}")

st.header("2. Settings & Customizations")
tab_basic, tab_layout, tab_advanced = st.tabs(["🖌️ Basic", "📏 Layout", "⚙️ Advanced"])

with tab_basic:
    col1, col2 = st.columns(2)
    with col1:
        font_choice = st.selectbox("Handwriting Font", list(FONT_URLS.keys()))
        custom_font_file = st.file_uploader("Or upload custom font (.ttf, .otf)", type=["ttf", "otf"])
        font_size = st.number_input("Font Size", min_value=10, max_value=100, value=30, step=2)
        ink_color = st.color_picker("Ink Color", value="#000f55")
        
    with col2:
        paper_style = st.selectbox("Paper Style", ["Blank", "Ruled", "College Ruled", "Dot Grid", "Yellow Legal", "Graph", "Parchment"])
        custom_bg_file = st.file_uploader("Or upload custom paper background (.png, .jpg)", type=["png", "jpg", "jpeg"])
        messiness = st.selectbox("Humanizer (Messiness)", ["Perfect", "Slight Wobble", "Messy Wobble"])

with tab_layout:
    col1, col2 = st.columns(2)
    with col1:
        page_size_options = {
            "A4 (800x1131)": (800, 1131),
            "US Letter (850x1100)": (850, 1100),
            "A5 (565x800)": (565, 800)
        }
        page_size_choice = st.selectbox("Page Size", list(page_size_options.keys()))
        line_spacing_factor = st.slider("Line Spacing", 1.0, 3.0, 1.5, 0.1)
    with col2:
        st.write("Margins")
        m_top = st.number_input("Top", 0, 500, 100)
        m_bottom = st.number_input("Bottom", 0, 500, 100)
        m_left = st.number_input("Left", 0, 500, 50)
        m_right = st.number_input("Right", 0, 500, 50)
        margins = (m_top, m_bottom, m_left, m_right)

with tab_advanced:
    apply_texture = st.checkbox("Enable Ink Texture (Realistic Ballpoint Pen effect)", value=True)
    st.write("Texture applies a slightly transparent, noisy layer to the ink for a realistic pen feel.")

st.header("3. Draw Diagram / Signature (Optional)")
st.write("Draw something below, and it will be appended to the end of your notes!")
canvas_result = st_canvas(
    fill_color="rgba(255, 165, 0, 0.3)",
    stroke_width=2,
    stroke_color=ink_color,
    background_color="rgba(0, 0, 0, 0)",
    height=200,
    width=800,
    drawing_mode="freedraw",
    key="canvas",
)

st.markdown("---")
st.header("4. Live Preview")

is_canvas_empty = canvas_result.image_data is None or not np.any(canvas_result.image_data)

if not text_input.strip() and is_canvas_empty:
    st.info("Start typing, uploading a file, or drawing to see the live preview!")
else:
    with st.spinner("Generating Live Preview..."):
        # Prepare font
        if custom_font_file:
            font_obj = load_custom_font(custom_font_file.getvalue(), font_size)
        else:
            font_obj = load_font(font_choice, font_size)
            
        # Prepare background
        custom_bg_bytes = custom_bg_file.getvalue() if custom_bg_file else None
        
        page_dims = page_size_options[page_size_choice]
        
        images, last_y = render_handwriting(
            text=text_input, 
            font_obj=font_obj, 
            font_size=font_size, 
            ink_color=ink_color, 
            paper_style=paper_style, 
            custom_bg=custom_bg_bytes,
            messiness=messiness, 
            margins=margins, 
            page_size=page_dims, 
            line_spacing_factor=line_spacing_factor,
            apply_texture=apply_texture
        )
        
        # Append diagram if drawn
        if not is_canvas_empty:
            diagram = Image.fromarray(canvas_result.image_data).convert("RGBA")
            width, height = page_dims
            if last_y + 200 > height - margins[1]:
                # Does not fit, append as new page
                diagram_page = create_background(paper_style, width, height, custom_bg_bytes, int(font_size * line_spacing_factor), margins[0], font_size)
                diagram_page.paste(diagram, (margins[2], margins[0]), diagram)
                images.append(diagram_page.convert("RGB"))
            else:
                # Fits on the current page, append below text
                last_page = images[-1].convert("RGBA")
                last_page.paste(diagram, (margins[2], int(last_y) + 20), diagram)
                images[-1] = last_page.convert("RGB")
        
        st.session_state['generated_images'] = images

if 'generated_images' in st.session_state and (text_input.strip() or not is_canvas_empty):
    images = st.session_state['generated_images']
    num_pages = len(images)
    st.success(f"Successfully generated {num_pages} pages!")
    
    # Payment Logic Calculations
    price_per_page = 5 if num_pages <= 10 else 2
    total_price_inr = num_pages * price_per_page
    
    import hashlib
    state_str = text_input + str(font_size) + str(paper_style) + str(messiness) + str(margins) + str(num_pages)
    current_state_id = hashlib.md5(state_str.encode()).hexdigest()
    is_paid = st.session_state.get('paid_state_id') == current_state_id
    
    def apply_watermark(base_img):
        watermarked = base_img.copy().convert("RGBA")
        txt_layer = Image.new('RGBA', watermarked.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        width, height = watermarked.size
        
        try:
            watermark_font = load_font(font_choice, 80)
        except Exception:
            watermark_font = ImageFont.load_default()
            
        for y in range(150, height, 300):
            for x in range(20, width, 400):
                draw.text((x, y), "PREVIEW", fill=(255, 0, 0, 100), font=watermark_font)
        return Image.alpha_composite(watermarked, txt_layer).convert("RGB")
    
    # Display images
    cols = st.columns(min(num_pages, 3) if num_pages > 0 else 1)
    for i, img in enumerate(images):
        with cols[i % 3]:
            if is_paid:
                st.image(img, caption=f"Page {i+1} (Unlocked)", use_container_width=True)
            else:
                st.image(apply_watermark(img), caption=f"Page {i+1} (Watermarked Preview)", use_container_width=True)
            
    st.markdown("---")
    
    if is_paid:
        st.success("✅ Payment verified for these pages! You can now download them.")
        dl_col1, dl_col2 = st.columns(2)
        
        # ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, img in enumerate(images):
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                zf.writestr(f"page_{i+1}.png", img_byte_arr.getvalue())
                
        with dl_col1:
            st.download_button("Download All as ZIP", data=zip_buffer.getvalue(), file_name="handwritten_notes.zip", mime="application/zip", use_container_width=True)
            
        # PDF
        if images:
            pdf_buffer = io.BytesIO()
            images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:])
            with dl_col2:
                st.download_button("Download as PDF", data=pdf_buffer.getvalue(), file_name="handwritten_notes.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.write(f"### 📥 Download your High-Res Document for ₹{total_price_inr}")
        st.write(f"*{num_pages} pages at ₹{price_per_page} per page.*")
        
        pay_col1, pay_col2 = st.columns([1, 1])
        with pay_col1:
            if st.button("💳 Generate Secure Payment Link", use_container_width=True):
                with st.spinner("Connecting to Razorpay..."):
                    link_id, link_url = create_payment_link(total_price_inr * 100, f"{num_pages} pages of handwriting export")
                    st.session_state['current_payment_link_id'] = link_id
                    st.session_state['current_payment_link_url'] = link_url
                    
        if st.session_state.get('current_payment_link_url'):
            with pay_col2:
                st.link_button("👉 Step 1: Click here to Pay (Opens in new tab)", st.session_state['current_payment_link_url'], use_container_width=True)
                
                if st.button("👉 Step 2: I have completed the payment", type="primary", use_container_width=True):
                    with st.spinner("Verifying payment status..."):
                        if check_payment_status(st.session_state['current_payment_link_id']):
                            st.session_state['paid_state_id'] = current_state_id
                            st.rerun()
                        else:
                            st.error("Payment has not been completed yet. Please complete the payment and try again.")
