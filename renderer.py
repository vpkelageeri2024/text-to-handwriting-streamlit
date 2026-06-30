import os
import io
import math
import random
import re
import urllib.request
import numpy as np
import streamlit as st
import cv2
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

def parse_markdown_line(line: str) -> List[Dict[str, Any]]:
    """Parses a single line of Markdown for headers (#) and bold text (**bold**)."""
    line = line.rstrip('\r\n')
    
    is_header = False
    header_match = re.match(r'^(#+)\s+(.*)$', line)
    if header_match:
        is_header = True
        content = header_match.group(2)
    else:
        content = line

    tokens = []
    # Split by **bold** text
    parts = re.split(r'(\*\*[^*]+?\*\*)', content)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) >= 4:
            tokens.append({
                'text': part[2:-2],
                'bold': True,
                'header': is_header
            })
        else:
            tokens.append({
                'text': part,
                'bold': False,
                'header': is_header
            })
            
    if not tokens:
        tokens.append({
            'text': '',
            'bold': False,
            'header': is_header
        })
        
    return tokens

def apply_sketch_effect(image: Image.Image) -> Image.Image:
    """Applies an OpenCV pencil sketch filter to a PIL Image."""
    orig_mode = image.mode
    
    # Convert PIL Image to RGBA numpy array
    img_np = np.array(image.convert("RGBA"))
    if img_np.size == 0:
        return image
        
    rgb_img = img_np[:, :, :3]
    alpha = img_np[:, :, 3]
    
    # Convert to grayscale
    gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)
    
    # Invert grayscale
    gray_inv = 255 - gray
    
    # Calculate Gaussian blur kernel size dynamically
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    k_w = min(21, width, height)
    if k_w % 2 == 0:
        k_w = max(1, k_w - 1)
    
    # Blur the inverted image
    blur = cv2.GaussianBlur(gray_inv, (k_w, k_w), 0)
    
    # Invert blurred
    blur_inv = 255 - blur
    
    # Divide gray by inverted blurred to get sketch effect
    sketch = cv2.divide(gray, blur_inv, scale=256.0)
    
    # Convert back to RGB
    sketch_rgb = cv2.cvtColor(sketch, cv2.COLOR_GRAY2RGB)
    
    # Combine with original alpha channel
    out_np = np.zeros_like(img_np)
    out_np[:, :, :3] = sketch_rgb
    out_np[:, :, 3] = alpha
    
    out_img = Image.fromarray(out_np, mode="RGBA")
    if orig_mode != "RGBA":
        out_img = out_img.convert(orig_mode)
        
    return out_img

def alpha_composite_paste(dest: Image.Image, src: Image.Image, box: Tuple[int, int]):
    """Safely pastes src onto dest using alpha compositing, handling boundaries."""
    bx, by = box
    sw, sh = src.size
    dw, dh = dest.size
    
    # Calculate overlapping region
    x0 = max(0, bx)
    y0 = max(0, by)
    x1 = min(dw, bx + sw)
    y1 = min(dh, by + sh)
    
    if x1 <= x0 or y1 <= y0:
        return
        
    src_crop = src.crop((x0 - bx, y0 - by, x1 - bx, y1 - by))
    dest_crop = dest.crop((x0, y0, x1, y1))
    
    composite = Image.alpha_composite(dest_crop, src_crop)
    dest.paste(composite, (x0, y0))

def draw_char_rotated(char: str, font_obj: Any, fill_color: Tuple[int, int, int, int], 
                      theta: float, dy: float, x: float, y: float, text_layer: Image.Image, 
                      bold: bool = False):
    """Draws a single character onto a text layer with rotation, offset, and stroke if bold."""
    draw_obj = ImageDraw.Draw(text_layer)
    stroke_width = 2 if bold else 0
    
    try:
        bbox = font_obj.getbbox(char, stroke_width=stroke_width)
    except TypeError:
        bbox = font_obj.getbbox(char)
        
    if not bbox:
        return
        
    left, top, right, bottom = bbox
    
    if stroke_width > 0:
        left -= stroke_width
        top -= stroke_width
        right += stroke_width
        bottom += stroke_width
        
    w = right - left
    h = bottom - top
    if w <= 0 or h <= 0:
        return
        
    # Temporary RGBA image for drawing the character
    pad = font_obj.size
    char_img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    char_draw = ImageDraw.Draw(char_img)
    
    # Draw character with offset mapping to text origin
    try:
        if stroke_width > 0:
            char_draw.text((pad - left, pad - top), char, font=font_obj, fill=fill_color,
                           stroke_width=stroke_width, stroke_fill=fill_color)
        else:
            char_draw.text((pad - left, pad - top), char, font=font_obj, fill=fill_color)
    except TypeError:
        if stroke_width > 0:
            for dx_offset in [-1, 0, 1]:
                for dy_offset in [-1, 0, 1]:
                    char_draw.text((pad - left + dx_offset, pad - top + dy_offset), char, 
                                   font=font_obj, fill=fill_color)
        else:
            char_draw.text((pad - left, pad - top), char, font=font_obj, fill=fill_color)
            
    # Rotate around text origin center=(pad - left, pad - top)
    center = (pad - left, pad - top)
    rotated = char_img.rotate(theta, resample=Image.BICUBIC, center=center)
    
    # Target pasting coordinates
    paste_x = int(round(x - (pad - left)))
    paste_y = int(round(y + dy - (pad - top)))
    
    alpha_composite_paste(text_layer, rotated, (paste_x, paste_y))

