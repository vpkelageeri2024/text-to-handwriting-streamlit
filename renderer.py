import os
import io
import math
import random
import re
import urllib.request
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

FONT_URLS = {
    "Homemade Apple": "https://github.com/google/fonts/raw/main/apache/homemadeapple/HomemadeApple-Regular.ttf",
    "Caveat (Latin/Cyrillic)": "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf",
    "Indie Flower": "https://github.com/google/fonts/raw/main/ofl/indieflower/IndieFlower-Regular.ttf",
    "Patrick Hand": "https://github.com/google/fonts/raw/main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "Dancing Script": "https://github.com/google/fonts/raw/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
    "Amatic SC": "https://github.com/google/fonts/raw/main/ofl/amaticsc/AmaticSC-Regular.ttf",
    "Shadows Into Light": "https://github.com/google/fonts/raw/main/ofl/shadowsintolight/ShadowsIntoLight-Regular.ttf",
    "Architects Daughter": "https://github.com/google/fonts/raw/main/ofl/architectsdaughter/ArchitectsDaughter-Regular.ttf",
    "Pacifico": "https://github.com/google/fonts/raw/main/ofl/pacifico/Pacifico-Regular.ttf",
    
    "Kalam (Latin/Devanagari)": "https://github.com/google/fonts/raw/main/ofl/kalam/Kalam-Regular.ttf",
    "Tillana (Devanagari/Hindi)": "https://github.com/google/fonts/raw/main/ofl/tillana/Tillana-Regular.ttf",
    "Yatra One (Devanagari/Hindi)": "https://github.com/google/fonts/raw/main/ofl/yatraone/YatraOne-Regular.ttf",
    "Aref Ruqaa (Arabic)": "https://github.com/google/fonts/raw/main/ofl/arefruqaa/ArefRuqaa-Regular.ttf",
    "Nanum Pen Script (Korean)": "https://github.com/google/fonts/raw/main/ofl/nanumpenscript/NanumPenScript-Regular.ttf",
    "Zhi Mang Xing (Chinese)": "https://github.com/google/fonts/raw/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf",
    "Yuji Boku (Japanese)": "https://github.com/google/fonts/raw/main/ofl/yujiboku/YujiBoku-Regular.ttf",
    "Neucha (Cyrillic/Russian)": "https://github.com/google/fonts/raw/main/ofl/neucha/Neucha.ttf",
    "Bad Script (Cyrillic/Russian)": "https://github.com/google/fonts/raw/main/ofl/badscript/BadScript-Regular.ttf",
    
    "Kavivanar (Tamil)": "https://github.com/google/fonts/raw/main/ofl/kavivanar/Kavivanar-Regular.ttf",
    "Chilanka (Malayalam)": "https://github.com/google/fonts/raw/main/ofl/chilanka/Chilanka-Regular.ttf",
    "Galada (Bengali)": "https://github.com/google/fonts/raw/main/ofl/galada/Galada-Regular.ttf",
    "Peddana (Telugu)": "https://github.com/google/fonts/raw/main/ofl/peddana/Peddana-Regular.ttf",
    "Mogra (Gujarati)": "https://github.com/google/fonts/raw/main/ofl/mogra/Mogra-Regular.ttf",
    "Hubballi (Kannada)": "https://github.com/google/fonts/raw/main/ofl/hubballi/Hubballi-Regular.ttf"
}

@st.cache_resource
def load_font(font_name: str, size: int) -> Any:
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

def load_custom_font(font_bytes: bytes, size: int) -> Any:
    try:
        return ImageFont.truetype(io.BytesIO(font_bytes), size)
    except Exception as e:
        st.error(f"Failed to load custom font: {e}")
        return ImageFont.load_default()

def create_background(style: str, width: int, height: int, custom_bg: Optional[bytes] = None, line_spacing: int = 40, margin_top: int = 100, font_size: int = 30, is_paid: bool = False) -> Image.Image:
    if custom_bg:
        try:
            img = Image.open(io.BytesIO(custom_bg)).convert("RGBA")
            return img.resize((width, height))
        except Exception:
            pass 

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
    
    if not is_paid:
        wm_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        wm_draw = ImageDraw.Draw(wm_layer)
        watermark_font = ImageFont.load_default()
        for y in range(40, height, 100):
            for x in range(20, width, 150):
                wm_draw.text((x, y), "PREVIEW", fill=(150, 150, 150, 120), font=watermark_font)
        img = Image.alpha_composite(img, wm_layer)
        
    return img

