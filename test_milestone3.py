import unittest
import numpy as np
import io
import fitz
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

class TestMilestone3(unittest.TestCase):
    def test_markdown_parsing(self):
        # 1. Simple text
        tokens = parse_markdown_line("Hello world")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "Hello world")
        self.assertFalse(tokens[0]['bold'])
        self.assertFalse(tokens[0]['header'])

        # 2. Bold text
        tokens = parse_markdown_line("This is **bold** text")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0]['text'], "This is ")
        self.assertFalse(tokens[0]['bold'])
        self.assertEqual(tokens[1]['text'], "bold")
        self.assertTrue(tokens[1]['bold'])
        self.assertEqual(tokens[2]['text'], " text")
        self.assertFalse(tokens[2]['bold'])

        # 3. Header text
        tokens = parse_markdown_line("# Header Title")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]['text'], "Header Title")
        self.assertFalse(tokens[0]['bold'])
        self.assertTrue(tokens[0]['header'])

        # 4. Header with bold text
        tokens = parse_markdown_line("# Header with **bold** word")
        self.assertEqual(len(tokens), 3)
        self.assertTrue(tokens[0]['header'])
        self.assertTrue(tokens[1]['header'])
        self.assertTrue(tokens[1]['bold'])

    def test_character_level_jitter_non_identity(self):
        # Render the same text twice with identical parameters
        text = "The quick brown fox jumps over the lazy dog."
        font_size = 20
        ink_color = "#000000"
        paper_style = "Blank"
        custom_bg = None
        messiness = "Slight Wobble"
        margins = (50, 50, 50, 50)
        page_size = (400, 400)
        line_spacing_factor = 1.5
        apply_texture = False
        is_paid = True
        mistake_prob = 0.0

        # Execute run 1
        images1, _ = render_handwriting_cached(
            text=text,
            font_size=font_size,
            ink_color=ink_color,
            paper_style=paper_style,
            custom_bg=custom_bg,
            messiness=messiness,
            margins=margins,
            page_size=page_size,
            line_spacing_factor=line_spacing_factor,
            apply_texture=apply_texture,
            is_paid=is_paid,
            mistake_prob=mistake_prob
        )

        # Execute run 2
        images2, _ = render_handwriting_cached(
            text=text,
            font_size=font_size,
            ink_color=ink_color,
            paper_style=paper_style,
            custom_bg=custom_bg,
            messiness=messiness,
            margins=margins,
            page_size=page_size,
            line_spacing_factor=line_spacing_factor,
            apply_texture=apply_texture,
            is_paid=is_paid,
            mistake_prob=mistake_prob
        )

        self.assertEqual(len(images1), len(images2))
        self.assertGreater(len(images1), 0)

        # Verify that the dual rendering run produces mathematically non-identical image arrays
        for img1, img2 in zip(images1, images2):
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            self.assertFalse(np.array_equal(arr1, arr2), "Dual rendering runs with identical settings yielded identical image arrays!")

    def test_pdf_extraction_formatting(self):
        # Create a mock PDF with PyMuPDF
        doc = fitz.open()
        page = doc.new_page(width=595, height=842) # A4 size
        
        # Insert a header (larger font size)
        page.insert_text((50, 50), "Document Header Title", fontsize=20, fontname="helv")
        
        # Insert a normal text line
        page.insert_text((50, 100), "This is normal body text.", fontsize=11, fontname="helv")
        
        # Insert a bold text line (using Helvetica-Bold font 'hebo')
        page.insert_text((50, 150), "This is bold body text.", fontsize=11, fontname="hebo")
        
        pdf_bytes = doc.write()
        doc.close()

        uploaded_file = MockUploadedFile("test_doc.pdf", pdf_bytes)
        
        # Extract formatting
        markdown_text = extract_formatted_text_from_pdf(uploaded_file)
        
        # Verify that the header title has been identified and prefixed with '#'
        self.assertIn("# Document Header Title", markdown_text)
        
        # Verify that bold text has been identified and wrapped in '**'
        self.assertIn("**This is bold body text.**", markdown_text)

    def test_sketch_filter(self):
        # Create a blank PIL Image
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        
        # Draw some features on it
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.line([(10, 10), (90, 90)], fill=(0, 0, 0, 255), width=5)
        
        # Apply filter
        sketch = apply_sketch_effect(img)
        
        self.assertEqual(sketch.size, img.size)
        self.assertEqual(sketch.mode, img.mode)
        
        # The output sketch image array should not be completely identical to the input
        arr_img = np.array(img)
        arr_sketch = np.array(sketch)
        self.assertFalse(np.array_equal(arr_img, arr_sketch))

if __name__ == '__main__':
    unittest.main()
