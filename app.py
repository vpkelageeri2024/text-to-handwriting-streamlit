import streamlit as st
from PIL import Image
import io
import math
import zipfile
import numpy as np
from streamlit_drawable_canvas import st_canvas

# Import our modularized code
from renderer import render_handwriting_cached, FONT_URLS, create_background, apply_sketch_effect
from utils import extract_text_from_file
from payments import create_credit_payment_link, verify_payment_link, PAYMENTS_ENABLED
from supabase_client import SupabaseAuthClient, SupabaseWalletClient

st.set_page_config(page_title="Text to Handwriting", layout="wide", page_icon="📝")

# Initialize Supabase Clients
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
except Exception:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""

use_mock = not SUPABASE_URL or not SUPABASE_KEY

auth_client = SupabaseAuthClient(SUPABASE_URL, SUPABASE_KEY, use_mock=use_mock)
wallet_client = SupabaseWalletClient(SUPABASE_URL, SUPABASE_KEY, use_mock=use_mock)

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- User Account and Credit Wallet Sidebar ---
with st.sidebar:
    st.markdown("## 👤 User Account")
    
    if st.session_state['user'] is None:
        tab_login, tab_signup = st.tabs(["🔑 Login", "📝 Sign Up"])
        
        with tab_login:
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Log In", key="login_btn", use_container_width=True):
                res = auth_client.sign_in(login_email, login_password)
                if res['success']:
                    st.session_state['user'] = res['session']['user']
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error(f"Error: {res['error']}")
                    
        with tab_signup:
            signup_email = st.text_input("Email", key="signup_email")
            signup_password = st.text_input("Password", type="password", key="signup_password")
            if st.button("Sign Up", key="signup_btn", use_container_width=True):
                if len(signup_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    res = auth_client.sign_up(signup_email, signup_password)
                    if res['success']:
                        st.success("Account created! Please log in.")
                    else:
                        st.error(f"Error: {res['error']}")
    else:
        user = st.session_state['user']
        st.write(f"Logged in as: **{user['email']}**")
        
        # Get and display wallet balance
        balance = wallet_client.get_balance(user['id'])
        st.metric(label="Wallet Balance", value=f"{balance} Credits")
        
        # Log Out
        if st.button("Log Out", key="logout_btn", use_container_width=True):
            auth_client.sign_out()
            st.session_state['user'] = None
            # Clear generation state
            st.session_state.pop('generated_images', None)
            st.session_state.pop('generated_is_paid', None)
            st.success("Logged out successfully!")
            st.rerun()
            
        st.markdown("---")
        st.markdown("### 💳 Buy Credits")
        
        credit_packages = {
            "10 Credits (₹50)": (5000, 10),
            "50 Credits (₹200)": (20000, 50),
            "100 Credits (₹350)": (35000, 100)
        }
        
        selected_package = st.selectbox("Choose Package", list(credit_packages.keys()))
        amount_paise, package_credits = credit_packages[selected_package]
        
        if st.button("Generate Payment Link", key="buy_credits_btn", use_container_width=True):
            with st.spinner("Creating payment link..."):
                try:
                    link_id, link_url = create_credit_payment_link(amount_paise, package_credits, user['email'])
                    if link_id and link_url:
                        st.session_state['payment_link_id'] = link_id
                        st.session_state['payment_link_url'] = link_url
                        st.session_state['payment_package_credits'] = package_credits
                        st.success("Payment link generated!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error creating payment link: {str(e)}")
        
        if st.session_state.get('payment_link_url'):
            st.markdown(f"[👉 Click here to pay]({st.session_state['payment_link_url']})")
            
            if use_mock:
                if st.button("💳 [Mock] Simulate Payment Success", key="mock_pay_success_btn", use_container_width=True):
                    from payments import simulate_payment_success
                    simulate_payment_success(st.session_state['payment_link_id'])
                    st.success("Mock payment simulated successfully!")
            
            if st.button("Verify Payment", key="verify_pay_btn", type="primary", use_container_width=True):
                with st.spinner("Checking payment status..."):
                    if verify_payment_link(st.session_state['payment_link_id']):
                        credits_to_add = st.session_state['payment_package_credits']
                        wallet_client.add_credits(user['id'], credits_to_add, st.session_state['payment_link_id'])
                        st.success(f"Successfully added {credits_to_add} credits!")
                        st.session_state['payment_link_id'] = None
                        st.session_state['payment_link_url'] = None
                        st.session_state['payment_package_credits'] = None
                        st.rerun()
                    else:
                        st.error("Payment not completed yet.")

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
    
    /* Highlighted Generate Handwriting Button */
    [data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(45deg, #ff007f, #ff6b6b, #ff8e53, #ff007f);
        background-size: 300% auto;
        color: white !important;
        border: none;
        border-radius: 12px;
        font-size: 1.2rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.5);
        transition: all 0.3s ease-in-out;
        animation: gradient-shift 4s ease infinite, pulse-glow 2s infinite;
    }

    [data-testid="stFormSubmitButton"] > button:hover {
        background-position: right center;
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 8px 25px rgba(255, 107, 107, 0.8);
    }

    @keyframes gradient-shift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    @keyframes pulse-glow {
        0% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7); }
        70% { box-shadow: 0 0 0 15px rgba(255, 107, 107, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0); }
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

