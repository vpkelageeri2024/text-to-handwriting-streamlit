import unittest
import numpy as np
import io
import time
import fitz
from PIL import Image, ImageDraw
from renderer import render_handwriting_cached, parse_markdown_line, apply_sketch_effect, draw_char_rotated
from utils import extract_formatted_text_from_pdf, extract_text_from_file

class TestMilestone3StressAndAdversarial(unittest.TestCase):
    def setUp(self):
        # Base settings for rendering
        self.base_settings = {
            "font_size": 24,
            "ink_color": "#1e3a8a",  # Dark blue
            "paper_style": "College Ruled",
            "custom_bg": None,
            "messiness": "Slight Wobble",
            "margins": (60, 60, 60, 60),
            "page_size": (800, 1000),
            "line_spacing_factor": 1.5,
            "apply_texture": True,
            "is_paid": True,
            "mistake_prob": 0.05,
            "font_choice": "Homemade Apple",
            "custom_font_bytes": None,
            "max_pages": 10
        }

    def test_mathematical_non_identity_verification(self):
        """
        Adversarial: Verify that generating the same document twice with the exact same settings
        yields two mathematically non-identical image arrays due to random jitter/opacity.
        """
        text = "This is a test document to verify mathematical non-identity."
        
        # Bypass cache by calling the underlying __wrapped__ function if it exists,
        # or clear the Streamlit cache to ensure we test the generator's execution.
        render_func = render_handwriting_cached
        if hasattr(render_handwriting_cached, "__wrapped__"):
            render_func = render_handwriting_cached.__wrapped__
            
        images1, _ = render_func(text=text, **self.base_settings)
        images2, _ = render_func(text=text, **self.base_settings)
        
        self.assertEqual(len(images1), len(images2))
        self.assertGreater(len(images1), 0)
        
        for idx, (img1, img2) in enumerate(zip(images1, images2)):
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            
            # Check shape equality
            self.assertEqual(arr1.shape, arr2.shape)
            
            # Calculate pixel differences
            diff = np.abs(arr1.astype(int) - arr2.astype(int))
            diff_pixels = np.sum(diff > 0)
            total_pixels = arr1.size
            diff_percentage = (diff_pixels / total_pixels) * 100
            
            print(f"\n[Non-identity] Page {idx+1}: Different values in {diff_pixels}/{total_pixels} bytes ({diff_percentage:.4f}%)")
            
            # Verify they are mathematically non-identical
            self.assertFalse(np.array_equal(arr1, arr2), f"Page {idx+1} is identical between two runs!")
            self.assertGreater(diff_pixels, 0, f"Page {idx+1} has 0 different pixels between two runs!")

    def test_extremely_long_text_performance_and_limits(self):
        """
        Stress: Test the system with an extremely long text input.
        Verifies that max_pages works and does not cause OOM, infinite loops, or crashes.
        """
        # Generate 15,000 words (~75,000 characters)
        long_words = ["word"] * 15000
        text = " ".join(long_words)
        
        settings = self.base_settings.copy()
        settings["max_pages"] = 3  # Cap page output to test boundary limit
        
        start_time = time.time()
        render_func = render_handwriting_cached.__wrapped__ if hasattr(render_handwriting_cached, "__wrapped__") else render_handwriting_cached
        images, last_y = render_func(text=text, **settings)
        elapsed = time.time() - start_time
        
        print(f"\n[Long Text Stress] Rendered {len(images)} pages in {elapsed:.2f} seconds")
        
        # Verify page size constraint
        self.assertLessEqual(len(images), settings["max_pages"])
        self.assertGreater(len(images), 0)

    def test_weird_and_malicious_characters(self):
        """
        Adversarial: Test rendering with emojis, Unicode scripts, control characters, and escape sequences.
        """
        weird_texts = [
            "Emojis: 😊 🚀 🔒 ⚠️ ❌ ✅",
            "Devanagari: हिन्दी वर्णमाला",
            "Cyrillic: Русский язык",
            "Chinese: 中文字符测试",
            "Control chars: \t \r \b \x00 \x01 \x1f",
            "Quotes & Escapes: \\ \" ' \n \n\n \\n \\t",
            "HTML Injection: <script>alert('hack')</script> <b>bold</b>",
            "Very long single word: " + ("A" * 500)  # Exceeds page width
        ]
        
        render_func = render_handwriting_cached.__wrapped__ if hasattr(render_handwriting_cached, "__wrapped__") else render_handwriting_cached
        
        for text in weird_texts:
            try:
                images, _ = render_func(text=text, **self.base_settings)
                self.assertGreater(len(images), 0)
            except Exception as e:
                self.fail(f"Failed to render text containing weird characters: '{text}'. Error: {e}")

    def test_large_pdf_extraction_formatting(self):
        """
        Stress/Adversarial: Test extracting layout and formatting from a large multi-page PDF.
        """
        doc = fitz.open()
        
        # Create 8 pages with headers, body, and bold text
        for i in range(8):
            page = doc.new_page(width=595, height=842)
            # Header
            page.insert_text((50, 50), f"Section Header {i+1}", fontsize=22, fontname="helv")
            # Body
            page.insert_text((50, 100), f"This is page {i+1} normal text content.", fontsize=11, fontname="helv")
            # Bold
            page.insert_text((50, 130), f"Important bold point {i+1}", fontsize=11, fontname="hebo")
            
        pdf_bytes = doc.write()
        doc.close()
        
        class MockUploadedFile:
            def __init__(self, data):
                self.data = data
                self.name = "large_stress_doc.pdf"
            def read(self):
                return self.data
            def seek(self, pos):
                pass
                
        uploaded_file = MockUploadedFile(pdf_bytes)
        
        start_time = time.time()
        extracted_md = extract_formatted_text_from_pdf(uploaded_file)
        elapsed = time.time() - start_time
        
        print(f"\n[Large PDF Stress] Extracted text from 8-page PDF in {elapsed:.4f} seconds")
        
        # Verify formatting flags
        for i in range(8):
            self.assertIn(f"# Section Header {i+1}", extracted_md)
            self.assertIn(f"**Important bold point {i+1}**", extracted_md)

    def test_sketch_filter_boundary_images(self):
        """
        Adversarial: Test the sketch filter with extreme inputs (empty, very large, transparent).
        """
        # 1. Single pixel image
        img_single = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        sketch_single = apply_sketch_effect(img_single)
        self.assertEqual(sketch_single.size, (1, 1))
        
        # 2. Large image
        img_large = Image.new("RGBA", (3000, 3000), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img_large)
        draw.line([(0, 0), (3000, 3000)], fill=(0, 0, 0, 255), width=10)
        start_time = time.time()
        sketch_large = apply_sketch_effect(img_large)
        elapsed = time.time() - start_time
        print(f"\n[Sketch Stress] Processed 3000x3000px image in {elapsed:.2f} seconds")
        self.assertEqual(sketch_large.size, (3000, 3000))
        
        # 3. Completely transparent image
        img_trans = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        sketch_trans = apply_sketch_effect(img_trans)
        arr_trans = np.array(sketch_trans)
        # Alpha channel should remain 0 (transparent)
        self.assertTrue(np.all(arr_trans[:, :, 3] == 0))

    def test_layout_edge_cases(self):
        """
        Adversarial: Run rendering with extreme layout parameters.
        """
        render_func = render_handwriting_cached.__wrapped__ if hasattr(render_handwriting_cached, "__wrapped__") else render_handwriting_cached
        
        # 1. Extremely large margins (larger than page size)
        settings = self.base_settings.copy()
        settings["margins"] = (500, 500, 500, 500) # page is 800x1000
        # This shouldn't crash, though it might wrap heavily or fit no words per line.
        try:
            images, _ = render_func("Hello", **settings)
            self.assertGreater(len(images), 0)
        except Exception as e:
            self.fail(f"Failed with large margins: {e}")
            
        # 2. Line spacing factor = 0
        settings_spacing = self.base_settings.copy()
        settings_spacing["line_spacing_factor"] = 0.0
        try:
            images, _ = render_func("Line 1\nLine 2", **settings_spacing)
            self.assertGreater(len(images), 0)
        except Exception as e:
            self.fail(f"Failed with zero line spacing factor: {e}")
            
        # 3. Mistake probability = 1.0 (every word crossed out)
        settings_mistake = self.base_settings.copy()
        settings_mistake["mistake_prob"] = 1.0
        try:
            images, _ = render_func("This is a mistake test sentence.", **settings_mistake)
            self.assertGreater(len(images), 0)
        except Exception as e:
            self.fail(f"Failed with mistake probability 1.0: {e}")

if __name__ == '__main__':
    unittest.main()
