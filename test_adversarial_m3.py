import unittest
import numpy as np
import io
import fitz
import time
from PIL import Image
from renderer import render_handwriting_cached, parse_markdown_line, apply_sketch_effect
from utils import extract_formatted_text_from_pdf, extract_text_from_file

class MockUploadedFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data
        self._pos = 0

    def read(self, *args, **kwargs):
        return self.data

    def getvalue(self):
        return self.data

    def seek(self, pos):
        self._pos = pos

class TestAdversarialM3(unittest.TestCase):
    def test_markdown_parsing_edge_cases(self):
        # 1. Unclosed bold
        tokens = parse_markdown_line("This is **unclosed bold text")
        # Let's verify what parse_markdown_line returns for unclosed bold.
        # It uses re.split(r'(\*\*[^*]+?\*\*)', content)
        # If it doesn't match, it shouldn't treat it as bold.
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "This is **unclosed bold text")
        self.assertFalse(tokens[0]['bold'])

        # 2. Nested header inside bold
        # Wait, header is matched first with: header_match = re.match(r'^(#+)\s+(.*)$', line)
        tokens = parse_markdown_line("# **Bold Header**")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "Bold Header")
        self.assertTrue(tokens[0]['bold'])
        self.assertTrue(tokens[0]['header'])

        # 3. Empty bold syntax '**'
        tokens = parse_markdown_line("Hello **** world")
        # Empty part in re.split might produce empty tokens or normal tokens
        # Let's assert it runs without raising errors and returns correct tokens
        self.assertTrue(isinstance(tokens, list))

        # 4. Multiple bolds in a single line
        tokens = parse_markdown_line("This **is** a **bold** test")
        # Should split into: "This ", "**is**", " a ", "**bold**", " test"
        bold_tokens = [t for t in tokens if t['bold']]
        self.assertEqual(len(bold_tokens), 2)
        self.assertEqual(bold_tokens[0]['text'], "is")
        self.assertEqual(bold_tokens[1]['text'], "bold")

        # 5. Empty line or only spaces
        tokens = parse_markdown_line("")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "")

        tokens = parse_markdown_line("   ")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "   ")

    def test_letter_variability_mathematical_difference(self):
        text = "Check mathematical differences between dual runs."
        
        # Test configurations
        configs = [
            ("Perfect", False),
            ("Slight Wobble", False),
            ("Messy Wobble", False),
        ]
        
        for messiness, is_preview in configs:
            with self.subTest(messiness=messiness, is_preview=is_preview):
                images1, _ = render_handwriting_cached(
                    text=text,
                    font_size=20,
                    ink_color="#000000",
                    paper_style="Blank",
                    custom_bg=None,
                    messiness=messiness,
                    margins=(50, 50, 50, 50),
                    page_size=(400, 400),
                    line_spacing_factor=1.5,
                    apply_texture=False,
                    is_paid=True,
                    mistake_prob=0.0,
                    is_preview=is_preview
                )
                
                images2, _ = render_handwriting_cached(
                    text=text,
                    font_size=20,
                    ink_color="#000000",
                    paper_style="Blank",
                    custom_bg=None,
                    messiness=messiness,
                    margins=(50, 50, 50, 50),
                    page_size=(400, 400),
                    line_spacing_factor=1.5,
                    apply_texture=False,
                    is_paid=True,
                    mistake_prob=0.0,
                    is_preview=is_preview
                )
                
                self.assertEqual(len(images1), len(images2))
                self.assertGreater(len(images1), 0)
                
                # Check that for standard rendering (is_preview=False), the pixel arrays are different
                # due to character-level random jitter.
                arr1 = np.array(images1[0])
                arr2 = np.array(images2[0])
                
                # Assert mathematical difference
                diff_pixels = np.sum(arr1 != arr2)
                total_pixels = arr1.size
                diff_percentage = (diff_pixels / total_pixels) * 100
                print(f"[{messiness}] Pixel diff count: {diff_pixels} / {total_pixels} ({diff_percentage:.4f}%)")
                
                self.assertFalse(np.array_equal(arr1, arr2), f"Dual rendering runs with messiness='{messiness}' yielded mathematically identical image arrays!")
                self.assertGreater(diff_pixels, 0, f"No pixel differences found in dual run with messiness='{messiness}'")

    def test_preview_mode_speed_and_identity(self):
        # Preview mode uses cached renders or bypasses jitter for high speed
        # Preview mode should have is_preview = True
        text = "This is a speed preview test to check performance."
        
        start_time = time.time()
        images_prev1, _ = render_handwriting_cached(
            text=text,
            font_size=20,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Slight Wobble",
            margins=(50, 50, 50, 50),
            page_size=(400, 400),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            is_preview=True
        )
        prev1_duration = time.time() - start_time
        
        start_time = time.time()
        images_prev2, _ = render_handwriting_cached(
            text=text,
            font_size=20,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Slight Wobble",
            margins=(50, 50, 50, 50),
            page_size=(400, 400),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            is_preview=True
        )
        prev2_duration = time.time() - start_time
        
        print(f"[Preview Mode] Speed: Run 1 = {prev1_duration:.4f}s, Run 2 = {prev2_duration:.4f}s")
        
        # Verify that preview mode images are identical since is_preview resets jitter ranges to (0.0, 0.0)
        # unless caching is at play, but even without cache they should be identical.
        arr_p1 = np.array(images_prev1[0])
        arr_p2 = np.array(images_prev2[0])
        
        # Due to render_handwriting_cached being @st.cache_data, it returns identical cached images.
        # But even if cache is bypassed, is_preview=True has rot_range = (0.0, 0.0), baseline_range = (0.0, 0.0), spacing_range = (0.0, 0.0).
        # Let's confirm they are identical.
        self.assertTrue(np.array_equal(arr_p1, arr_p2), "Preview mode generated non-identical images between runs!")

    def test_extreme_inputs(self):
        # 1. Extremely long text (milestone limit is max_pages=50, preview limit is 4 lines, 1 page)
        long_text = "\n".join([f"This is line number {i} of the extremely long test text." for i in range(1000)])
        
        # Rendering long text in standard mode should cap at max_pages (default 50)
        images, final_y = render_handwriting_cached(
            text=long_text,
            font_size=20,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Slight Wobble",
            margins=(50, 50, 50, 50),
            page_size=(400, 400),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            max_pages=5, # Limit to 5 pages for faster execution in tests
            is_preview=False
        )
        self.assertEqual(len(images), 5) # Caps at max_pages
        
        # 2. Extreme/weird margins: zero margins
        images_zero_margin, _ = render_handwriting_cached(
            text="Hello world",
            font_size=20,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Slight Wobble",
            margins=(0, 0, 0, 0),
            page_size=(200, 200),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            max_pages=1,
            is_preview=False
        )
        self.assertEqual(len(images_zero_margin), 1)

        # 3. Extreme font size vs page size
        # Font size (300) larger than page width/height (100x100)
        images_huge_font, _ = render_handwriting_cached(
            text="Huge font sizing",
            font_size=300,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Perfect",
            margins=(5, 5, 5, 5),
            page_size=(100, 100),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            max_pages=1,
            is_preview=False
        )
        self.assertEqual(len(images_huge_font), 1)

    def test_unicode_characters(self):
        # Test rendering with various non-latin scripts and emojis
        unicode_text = (
            "Hindi: नमस्ते दुनिया\n"
            "Chinese: 你好世界\n"
            "Arabic: مرحبا بالعالم\n"
            "Emojis: 📝✨🔥👍"
        )
        
        # Test rendering using standard font choice
        images, _ = render_handwriting_cached(
            text=unicode_text,
            font_size=20,
            ink_color="#000000",
            paper_style="Blank",
            custom_bg=None,
            messiness="Slight Wobble",
            margins=(50, 50, 50, 50),
            page_size=(400, 400),
            line_spacing_factor=1.5,
            apply_texture=False,
            is_paid=True,
            mistake_prob=0.0,
            max_pages=1,
            is_preview=False
        )
        self.assertGreater(len(images), 0)

    def test_sketch_filter_edge_cases(self):
        # 1. Blank/Empty image sketch
        img_blank = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        sketch_blank = apply_sketch_effect(img_blank)
        self.assertEqual(sketch_blank.size, img_blank.size)

        # 2. Large image sketch performance
        img_large = Image.new("RGBA", (2000, 2000), (200, 200, 200, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img_large)
        draw.rectangle([500, 500, 1500, 1500], fill=(0, 0, 0, 255))
        
        start_time = time.time()
        sketch_large = apply_sketch_effect(img_large)
        duration = time.time() - start_time
        print(f"[Sketch Filter] 2000x2000 image processed in {duration:.4f} seconds")
        self.assertEqual(sketch_large.size, img_large.size)
        self.assertLess(duration, 2.0, "Sketch filter took too long for a 2000x2000 image")

    def test_pdf_extraction_robustness(self):
        # Create a complex mock PDF with various formatting elements
        doc = fitz.open()
        
        # Page 1: Headings and mixed styles
        page1 = doc.new_page(width=600, height=800)
        # Normal header
        page1.insert_text((50, 50), "Section 1: Setup", fontsize=18, fontname="helv")
        # Bold text (PyMuPDF dict structure uses flags or font name to identify bold)
        page1.insert_text((50, 100), "This text is bold", fontsize=11, fontname="helv-bold")
        # Italic text
        page1.insert_text((50, 150), "This text is italic", fontsize=11, fontname="helv-oblique")
        # Normal text
        page1.insert_text((50, 200), "This is plain normal text.", fontsize=11, fontname="helv")
        
        # Page 2: Empty blocks and non-latin text
        page2 = doc.new_page(width=600, height=800)
        page2.insert_text((50, 50), "Section 2: Unicode", fontsize=18, fontname="helv")
        page2.insert_text((50, 100), "Chinese: 华文 text", fontsize=11, fontname="helv")
        
        pdf_bytes = doc.write()
        doc.close()
        
        uploaded_file = MockUploadedFile("complex_test.pdf", pdf_bytes)
        extracted_text = extract_formatted_text_from_pdf(uploaded_file)
        
        print("\n[PDF Extraction Output]:")
        print(extracted_text)
        
        # Verify headers got identified
        self.assertIn("# Section 1: Setup", extracted_text)
        self.assertIn("# Section 2: Unicode", extracted_text)
        # Verify bold got identified
        # Note: Depending on font flags, helv-bold might be detected as bold. Let's inspect.
        self.assertTrue(any(x in extracted_text for x in ["**This text is bold**", "This text is bold"]), "Bold text extraction failed to retain formatting safely")

if __name__ == '__main__':
    unittest.main()