st.header("1. Input Document or Text")
col_upload, col_text = st.columns([1, 1])

with col_upload:
    uploaded_file = st.file_uploader("Upload a document (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
        
with col_text:
    manual_input = st.text_area("Or type/paste your text here...", height=150, placeholder="Write something nice here...")

st.header("2. Settings & Customizations (Chat Setup)")

if 'wizard_step' not in st.session_state:
    st.session_state.wizard_step = 0
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Hi! I'll help you configure your handwriting style. First, please select a **Handwriting Font**."}
    ]
    st.session_state.wizard_selections = {
        "font": "Homemade Apple",
        "paper": "Blank",
        "ink_color": "#000f55",
        "messiness": "Perfect"
    }

for i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        if msg["content"].startswith("#") and len(msg["content"]) == 7:
            st.markdown(f"<div style='width:30px;height:30px;border-radius:50%;background-color:{msg['content']};border:1px solid #ddd;'></div>", unsafe_allow_html=True)
        else:
            st.write(msg["content"])

if st.session_state.wizard_step == 0:
    with st.chat_message("assistant"):
        font_choice_sel = st.selectbox("Options:", list(FONT_URLS.keys()), key="wizard_font")
        if st.button("Select Font"):
            st.session_state.wizard_selections["font"] = font_choice_sel
            st.session_state.chat_history.append({"role": "user", "content": font_choice_sel})
            st.session_state.chat_history.append({"role": "assistant", "content": "Great choice! Now, what **Paper Style** do you prefer?"})
            st.session_state.wizard_step = 1
            st.rerun()

elif st.session_state.wizard_step == 1:
    with st.chat_message("assistant"):
        paper_choice_sel = st.selectbox("Options:", ["Blank", "Ruled", "College Ruled", "Dot Grid", "Yellow Legal", "Graph", "Parchment"], key="wizard_paper")
        if st.button("Select Paper"):
            st.session_state.wizard_selections["paper"] = paper_choice_sel
            st.session_state.chat_history.append({"role": "user", "content": paper_choice_sel})
            st.session_state.chat_history.append({"role": "assistant", "content": "Awesome! How about the **Ink Color**?"})
            st.session_state.wizard_step = 2
            st.rerun()

elif st.session_state.wizard_step == 2:
    with st.chat_message("assistant"):
        ink_color_choice_sel = st.color_picker("Options:", value="#000f55", key="wizard_color")
        if st.button("Select Color"):
            st.session_state.wizard_selections["ink_color"] = ink_color_choice_sel
            st.session_state.chat_history.append({"role": "user", "content": ink_color_choice_sel})
            st.session_state.chat_history.append({"role": "assistant", "content": "Nice color! Finally, how **Messy** should the handwriting be?"})
            st.session_state.wizard_step = 3
            st.rerun()

