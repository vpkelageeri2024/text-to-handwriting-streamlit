import streamlit as st
from PIL import Image
import io
import math
import zipfile
import numpy as np
from streamlit_drawable_canvas import st_canvas

# Import our modularized code
from renderer import render_handwriting_cached, FONT_URLS, create_background
from utils import extract_text_from_file
from payments import create_payment_link, check_payment_status, PAYMENTS_ENABLED

st.set_page_config(page_title="Text to Handwriting", layout="wide", page_icon="📝")

# --- UI/UX Enhancements ---
st.markdown("""
<style>
    /* Prevent dragging/saving watermarked images easily */
    img {
        pointer-events: none;
        user-select: none;
        -webkit-user-select: none;
    }
    
    /* Premium aesthetics for headers and buttons */
    h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding-bottom: 20px;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        transition: transform 0.2s ease-in-out, box-shadow 0.2s;
        font-weight: 600;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    /* Card-like containers for form */
    .css-1r6slb0, .css-1y4p8pa {
        padding: 2rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.03);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        backdrop-filter: blur(4px);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>Text to Handwriting ✨</h1>", unsafe_allow_html=True)

# Wrap settings and input in a form to prevent rendering on every keystroke
with st.form("handwriting_form"):
    st.header("1. Input Document or Text")
    col_upload, col_text = st.columns([1, 1])

    with col_upload:
        uploaded_file = st.file_uploader("Upload a document (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
            
    with col_text:
        manual_input = st.text_area("Or type/paste your text here...", height=150, placeholder="Write something nice here...")

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
        apply_texture = st.checkbox("Enable Ink Texture (Realistic Ballpoint Pen effect)", value=True, help="Only applies after payment to speed up previews.")
        mistake_prob = st.slider("Realistic Mistakes Probability", 0.0, 0.1, 0.0, 0.01, help="Simulates human errors by randomly miswriting and crossing out words.")
        max_pages = st.number_input("Max Pages (Safety Limit)", 1, 100, 50)

    # Note: st_canvas cannot be inside a form in Streamlit, so we move it outside.
    submitted = st.form_submit_button("🎨 Generate Handwriting", use_container_width=True)

st.header("3. Draw Diagram / Signature (Optional)")
st.info("Note: Drawings update immediately, but text updates require clicking 'Generate Handwriting'.")
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

# Compute final text
text_input = extract_text_from_file(uploaded_file)
if manual_input:
    text_input = (text_input + "\n" + manual_input) if text_input else manual_input

is_canvas_empty = canvas_result.image_data is None or not np.any(canvas_result.image_data)

if not text_input.strip() and is_canvas_empty:
    st.info("Start typing, uploading a file, or drawing, then click Generate!")
elif submitted or 'generated_images' in st.session_state:
    with st.spinner("Generating Live Preview..."):
        # Setup arguments
        custom_font_bytes = custom_font_file.getvalue() if custom_font_file else None
        custom_bg_bytes = custom_bg_file.getvalue() if custom_bg_file else None
        page_dims = page_size_options[page_size_choice]
        
        # Payment verification hash
        import hashlib
        state_str = text_input + str(font_size) + str(paper_style) + str(messiness) + str(margins) + (str(canvas_result.json_data) if not is_canvas_empty else "") + str(mistake_prob)
        current_state_id = hashlib.md5(state_str.encode()).hexdigest()
        is_paid = st.session_state.get('paid_state_id') == current_state_id
        
        images, last_y = render_handwriting_cached(
            text=text_input, 
            font_size=font_size, 
            ink_color=ink_color, 
            paper_style=paper_style, 
            custom_bg=custom_bg_bytes,
            messiness=messiness, 
            margins=margins, 
            page_size=page_dims, 
            line_spacing_factor=line_spacing_factor,
            apply_texture=apply_texture,
            is_paid=is_paid,
            mistake_prob=mistake_prob,
            font_choice=font_choice,
            custom_font_bytes=custom_font_bytes,
            max_pages=max_pages
        )
        
        # Append diagram if drawn
        if not is_canvas_empty:
            diagram = Image.fromarray(canvas_result.image_data).convert("RGBA")
            width, height = page_dims
            if last_y + 200 > height - margins[1]:
                diagram_page = create_background(paper_style, width, height, custom_bg_bytes, int(font_size * line_spacing_factor), margins[0], font_size, is_paid)
                diagram_page.paste(diagram, (margins[2], margins[0]), diagram)
                images.append(diagram_page.convert("RGB"))
            else:
                last_page = images[-1].convert("RGBA")
                last_page.paste(diagram, (margins[2], int(last_y) + 20), diagram)
                images[-1] = last_page.convert("RGB")
        
        st.session_state['generated_images'] = images

if 'generated_images' in st.session_state and (text_input.strip() or not is_canvas_empty):
    images = st.session_state['generated_images']
    num_pages = len(images)
    st.success(f"Successfully generated {num_pages} pages!")
    
    cols = st.columns(min(num_pages, 3) if num_pages > 0 else 1)
    for i, img in enumerate(images):
        with cols[i % 3]:
            caption_text = f"Page {i+1} (Unlocked)" if is_paid else f"Page {i+1} (Watermarked Preview)"
            st.image(img, caption=caption_text, use_container_width=True)
            
    st.markdown("---")
    
    if not PAYMENTS_ENABLED:
        st.warning("⚠️ Payments are currently disabled. You can only view the watermarked preview.")
    else:
        price_per_page = 5 if num_pages <= 10 else 2
        total_price_inr = num_pages * price_per_page
        
        if is_paid:
            st.success("✅ Payment verified for these pages! You can now download them.")
            dl_col1, dl_col2 = st.columns(2)
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for i, img in enumerate(images):
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    zf.writestr(f"page_{i+1}.png", img_byte_arr.getvalue())
                    
            with dl_col1:
                st.download_button("Download All as ZIP", data=zip_buffer.getvalue(), file_name="handwritten_notes.zip", mime="application/zip", use_container_width=True)
                
            if images:
                pdf_buffer = io.BytesIO()
                images[0].save(pdf_buffer, format="PDF", save_all=True, append_images=images[1:], resolution=100.0)
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
                        if link_id:
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
