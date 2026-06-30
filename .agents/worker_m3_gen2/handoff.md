# Handoff Report — worker_m3_gen2

## 1. Observation

Direct observations and findings in the codebase:
- **Streamlit Caching Billing Exploit**:
  - Path: `/home/vishal/text-to-handwriting-streamlit/renderer.py`
  - Function: `render_handwriting_cached` (lines 304-308) was decorated with `@st.cache_data(show_spinner=False)`, causing repeated paid calls with identical settings to return cached outputs instead of busting the cache and generating unique jitter.
  - Path: `/home/vishal/text-to-handwriting-streamlit/app.py`
  - Function call: `render_handwriting_cached` at line 362 did not pass a unique identifier (like a UUID) to prevent cached hits.
- **OpenCV Sketch Filter Small Image Crash**:
  - Path: `/home/vishal/text-to-handwriting-streamlit/renderer.py`
  - Function: `apply_sketch_effect` (line 201) called `cv2.GaussianBlur(gray_inv, (21, 21), 0)` with a hardcoded kernel size of `21x21`. If the input image dimension was smaller than 21 (e.g. 1x1 or 2x2), OpenCV would crash.
- **Word wrapping overflow & clipping**:
  - Path: `/home/vishal/text-to-handwriting-streamlit/renderer.py`
  - Loop: `render_handwriting_cached` (lines 399-408) checked `x + word_w > width - margin_right` to wrap words, but did not handle characters individually if a word had no spaces, or if a word following a mistake was advanced past the boundaries.
- **Extreme Font Size CPU Loop**:
  - Path: `/home/vishal/text-to-handwriting-streamlit/renderer.py`
  - Issue: No upper bound checking on `font_size` in `render_handwriting_cached`. An extremely large font size would cause every word/character to exceed the printable area instantly, triggering infinite page-wrapping up to `max_pages` and consuming high CPU.

---

## 2. Logic Chain

From the observations, the following logic and fixes were developed:
1. **Caching Exploit**:
   - By adding a `cache_buster: Optional[str] = None` argument to `render_handwriting_cached` in `renderer.py`, we change the cache signature.
   - When a paid run is triggered in `app.py`, generating a unique UUID via `uuid.uuid4()` and passing it as `cache_buster` guarantees a cache miss in `@st.cache_data`, ensuring a fresh unique handwriting image with randomized jitter is generated. Free/preview runs can continue to use caching (defaulting to `None`).
2. **OpenCV Sketch Filter Crash**:
   - To make the kernel size dynamic, we get the image width and height using `image.size`.
   - We calculate `k_w = min(21, width, height)`.
   - Since OpenCV's GaussianBlur requires the kernel size to be odd, we check `if k_w % 2 == 0: k_w = max(1, k_w - 1)`.
   - We call `cv2.GaussianBlur(gray_inv, (k_w, k_w), 0)`.
3. **Word Wrapping & Clipping**:
   - Added character-level boundary checks `if x + char_w > width - margin_right:` in both the mistake rendering loop and the normal character rendering loop.
   - If a boundary is crossed, the drawing coordinates wrap to `x = margin_left`, and `y` advances by `current_line_spacing` (with a page increment/limit check).
   - This ensures words with no spaces or words pushed off the page by a preceding mistake are wrapped cleanly character-by-character.
4. **Extreme Font Size CPU Loop**:
   - At the beginning of `render_handwriting_cached`, we calculate the printable height: `printable_height = height - margin_top - margin_bottom`.
   - We clamp `font_size` to a maximum of `max_font_size = max(1, int(printable_height * 0.5))`. This guarantees the font size cannot exceed 50% of the printable page height, preventing page allocation loop crashes.

---

## 3. Caveats

- We assumed that `is_preview=True` calls do not need unique cache-busting and can reuse the cache safely, which is consistent with user specifications.
- Race conditions or network issues during Supabase client initialization under unit tests are mocked, which is correct and handled by the test suites.

---

## 4. Conclusion

All 4 implementation issues identified in the Milestone 3 implementation have been fully fixed in `renderer.py` and `app.py`. The system is now robust against caching exploits, OpenCV crashes on small sketch images, boundary overflows, and extreme font size CPU loops.

---

## 5. Verification Method

To verify the changes:
1. Run the test command:
   ```bash
   python3 -m unittest test_milestone3.py test_milestone3_stress.py
   ```
2. Verify that all test cases pass without errors, including:
   - `test_mathematical_non_identity_verification`
   - `test_extremely_long_text_performance_and_limits`
   - `test_sketch_filter_boundary_images` (verifies small 1x1 image processing)
   - `test_layout_edge_cases`
3. Inspect `renderer.py` and `app.py` to confirm minimal changes were made.