elif st.session_state.wizard_step == 3:
    with st.chat_message("assistant"):
        messy_choice_sel = st.selectbox("Options:", ["Perfect", "Slight Wobble", "Messy Wobble"], key="wizard_messy")
        if st.button("Select Messiness"):
            st.session_state.wizard_selections["messiness"] = messy_choice_sel
            st.session_state.chat_history.append({"role": "user", "content": messy_choice_sel})
            st.session_state.chat_history.append({"role": "assistant", "content": "All set! You can optionally draw a diagram below, and then click **Generate Handwriting**."})
            st.session_state.wizard_step = 4
            st.rerun()

elif st.session_state.wizard_step == 4:
    if st.button("Start Over (Reset Settings)"):
        del st.session_state.wizard_step
        st.rerun()

# Apply the wizard selections and set defaults for advanced options
font_choice = st.session_state.wizard_selections["font"]
paper_style = st.session_state.wizard_selections["paper"]
ink_color = st.session_state.wizard_selections["ink_color"]
messiness = st.session_state.wizard_selections["messiness"]

# Advanced Defaults
custom_font_file = None
custom_bg_file = None
font_size = 30
page_size_options = {
    "A4 (800x1131)": (800, 1131),
    "US Letter (850x1100)": (850, 1100),
    "A5 (565x800)": (565, 800)
}
page_size_choice = "A4 (800x1131)"
line_spacing_factor = 1.5
margins = (100, 100, 50, 50)
apply_texture = True
mistake_prob = 0.0
max_pages = 50

# --- Instant Auto-Preview Thumbnail ---
if st.session_state.wizard_step >= 1:
    preview_text = "The quick brown fox jumps over the lazy dog. This is a live preview of your selected handwriting style."
    with st.container():
        st.markdown("#### ✨ Live Style Preview")
        try:
            preview_imgs, _ = render_handwriting_cached(
                text=preview_text,
                font_size=font_size,
                ink_color=ink_color,
                paper_style=paper_style,
                custom_bg=None,
                messiness=messiness,
                margins=margins,
                page_size=(400, 280),
                line_spacing_factor=line_spacing_factor,
                apply_texture=False,
                is_paid=True,
                mistake_prob=0.0,
                font_choice=font_choice,
                custom_font_bytes=None,
                max_pages=1,
                is_preview=True
            )
            if preview_imgs:
                st.image(preview_imgs[0], caption="Preview updates as you change settings", use_container_width=True)
        except Exception:
            st.caption("Preview will appear after selecting a font.")

with st.form("generate_form"):
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

uploaded_diagram_file = st.file_uploader("Or upload a diagram/signature image", type=["png", "jpg", "jpeg"], key="uploaded_diagram")

st.markdown("---")
st.header("4. Live Preview")

# Compute final text
text_input = extract_text_from_file(uploaded_file)
if manual_input:
    text_input = (text_input + "\n" + manual_input) if text_input else manual_input

is_canvas_empty = canvas_result.image_data is None or not np.any(canvas_result.image_data)

if not text_input.strip() and is_canvas_empty and uploaded_diagram_file is None:
    st.info("Start typing, uploading a file, or drawing, then click Generate!")
