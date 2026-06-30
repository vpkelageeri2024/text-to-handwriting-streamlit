# Handoff Report — Explorer 3 Codebase Analysis & SaaS Upgrade Architecture

## 1. Observation
During the investigation of `/home/vishal/text-to-handwriting-streamlit/`, the following aspects of the current codebase were observed:
- **Per-document Hashing**: In `app.py` lines 233-235:
  ```python
  state_str = text_input + str(font_size) + str(paper_style) + str(messiness) + str(margins) + (str(canvas_result.json_data) if not is_canvas_empty else "") + str(mistake_prob)
  current_state_id = hashlib.md5(state_str.encode()).hexdigest()
  is_paid = st.session_state.get('paid_state_id') == current_state_id
  ```
  Payment status is tightly coupled to the exact input and settings state hash.
- **Word-Level Messiness**: In `renderer.py` lines 220-222:
  ```python
  dy = random.uniform(-jitter_amp, jitter_amp) if jitter_amp > 0 else 0
  dx = random.uniform(-jitter_amp/2, jitter_amp/2) if jitter_amp > 0 else 0
  draw.text((x + dx, y + dy), w_text, fill=fill_color, font=font_obj)
  ```
  Jitter is applied uniformly to whole words (`w_text`), and outputs remain mathematically identical if messiness is "Perfect" (since `jitter_amp = 0` and `mistake_prob = 0.0`).
- **Plain Text PDF Extraction**: In `utils.py` lines 21-27:
  ```python
  with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
      text = []
      for page in doc:
          text.append(page.get_text("text"))
      return "\n".join(text)
  ```
  Text formatting (bold weights, header flags) is discarded during parsing.
- **Synchronous Rendering**: In `app.py` line 237, the script calls `render_handwriting_cached` synchronously inside the Streamlit page thread, which blocks the UI thread until generation finishes.
- **Dependencies**: In `requirements.txt`, standard SaaS dependencies like `supabase` and local image processing libraries like `opencv-python-headless` are missing.

---

## 2. Logic Chain
- **Wallet and Auth Upgrade**: Because the current payment logic verifies `paid_state_id == current_state_id` (Observation: `app.py` lines 233-235), any small change requires a new payment. Integrating Supabase Auth and a persistent credits wallet decoupling payment from document hash will resolve this.
- **Secure Transaction Enforcement**: Since client-side credit deduction is insecure, we will use a Postgres Database Function (RPC) running `SECURITY DEFINER` inside Supabase to securely deduct credits based on the authenticated session's `auth.uid()`.
- **Character-Level Algorithmic Variability**: Since current jitter is applied on a per-word basis (Observation: `renderer.py` lines 220-222) and yields deterministic outputs when messiness is disabled, we will implement letter-by-letter drawing. Applying micro-perturbations (rotation, scale, displacement) to individual characters guarantees mathematically unique image arrays on every run.
- **Sketch Styling for Drawings**: The drawn diagrams are currently pasted raw. To make them look hand-drawn, we can use OpenCV's coordinate mapping (`remap` with Gaussian-blurred noise) to jitter lines organically, morphological operations to vary line thickness, and alpha-composited noise for pen/pencil texture.
- **Formatting-Aware PDF Extraction**: The current parser drops styling (Observation: `utils.py` lines 21-27). Interrogating span dictionary flags (`span["flags"] & 16`) using PyMuPDF allows us to flag bold content, wrap it in `**` markdown tags, and instruct the renderer to draw them using PIL's native `stroke_width` and `stroke_fill` attributes.
- **UI Responsiveness (Previews & Background Workers)**: Because multi-page generation blocks Streamlit execution, adding a fast rendering path (`preview_mode`) that skips textures and limits generation to the first page enables instantaneous previews on setting changes. Wrapping full generation in python `threading.Thread` and monitoring task progress via a polling UI loop avoids browser timeouts.

---

## 3. Caveats
- No changes have been implemented yet; this is a pure analysis.
- Credit purchases assume Razorpay checkout is verified securely server-side inside the Streamlit backend before calling Supabase API with the service role key.
- CPU saturation may occur during multi-page rendering under heavy concurrency, as PIL and OpenCV are highly CPU-bound. If production traffic scales, this should be offloaded to a queue system (e.g. Celery with Redis).

---

## 4. Conclusion
The proposed architecture provides a clear path for upgrading the application into a SaaS platform. Key tasks involve setting up Supabase schemas and RLS, building the letter-by-letter rendering engine, implementing OpenCV sketch stylization, updating PDF parsing to retain bolding, and configuring background threads with a polling progress indicator.

---

## 5. Verification Method
- **Authentication & Wallet**: Execute `test_auth.py` (mocking Supabase and Razorpay interfaces) to verify user registration, credit balance decrements, and blocking when credits = 0.
- **Letter Variability**: Run a script that renders the same text twice with identical settings and asserts `np.array_equal(img1, img2) == False`.
- **Formatting**: Process a test PDF containing bold headers and verify that corresponding handwritten text renders with thicker lines.
- **UX & Performance**: Verify that modifying setting sliders in the wizard displays a thumbnail preview immediately, and generating a 10-page document renders a real-time progress bar.