def process_page(args: Tuple[Image.Image, str, int, int, Optional[bytes], int, int, int, bool, bool]) -> Image.Image:
    """Helper function to apply background and texture to a rendered text layer in parallel."""
    text_layer, paper_style, width, height, custom_bg, line_spacing, margin_top, font_size, is_paid, apply_texture = args
    
    bg = create_background(paper_style, width, height, custom_bg, line_spacing, margin_top, font_size, is_paid)
    
    if apply_texture and is_paid:
        arr = np.array(text_layer)
        alpha = arr[:,:,3]
        mask = alpha > 0
        if mask.any():
            noise = np.random.randint(150, 255, size=alpha.shape)
            arr[:,:,3] = np.where(mask, (alpha.astype(np.float32) * (noise / 255.0)).astype(np.uint8), alpha)
            text_layer = Image.fromarray(arr, mode="RGBA")
            
    out = Image.alpha_composite(bg.convert("RGBA"), text_layer)
    return out.convert("RGB")

@st.cache_data(show_spinner=False)
def render_handwriting_cached(text: str, font_size: int, ink_color: str, paper_style: str, custom_bg: Optional[bytes], 
                              messiness: str, margins: Tuple[int, int, int, int], page_size: Tuple[int, int], 
                              line_spacing_factor: float, apply_texture: bool, is_paid: bool, mistake_prob: float, 
                              font_choice: Optional[str] = None, custom_font_bytes: Optional[bytes] = None, 
                              max_pages: int = 50) -> Tuple[List[Image.Image], float]:
    
    if custom_font_bytes:
        font_obj = load_custom_font(custom_font_bytes, font_size)
    else:
        font_obj = load_font(font_choice or "Homemade Apple", font_size)
        
    width, height = page_size
    margin_top, margin_bottom, margin_left, margin_right = margins
    
    if paper_style == "College Ruled":
        margin_left = max(margin_left, 85)
    elif paper_style == "Yellow Legal":
        margin_left = max(margin_left, 110)
        
    raw_text_layers: List[Image.Image] = []
    lines = text.split('\n')
    line_spacing = int(font_size * line_spacing_factor)
    
    text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_layer)
    
    x, y = margin_left, margin_top
    
    jitter_amp = 0
    if messiness == "Slight Wobble":
        jitter_amp = 2
    elif messiness == "Messy Wobble":
        jitter_amp = 5

    def add_page():
        nonlocal text_layer, draw
        raw_text_layers.append(text_layer)
        text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_layer)

    h = ink_color.lstrip('#')
    rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    for line in lines:
        tokens = re.split(r'( +|\n)', line)
        for token in tokens:
            if not token:
                continue
                
            current_color = rgb
            clean_word = token
            
            if token.strip() and token.startswith('*') and token.endswith('*') and len(token) > 2:
                current_color = (200, 0, 0)
                clean_word = token[1:-1]
                
            is_mistake = (random.random() < mistake_prob) if clean_word.strip() else False
            
            def render_text(w_text: str, color: Tuple[int, int, int], cross_out: bool = False):
                nonlocal x, y, draw
                w_w = draw.textlength(w_text, font=font_obj)
                is_space = (w_text.strip() == "")
                
                if x + w_w > width - margin_right:
                    if is_space:
                        return
                    x = margin_left
                    y += line_spacing
                    if y + font_size > height - margin_bottom:
                        if len(raw_text_layers) >= max_pages - 1:
                            return 
                        add_page()
                        y = margin_top
                        
                if is_space:
                    x += w_w
                    return
                    
                start_x, start_y = x, y
                dy = random.uniform(-jitter_amp, jitter_amp) if jitter_amp > 0 else 0
                dx = random.uniform(-jitter_amp/2, jitter_amp/2) if jitter_amp > 0 else 0
                
                alpha = random.randint(180, 255)
                fill_color = color + (alpha,)
                
                draw.text((x + dx, y + dy), w_text, fill=fill_color, font=font_obj)
                x += w_w
                
                if cross_out:
                    cross_y = start_y + font_size * 0.6 + dy
                    draw.line([(start_x, cross_y), (x, cross_y)], fill=color + (200,), width=3)
            
            if is_mistake:
                chars = list(clean_word)
                if len(chars) > 1:
                    idx = random.randint(0, len(chars)-2)
                    chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
                    wrong_word = "".join(chars)
                else:
                    wrong_word = "wrong"
                    
                render_text(wrong_word, color=current_color, cross_out=True)
                x += draw.textlength(" ", font=font_obj)
                
            render_text(clean_word, color=current_color)
            
        x = margin_left
        y += line_spacing
        if y + font_size > height - margin_bottom:
            if len(raw_text_layers) >= max_pages - 1:
                break
            add_page()
            y = margin_top

    raw_text_layers.append(text_layer)
    
    # Process backgrounds and textures in parallel using ThreadPoolExecutor
    args_list = [
        (layer, paper_style, width, height, custom_bg, line_spacing, margin_top, font_size, is_paid, apply_texture)
        for layer in raw_text_layers
    ]
    
    with ThreadPoolExecutor() as executor:
        images = list(executor.map(process_page, args_list))
        
    return images, y