elif submitted or 'generated_images' in st.session_state:
    if submitted:
        st.session_state.pop('generated_images', None)
        st.session_state.pop('generated_is_paid', None)
        
        if st.session_state['user'] is None:
            st.error("🔒 Please log in or sign up in the sidebar to generate handwriting documents.")
        else:
            user_id = st.session_state['user']['id']
            balance = wallet_client.get_balance(user_id)
            if balance <= 0:
                st.error("⚠️ Insufficient credits. Your wallet balance is 0. Please buy credits in the sidebar.")
            else:
                    deducted = wallet_client.deduct_credits(user_id, 1)
                    if deducted:
                        try:
                            custom_font_bytes = custom_font_file.getvalue() if custom_font_file else None
                            custom_bg_bytes = custom_bg_file.getvalue() if custom_bg_file else None
                            page_dims = page_size_options[page_size_choice]
                            
                            is_paid = True
                            
                            import uuid
                            cache_buster = str(uuid.uuid4())
                            
                            progress_bar = st.progress(0, text="🖊️ Rendering handwriting...")
                            progress_bar.progress(5, text="🖊️ Loading fonts...")
                            
                            progress_bar.progress(15, text="🖊️ Generating pages...")
                            
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
                                max_pages=max_pages,
                                cache_buster=cache_buster
                            )
                            
                            progress_bar.progress(70, text=f"📄 Generated {len(images)} pages. Processing diagrams...")
                            
                            width, height = page_dims
                            
                            if not is_canvas_empty:
                                diagram = Image.fromarray(canvas_result.image_data).convert("RGBA")
                                diagram = apply_sketch_effect(diagram)
                                if not images or last_y + 200 > height - margins[1]:
                                    diagram_page = create_background(paper_style, width, height, custom_bg_bytes, int(font_size * line_spacing_factor), margins[0], font_size, is_paid)
                                    diagram_page.paste(diagram, (margins[2], margins[0]), diagram)
                                    images.append(diagram_page.convert("RGB"))
                                    last_y = margins[0] + 200
                                else:
                                    last_page = images[-1].convert("RGBA")
                                    last_page.paste(diagram, (margins[2], int(last_y) + 20), diagram)
                                    images[-1] = last_page.convert("RGB")
                                    last_y = last_y + 220
                                    
                            if uploaded_diagram_file is not None:
                                uploaded_diagram_img = Image.open(uploaded_diagram_file).convert("RGBA")
                                
                                # Scale size to fit printable width
                                max_w = width - margins[2] - margins[3]
                                if uploaded_diagram_img.width > max_w:
                                    aspect = uploaded_diagram_img.height / uploaded_diagram_img.width
                                    uploaded_diagram_img = uploaded_diagram_img.resize((max_w, int(max_w * aspect)))
                                    
                                # Make sure height is not too extreme
                                if uploaded_diagram_img.height > 300:
                                    aspect = uploaded_diagram_img.width / uploaded_diagram_img.height
                                    uploaded_diagram_img = uploaded_diagram_img.resize((int(300 * aspect), 300))
                                    
                                uploaded_diagram_img = apply_sketch_effect(uploaded_diagram_img)
                                
                                diag_h = uploaded_diagram_img.height
                                if not images or last_y + diag_h > height - margins[1]:
                                    diagram_page = create_background(paper_style, width, height, custom_bg_bytes, int(font_size * line_spacing_factor), margins[0], font_size, is_paid)
                                    diagram_page.paste(uploaded_diagram_img, (margins[2], margins[0]), uploaded_diagram_img)
                                    images.append(diagram_page.convert("RGB"))
                                    last_y = margins[0] + diag_h
                                else:
                                    last_page = images[-1].convert("RGBA")
                                    last_page.paste(uploaded_diagram_img, (margins[2], int(last_y) + 20), uploaded_diagram_img)
                                    images[-1] = last_page.convert("RGB")
                                    last_y = last_y + diag_h + 20
                            
                            progress_bar.progress(95, text="📦 Finalizing output...")
                            
                            st.session_state['generated_images'] = images
                            st.session_state['generated_is_paid'] = True
                            
                            progress_bar.progress(100, text="✅ Done!")
                            st.success("Generated! 1 credit deducted from your wallet.")
                            st.rerun()
                        except Exception as e:
                            import uuid
                            refund_id = f"refund_{uuid.uuid4().hex}"
                            wallet_client.add_credits(user_id, 1, refund_id)
                            st.error(f"Error during rendering: {str(e)}. 1 credit was refunded.")
                    else:
                        st.error("Error deducting credits.")

if 'generated_images' in st.session_state and (text_input.strip() or not is_canvas_empty or uploaded_diagram_file is not None):
    images = st.session_state['generated_images']
    num_pages = len(images)
    st.success(f"Successfully generated {num_pages} pages!")
    
    cols = st.columns(min(num_pages, 3) if num_pages > 0 else 1)
    for i, img in enumerate(images):
        with cols[i % 3]:
            st.image(img, caption=f"Page {i+1}", use_container_width=True)
            
    st.markdown("---")
    
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