@st.cache_data(show_spinner=False)
def render_handwriting_cached(text: str, font_size: int, ink_color: str, paper_style: str, custom_bg: Optional[bytes], 
                              messiness: str, margins: Tuple[int, int, int, int], page_size: Tuple[int, int], 
                              line_spacing_factor: float, apply_texture: bool, is_paid: bool, mistake_prob: float, 
                              font_choice: Optional[str] = None, custom_font_bytes: Optional[bytes] = None, 
                              max_pages: int = 50, is_preview: bool = False, cache_buster: Optional[str] = None) -> Tuple[List[Image.Image], float]:
    
    width, height = page_size
    margin_top, margin_bottom, margin_left, margin_right = margins
    
    # Clamp font_size to avoid CPU loop
    printable_height = height - margin_top - margin_bottom
    max_font_size = max(1, int(printable_height * 0.5))
    if font_size > max_font_size:
        font_size = max_font_size

    # Load fonts (both normal size and header size)
    header_font_size = int(font_size * 1.3)
    if custom_font_bytes:
        font_obj = load_custom_font(custom_font_bytes, font_size)
        header_font_obj = load_custom_font(custom_font_bytes, header_font_size)
    else:
        font_name = font_choice or "Homemade Apple"
        font_obj = load_font(font_name, font_size)
        header_font_obj = load_font(font_name, header_font_size)
        
    if paper_style == "College Ruled":
        margin_left = max(margin_left, 85)
    elif paper_style == "Yellow Legal":
        margin_left = max(margin_left, 110)
        
    raw_text_layers: List[Image.Image] = []
    line_spacing = int(font_size * line_spacing_factor)
    
    text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_layer)
    
    x, y = margin_left, margin_top
    
    # Setup jitter ranges based on messiness
    if is_preview:
        # No jitter for fast preview rendering
        rot_range = (0.0, 0.0)
        baseline_range = (0.0, 0.0)
        spacing_range = (0.0, 0.0)
    elif messiness == "Perfect":
        # Small random noise to ensure mathematically non-identical images
        rot_range = (-0.15, 0.15)
        baseline_range = (-0.15, 0.15)
        spacing_range = (-0.1, 0.1)
    elif messiness == "Slight Wobble":
        rot_range = (-1.5, 1.5)
        baseline_range = (-1.0, 1.0)
        spacing_range = (-0.8, 0.8)
    else:  # "Messy Wobble"
        rot_range = (-3.5, 3.5)
        baseline_range = (-2.0, 2.0)
        spacing_range = (-1.5, 1.5)

    def add_page():
        nonlocal text_layer, draw
        raw_text_layers.append(text_layer)
        text_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_layer)

    h = ink_color.lstrip('#')
    rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    reached_max_pages = False
    lines = text.split('\n')
    
    # Preview mode limit: max 4 lines, max 1 page
    if is_preview:
        lines = lines[:4]
        max_pages = 1
        
    for line in lines:
        if reached_max_pages:
            break
        tokens = parse_markdown_line(line)
        
        has_header = any(token['header'] for token in tokens)
        current_line_spacing = int(line_spacing * 1.3) if has_header else line_spacing
        current_font_size = int(font_size * 1.3) if has_header else font_size
        line_font_obj = header_font_obj if has_header else font_obj
        
        for token in tokens:
            if reached_max_pages:
                break
            t_text = token['text']
            bold = token['bold']
            
            # Split token text into words and spaces to preserve formatting and wrapping
            words = re.split(r'( +)', t_text)
            
            for word in words:
                if not word:
                    continue
                    
                is_space = (word.strip() == "")
                
                # Estimate word width
                word_w = draw.textlength(word, font=line_font_obj)
                if bold:
                    word_w += 4
                    
                # Wrap to next line if it exceeds boundaries
                if x + word_w > width - margin_right:
                    if is_space:
                        continue
                    x = margin_left
                    y += current_line_spacing
                    if y + current_font_size > height - margin_bottom:
                        if len(raw_text_layers) >= max_pages - 1:
                            reached_max_pages = True
                            break
                        add_page()
                        y = margin_top
                        
                if reached_max_pages:
                    break
                    
                if is_space:
                    space_jitter = random.uniform(*spacing_range)
                    x += word_w + space_jitter
                    continue
                    
                # Handle mistakes/cross-outs
                is_mistake = (random.random() < mistake_prob) if not is_preview else False
                if is_mistake:
                    chars = list(word)
                    if len(chars) > 1:
                        idx = random.randint(0, len(chars)-2)
                        chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
                        wrong_word = "".join(chars)
                    else:
                        wrong_word = "wrong"
                        
                    start_x = x
                    for char in wrong_word:
                        char_w = draw.textlength(char, font=line_font_obj)
                        theta = random.uniform(*rot_range)
                        dy = random.uniform(*baseline_range)
                        s_jitter = random.uniform(*spacing_range)
                        
                        # Wrap character-by-character if it exceeds boundaries
                        if x + char_w > width - margin_right:
                            # Draw cross-out line for the part written so far, if any
                            if x > start_x:
                                cross_y = y + current_font_size * 0.6
                                draw_obj = ImageDraw.Draw(text_layer)
                                draw_obj.line([(start_x, cross_y), (x, cross_y)], fill=rgb + (200,), width=3)
                            
                            x = margin_left
                            y += current_line_spacing
                            if y + current_font_size > height - margin_bottom:
                                if len(raw_text_layers) >= max_pages - 1:
                                    reached_max_pages = True
                                    break
                                add_page()
                                y = margin_top
                            start_x = x  # Reset start_x for the new line cross-out
                            
                        alpha = random.randint(180, 255)
                        fill_color = rgb + (alpha,)
                        
                        draw_char_rotated(char, line_font_obj, fill_color, theta, dy, x, y, text_layer, bold=bold)
                        x += char_w + s_jitter
                        
                    if reached_max_pages:
                        break
                        
                    # Draw cross-out line for the remaining part on the current line
                    if x > start_x:
                        cross_y = y + current_font_size * 0.6
                        draw_obj = ImageDraw.Draw(text_layer)
                        draw_obj.line([(start_x, cross_y), (x, cross_y)], fill=rgb + (200,), width=3)
                    
                    # Space after mistake
                    space_w = draw.textlength(" ", font=line_font_obj)
                    space_jitter = random.uniform(*spacing_range)
                    # Check if space exceeds boundary
                    if x + space_w > width - margin_right:
                        x = margin_left
                        y += current_line_spacing
                        if y + current_font_size > height - margin_bottom:
                            if len(raw_text_layers) >= max_pages - 1:
                                reached_max_pages = True
                                break
                            add_page()
                            y = margin_top
                    else:
                        x += space_w + space_jitter
                        
                if reached_max_pages:
                    break
                
                # Render the word character-by-character
                for char in word:
                    char_w = draw.textlength(char, font=line_font_obj)
                    theta = random.uniform(*rot_range)
                    dy = random.uniform(*baseline_range)
                    s_jitter = random.uniform(*spacing_range)
                    
                    if x + char_w > width - margin_right:
                        x = margin_left
                        y += current_line_spacing
                        if y + current_font_size > height - margin_bottom:
                            if len(raw_text_layers) >= max_pages - 1:
                                reached_max_pages = True
                                break
                            add_page()
                            y = margin_top
                            
                    alpha = random.randint(180, 255)
                    fill_color = rgb + (alpha,)
                    
                    draw_char_rotated(char, line_font_obj, fill_color, theta, dy, x, y, text_layer, bold=bold)
                    x += char_w + s_jitter
                    
            if reached_max_pages:
                break
                
            if len(raw_text_layers) >= max_pages and y + current_font_size > height - margin_bottom:
                reached_max_pages = True
                break
                
        if reached_max_pages:
            break
            
        # Advance line
        x = margin_left
        y += current_line_spacing
        if y + current_font_size > height - margin_bottom:
            if len(raw_text_layers) >= max_pages - 1:
                break
            add_page()
            y = margin_top
            
    if len(raw_text_layers) < max_pages:
        raw_text_layers.append(text_layer)
    
    # Process backgrounds and textures in parallel
    args_list = [
        (layer, paper_style, width, height, custom_bg, line_spacing, margin_top, font_size, is_paid, apply_texture)
        for layer in raw_text_layers
    ]
    
    with ThreadPoolExecutor() as executor:
        images = list(executor.map(process_page, args_list))
        
    return images, y
