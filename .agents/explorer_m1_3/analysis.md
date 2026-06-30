# Technical Analysis and SaaS Architecture Proposal

## 1. Executive Summary
This report outlines the technical architecture, milestones, and interface contracts for upgrading the Text-to-Handwriting Streamlit application into a commercial SaaS platform. The upgrade integrates:
- **Supabase Authentication** & a Postgres-backed **Credit Wallet**.
- **Razorpay Credit Purchases** replacing per-document payment flows.
- **Local AI Letter Variance** (rotation, scaling, baseline jitter per letter) and an **OpenCV Sketch Filter** for diagrams.
- **PDF Bold Formatting Retention** via PyMuPDF dict/span extraction.
- **UX Enhancements**: Instantaneous auto-previews (thumbnail generation) and background generation with smooth progress tracking.

---

## 2. Current Codebase Structure & Flow Analysis

The current application consists of four primary Python scripts:
1. **`app.py`**: Streamlit-based UI controller. Manages state using `st.session_state` (wizard steps, generated images, payment state). Uses `st_canvas` for diagrams and triggers the render and payment verification flows.
2. **`renderer.py`**: Performs handwriting rendering. Downloads fonts on-demand from Google Fonts, sets up paper backgrounds, uses PIL `ImageDraw` to draw text, and composites watermark/textures. It utilizes a `ThreadPoolExecutor` for parallelizing the rendering of backgrounds and textures.
3. **`payments.py`**: Integrates with Razorpay SDK to create payment links and query status. It is initialized using secrets (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`).
4. **`utils.py`**: Helper function to extract plain text from uploaded `.txt`, `.docx`, and `.pdf` (using PyMuPDF `fitz`).

### ⚠️ Current Architectural Issues & Limitations
* **Tight Coupling to State Hash**: Payments are validated against a checksum hash of the generated text and settings. Changing even one character invalidates the payment, forcing the user to pay again.
* **No Authentication**: Anyone can access the app; there is no persistent user profile, transaction ledger, or credit balance.
* **Coarse Jitter**: Messiness jitter is applied to the *entire word* rather than individual letters, meaning letters are drawn linearly, and outputs on the same setting are mathematically identical when messiness is set to "Perfect".
* **Loss of PDF Formatting**: PDF extraction uses `page.get_text("text")`, stripping away bold headings and font weight markers.
* **Synchronous UI Blocking**: Large document rendering blocks the main Streamlit thread, which can cause session timeouts and prevents updating the UI dynamically.

---

## 3. Proposed SaaS Technical Architecture

### A. Authentication & Credit Wallet System (Supabase)
We will introduce Supabase to manage user accounts and wallet credits.

#### 1. Database Schema
We will create the following tables and functions in Supabase:

```sql
-- Profiles table linked to auth.users
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    credits INTEGER DEFAULT 5 CONSTRAINT credits_nonnegative CHECK (credits >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Row Level Security (RLS) for Profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own profile" ON public.profiles FOR SELECT USING (auth.uid() = id);
-- Write permissions are restricted. Wallet adjustments MUST go through secure DB functions.

-- Transaction Log for Audit/Razorpay Verification
CREATE TABLE public.transactions (
    id TEXT PRIMARY KEY, -- Razorpay Payment Link ID
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    amount_paise INTEGER NOT NULL,
    credits_added INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL, -- 'pending', 'paid', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own transactions" ON public.transactions FOR SELECT USING (auth.uid() = user_id);

-- Credit History for tracking deductions and top-ups
CREATE TABLE public.credit_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    amount INTEGER NOT NULL,
    action TEXT NOT NULL, -- 'purchase', 'deduction', 'refund'
    reference_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

ALTER TABLE public.credit_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own credit history" ON public.credit_history FOR SELECT USING (auth.uid() = user_id);
```

#### 2. Secure Credit Deduction RPC
To prevent client-side credit tampering, credits will be deducted via a secure Postgres function running with `SECURITY DEFINER` (admin privileges) but constrained by the caller's verified JWT session (`auth.uid()`).

```sql
CREATE OR REPLACE FUNCTION public.deduct_credits(amount_to_deduct INTEGER, document_name TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    current_balance INTEGER;
BEGIN
    SELECT credits INTO current_balance FROM public.profiles WHERE id = auth.uid();
    
    IF current_balance IS NULL THEN
        RAISE EXCEPTION 'Profile not found.';
    END IF;
    
    IF current_balance < amount_to_deduct THEN
        RETURN FALSE;
    END IF;
    
    -- Deduct credits
    UPDATE public.profiles
    SET credits = credits - amount_to_deduct, updated_at = NOW()
    WHERE id = auth.uid();
    
    -- Log into history
    INSERT INTO public.credit_history (user_id, amount, action, reference_id)
    VALUES (auth.uid(), -amount_to_deduct, 'deduction', document_name);
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

#### 3. Client Integration Flow
1. Streamlit presents a login/register sidebar form using the `supabase` package.
2. Upon login, the session token (JWT) is stored in `st.session_state.supabase_client`.
3. High-res document generation is enabled if the user has `credits >= total_pages`.
4. Upon clicking "Generate", the Streamlit backend calls the `deduct_credits` RPC. If it succeeds, the high-res generation is executed. Otherwise, it defaults to a watermarked preview.

---

### B. Credit Purchase (Razorpay Integration)
Instead of pay-per-page, users purchase credit packages (e.g. 10 credits for INR 100).
1. The user clicks "Buy 10 Credits".
2. The Streamlit backend calls `payments.py:create_payment_link(10000, "10 Handwriting Credits")`.
3. It inserts a pending transaction row in the `transactions` table using a service role client to ensure database integrity.
4. Once paid, the user clicks "Verify Payment". The backend checks Razorpay's status. If verified, the backend credits the user's account using the service role client and updates the transaction status to `'paid'`.

---

### C. Local AI Letter Variance & Bold Formatting (OpenCV/PIL)

#### 1. Algorithmic Letter Variability
Instead of rendering word-by-word, the renderer will render character-by-character and inject microscopic variations on each individual character:
* **Position Shift (`dx`, `dy`)**: Add slight offsets to baseline coordinate.
* **Rotation (`angle`)**: Draw the character in a temporary canvas, rotate it using `Image.rotate()` by a small random angle, and paste it.
* **Scale/Size Variation**: Slightly adjust font size or scale the resulting character image.
* **Spacing/Kerning Jitter**: Add randomized kerning adjustments after drawing each letter.

This guarantees that two runs with the identical settings produce mathematically non-identical pixel arrays.

#### 2. Sketch-like Drawing filter (OpenCV)
When drawing diagrams on the canvas, we will apply an OpenCV filter to give it a natural shaky, textured look (like pencil sketch or organic ink):
* **Coordinate Remapping**: Use a displacement grid perturbed by Gaussian-blurred noise to introduce small physical wiggles to lines.
* **Morphology**: Vary stroke weights by applying morphological dilation/erosion.
* **Texture Compositing**: Blend the strokes with low-opacity noise to mimic pen/pencil pressure texture.

#### 3. Formatting-Aware PDF Extraction & Rendering
We will rewrite PDF extraction to fetch spans from blocks using PyMuPDF:
* Identify bold spans if `span["flags"] & 16` or if `"bold"` is in `span["font"].lower()`.
* Wrap bold spans in markdown tags: `**bold text**`.
* The renderer splits text by bold tags. For bold segments, it uses PIL's `draw.text` with `stroke_width = max(1, int(font_size * 0.05))` and `stroke_fill = ink_color` to draw a thicker weight.

---

### D. UX & Performance

#### 1. Fast Thumbnail Preview
* Introduce a `preview_mode` in `render_handwriting_cached`.
* If `preview_mode=True`, the renderer only processes the first page (or first 150 words), disables texture processing, and uses a simplified rendering loop.
* The thumbnail is rendered reactively in the UI whenever wizard settings are updated, bypassing the payment check and full-page layout calculations.

#### 2. Background Generation & Live Progress
* When a user generates a document, the task is executed in a background `threading.Thread`.
* The task progress is recorded in a shared global task map.
* In the Streamlit UI, a loop monitors the task state. It displays a progress bar (`st.progress`) and text updates, executing `time.sleep(0.5)` and `st.rerun()` to refresh the dashboard until the generation is complete.

---

## 4. Implementation Milestones

```
+-----------------------------------------------------------------------------+
| Milestone 1: Supabase Setup & Authentication (Day 1-2)                      |
| - Create Supabase project & configure schema (profiles, transactions, logs).|
| - Write deduct_credits RPC.                                                 |
| - Implement Login/Signup sidebar in app.py.                                 |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Milestone 2: Wallet System & Razorpay Packages (Day 3)                      |
| - Configure Razorpay top-ups with credit package options.                   |
| - Implement transaction verification and service-role database crediting.   |
| - Build test_auth.py to verify auth & credits lock mechanics.               |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Milestone 3: Local AI & Rendering Upgrade (Day 4-5)                         |
| - Implement letter-by-letter rendering with rotation, scale, position jitter.|
| - Build OpenCV sketch styling filter for drawing canvas.                    |
| - Implement PDF bold-preserving parser & thicker stroke rendering.          |
+-----------------------------------------------------------------------------+
                                      |
                                      v
+-----------------------------------------------------------------------------+
| Milestone 4: Instant Previews & Background Processing (Day 6)              |
| - Add preview_mode to renderer for fast thumbnail generation.               |
| - Implement threading worker for background document generation.            |
| - Connect live Streamlit progress bar.                                      |
+-----------------------------------------------------------------------------+
```

---

## 5. Interface Contracts

### A. Database Interfaces (Supabase RPCs)
* `public.deduct_credits(amount_to_deduct int, document_name text) -> boolean`
* `public.add_credits_via_payment(payment_link_id text) -> boolean`

### B. PDF Formatting Utility (`utils.py`)
```python
def extract_text_from_file(uploaded_file: Any) -> str:
    """
    Extracts text from txt, docx, or pdf.
    If pdf, extracts formatting (spans) and wraps bold segments in '**' tags.
    """
```

### C. OpenCV Sketch Filter (`renderer.py`)
```python
def apply_sketch_style(image_data: np.ndarray, ink_color_rgb: Tuple[int, int, int]) -> Image.Image:
    """
    Applies vector coordinate remapping and morphology using OpenCV 
    to convert canvas drawings into natural sketchy strokes.
    """
```

### D. Handwriting Renderer (`renderer.py`)
```python
def render_handwriting_cached(
    text: str, 
    font_size: int, 
    ink_color: str, 
    paper_style: str, 
    custom_bg: Optional[bytes], 
    messiness: str, 
    margins: Tuple[int, int, int, int], 
    page_size: Tuple[int, int], 
    line_spacing_factor: float, 
    apply_texture: bool, 
    is_paid: bool, 
    mistake_prob: float, 
    font_choice: Optional[str] = None, 
    custom_font_bytes: Optional[bytes] = None, 
    max_pages: int = 50,
    preview_mode: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None
) -> Tuple[List[Image.Image], float]:
    """
    Renders text using letter-by-letter drawing.
    - Applies character-level jitter (position, angle, scale, kerning).
    - Checks for bold tags '**' and applies stroke_width/stroke_fill.
    - Returns list of PIL Images (only 1 if preview_mode is True).
    - Reports progress through progress_callback.
    """
```

### E. Background Processing Task (`app.py`)
```python
class DocumentGenerationTask:
    def __init__(self, text: str, settings: dict):
        self.id: str = str(uuid.uuid4())
        self.text: str = text
        self.settings: dict = settings
        self.progress: float = 0.0
        self.status: str = "queued"  # "queued", "processing", "completed", "failed"
        self.images: List[Image.Image] = []
        self.error: Optional[str] = None
```
