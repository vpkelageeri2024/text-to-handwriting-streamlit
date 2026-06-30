# Handoff Report - Milestone M1 Exploration

## 1. Observation

During the exploration of `/home/vishal/text-to-handwriting-streamlit/`, the following structures and code segments were examined:

- **File Path**: `/home/vishal/text-to-handwriting-streamlit/app.py`
  - Implements the central Streamlit layout, including the settings wizard chat UI:
    ```python
    if 'wizard_step' not in st.session_state:
        st.session_state.wizard_step = 0
        ...
    ```
  - Blends the custom user drawing/signature canvas:
    ```python
    canvas_result = st_canvas(..., drawing_mode="freedraw", key="canvas")
    ```
  - Directly handles payment verification with a state hash check:
    ```python
    is_paid = st.session_state.get('paid_state_id') == current_state_id
    ```

- **File Path**: `/home/vishal/text-to-handwriting-streamlit/renderer.py`
  - Downloads external fonts directly at runtime using `urllib.request.urlretrieve` (lines 47-52).
  - Renders lines word-by-word onto a transparent RGBA PIL Image using `draw.text` (lines 199-232).
  - Generates page backgrounds and tiles "PREVIEW" watermarks if `is_paid` is False.
  - Combines text and backgrounds in parallel with `ThreadPoolExecutor`.

- **File Path**: `/home/vishal/text-to-handwriting-streamlit/payments.py`
  - Integrates with the Razorpay API to generate payment links:
    ```python
    rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    ...
    payment_link = rzp_client.payment_link.create(payment_data)
    ```

- **File Path**: `/home/vishal/text-to-handwriting-streamlit/utils.py`
  - Extracts raw unformatted text from PDFs using PyMuPDF (`fitz`):
    ```python
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        ...
        text.append(page.get_text("text"))
    ```

- **File Path**: `/home/vishal/text-to-handwriting-streamlit/ORIGINAL_REQUEST.md`
  - Defines the core requirements: Monetization & Auth (R1), AI & Output Enhancements (R2), and UX & Performance (R3).

---

## 2. Logic Chain

- **R1. Authentication & Wallet**: Since there is no user management in the codebase, we must integrate Supabase Auth. Because Streamlit is single-page and session-based, keeping session tokens in `st.session_state` is appropriate. Adding a `profiles` table in Supabase tracking `credits` enables a wallet-based billing system, where high-res generation deducts credits on a per-page basis.
- **R2. Letter Variability**: Standard font rendering produces identical glyph arrays for duplicate letters. By refactoring the renderer to render character-by-character with random small rotations ($\theta \in [-1.5^\circ, 1.5^\circ]$), vertical baseline offsets ($\Delta y \in [-1, 1]$ pixels), and kerning spacing jitters, each generation is guaranteed to produce mathematically non-identical pixel arrays.
- **R3. Formatting Retention**: Using PyMuPDF's plain text extractor discards font weights and styles. By changing to `page.get_text("dict")`, we can identify bold spans (by flag or font name) and headers (by font size). Converting them into Markdown (`**bold**` and `# Heading`) allows standard editing in the manual text area and parsed rendering via 3-pass stroke bolding and scaling.
- **R4. Sketch-like Styling**: Custom drawings are currently pasted directly as color strokes. By feeding the drawing canvas array into a local OpenCV pencil sketch filter (`cv2.pencilSketch`), we satisfy the requirement for sketch-like styling of diagrams using only local libraries.
- **R5. Instant Previews & Backgrounds**: Full document generation is too slow for real-time slider updates. Creating a fast thumbnail renderer that draws only the first paragraph on a smaller scale background provides immediate feedback. Moving multi-page generation to a Python generator allows real-time rendering status updates via Streamlit's `st.progress` bar.

---

## 3. Caveats

- **External Network Restrictions**: Since the agent operates in `CODE_ONLY` network mode, external fonts downloads and API calls are not executed during investigation. Font caching is assumed to succeed locally at runtime.
- **Supabase/Razorpay Configuration**: For unit testing (`test_auth.py`), we assume a mock/local mode will be activated when secrets are not populated, to ensure local builds pass cleanly.
- **Performance Tradeoff**: Character-by-character drawing takes more execution steps than word-by-word drawing, but the overall time will remain small enough (< 100ms per page preview), especially when parallelized.

---

## 4. Conclusion

The existing codebase is highly modularized, making it straightforward to plug in the new SaaS components.
- **Supabase Auth & Razorpay Credit Wallet** will be implemented using a unified client framework with mock fallbacks.
- **AI Formatting & Character Variance** will be resolved by character-level rendering with random transformations and PyMuPDF dict parsing.
- **Instant Previews & Progress Bars** will be resolved via a dedicated preview renderer and a page-by-page rendering generator.

We have proposed a technical architecture, detailed milestones, and explicit function/database contracts in `analysis.md`.

---

## 5. Verification Method

To verify the findings and proposed contracts:
1. Inspect the detailed system architecture, contracts, and milestones in `/home/vishal/text-to-handwriting-streamlit/.agents/explorer_m1_1/analysis.md`.
2. Verify that `app.py`, `renderer.py`, `payments.py`, and `utils.py` are mapped properly and their integration paths defined.
3. Validate that once implemented, the `test_auth.py` test suite will be able to execute clean verification of the wallet deduction logic.
