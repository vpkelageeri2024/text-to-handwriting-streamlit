# Codebase Analysis & SaaS Upgrade Architecture Proposal

## 1. Existing Codebase Analysis

The current **Text-to-Handwriting Streamlit** application allows users to upload documents or type manual text, customize handwriting options through a guided chat interface, optionally add drawings, and export generated handwritten images (either with a watermark or high-res paid export).

### Module Interactions
- **`app.py`**: The central Streamlit application orchestrating the UI/UX. It manages the chat-wizard state, captures user settings (font, paper, ink color, messiness), renders the canvas diagram drawing interface, verifies payment state using a hash of the settings, coordinates execution, and shows options for downloading ZIPs/PDFs.
- **`renderer.py`**: The rendering engine.
  - Downloads Google Fonts at runtime (caching them locally in `fonts/`).
  - `create_background` draws the selected paper template (Ruled, College Ruled, Yellow Legal, Dot Grid, Graph, Parchment) and applies a tiling "PREVIEW" watermark if the page is unpaid.
  - `process_page` composite the text layer onto the template and applies an optional pixel-level noise texture.
  - `render_handwriting_cached` splits the raw text into words, iterates through them, handles wrapping based on character widths, and draws them onto a transparent RGBA layer. It supports a rudimentary mistake model (crossing out text) and wobbliness (jittering the coordinates). It parallelizes page generation via `ThreadPoolExecutor`.
- **`payments.py`**: Integration with Razorpay. It provides `create_payment_link` to create a one-off payment link per document and `check_payment_status` to poll link payment status.
- **`utils.py`**: Utility module for document text extraction. It reads `.txt`, `.docx`, and `.pdf` files. It uses PyMuPDF (`fitz`) to extract raw plain text from PDFs.

---

## 2. SaaS Upgrade Technical Architecture

We propose upgrading the architecture into a secure, scalable, credit-based SaaS platform. Below is the technical details for each subsystem.

```
                  ┌──────────────────────────────────────────────┐
                  │                Streamlit UI                  │
                  └──────────────┬────────────────┬──────────────┘
                                 │                │
      ┌──────────────────────────▼───┐        ┌───▼──────────────────────────┐
      │     Monetization & Auth      │        │    AI & Rendering Engine     │
      │  (Supabase Auth & Database)   │        │     (PIL, OpenCV, PyMuPDF)   │
      └──────────────┬───────────────┘        └──────────────┬───────────────┘
                     │                                       │
     ┌───────────────▼───────────────┐       ┌───────────────▼───────────────┐
     │      Razorpay Wallet API      │       │ Character-Level Jitter / Bold │
     │  (Credit Packs & Wallet Tx)   │       │   Markdown Parser Renderer    │
     └───────────────────────────────┘       └───────────────┬───────────────┘
                                                             │
                                             ┌───────────────▼───────────────┐
                                             │    Background Generator &     │
                                             │   Instant Thumbnail Preview   │
                                             └───────────────────────────────┘
```

### R1. Monetization & Authentication (Supabase & Razorpay)

#### Database Schema (Supabase)
1. **`profiles`** (Public user profiles, linked to Supabase auth):
   - `id`: UUID (Primary Key, references `auth.users.id` on delete cascade)
   - `email`: Text
   - `credits`: Integer (default: 10, free trial credits)
   - `updated_at`: Timestamp
2. **`transactions`** (Logs wallet credit history):
   - `id`: UUID (Primary Key)
   - `user_id`: UUID (references `profiles.id`)
   - `amount_paise`: Integer
   - `credits_added`: Integer
   - `status`: Text (`pending`, `completed`, `failed`)
   - `razorpay_payment_id`: Text (nullable)
   - `created_at`: Timestamp

#### User Auth & Wallet Flow
- **Session State**: Store Supabase session tokens in `st.session_state`.
- **Auth UI**: Implement a simple Sidebar / Tab login/signup system.
- **Credit Purchases**:
  - Instead of direct pay-per-document, users buy credits in packages (e.g. 50 credits = ₹50, 100 credits = ₹80).
  - Razorpay payment link is generated for a chosen package.
  - Users click the link, and complete payment. Streamlit polls or the user verifies via a button, updating transaction status and user balance.
- **Deduction Rule**: Generating a high-resolution export costs 1 credit per page. Preview generation remains free. Balance is updated in the database on high-res generation, blocking execution if the user has 0 credits.
- **Mock Mode**: To facilitate CI/CD testing without real keys, we will implement a mock client wrapper that activates when real credentials are absent.

### R2. Output & AI Enhancements

#### Realistic Letter Variability
Currently, the renderer renders text word-by-word. We will refactor this to draw **character-by-character** on the canvas, introducing fine-grained algorithmic variability to each character:
1. **Rotation Jitter**: Each character image is rendered in isolation, rotated by a random small angle $\theta \sim \text{Uniform}(-1.5^\circ, 1.5^\circ)$, and then pasted.
2. **Baseline Offset**: Shift each character vertically by $\Delta y \sim \text{Uniform}(-1, 1)$ pixels.
3. **Spacing Jitter**: Randomize kerning spacing slightly: $\Delta x \sim \text{Uniform}(-0.5, 0.5)$ pixels.
4. **Thickness / Opacity Variation**: Slightly randomize stroke alpha/thickness per character.
This algorithmic character modification guarantees that rendering the same text twice will produce mathematically non-identical images (satisfying the acceptance criteria).

#### Text Formatting & Header Retention
- **PyMuPDF Dict Extraction**: Modify `utils.py` to call `page.get_text("dict")`.
- **Markdown Mapping**: Extract formatting details:
  - Spans with font size $> 1.2 \times$ baseline are converted to Headers (`#` or `##`).
  - Spans with bold flags/font names containing `Bold`, `Black`, `Heavy`, etc. are wrapped in double asterisks (`**bold**`).
- **Markdown Parser in Renderer**:
  - The renderer parses headings (scaling `font_size` by 1.3x) and bold text (`**`).
  - Since we don't have separate bold fonts for all handwriting TTFs, we will implement a **3-pass offset drawing** technique for bold text (drawing the character at $(x, y)$, $(x+1, y)$, and $(x, y+1)$) which mimics ink bleeding/thicker strokes beautifully.

#### Sketch-like Styling for Diagrams
- Run the drawing canvas image through a local OpenCV pipeline to simulate pencil sketch details:
  ```python
  def apply_sketch_filter(canvas_image_data: np.ndarray) -> np.ndarray:
      # Convert RGBA to BGR
      bgr = canvas_image_data[:, :, :3]
      alpha = canvas_image_data[:, :, 3]
      # Apply OpenCV pencil sketch
      dst_gray, dst_color = cv2.pencilSketch(bgr, sigma_s=50, sigma_r=0.07, shade_factor=0.03)
      # Re-apply alpha channel to render on handwriting page background
      ...
  ```

### R3. UX & Performance

#### Instant Thumbnail Previews
- When a user changes settings in the wizard, we immediately render a **single-page thumbnail (first 3-4 lines of text)**.
- We skip the full text wrap and multi-page layout loop.
- The thumbnail is scaled down (e.g. 50% size) for rapid display, updating instantly (< 50ms) to provide real-time style feedback.

#### Background Generation
- For full documents (which can contain multiple pages), we wrap the generation logic in a **Python generator**.
- This yields intermediate progress percentages:
  ```python
  def render_handwriting_generator(...) -> Generator[Tuple[Image.Image, float], None, None]:
      # Loop through pages
      # Yield current page and progress percentage
  ```
- The Streamlit front-end consumes this generator, updating `st.progress(...)` in real-time, giving the user immediate visual feedback of the generation queue.

---

## 3. List of Milestones

| Milestone | Title | Focus Area | Deliverables |
|---|---|---|---|
| **M1** | Exploration & Architecture | Planning & Investigation | Codebase analysis, architecture design, interface contracts (`analysis.md`, `handoff.md`). |
| **M2** | Monetization & Authentication | Auth, Supabase, Razorpay | Supabase database integration, authentication tabs, credit wallet UI, Razorpay credit packages, and `test_auth.py` passing with mock support. |
| **M3** | Core AI & Formatting | Letter Variance, PDFs, Sketch | Character-by-character jitter, PDF formatting (bold/headers) mapping, simulated bold rendering, OpenCV sketch filters. |
| **M4** | UX & Performance | Previews, Progress Bars | Fast single-page settings-change preview, generator-based progress reporting. |
| **M5** | Integration & Quality | E2E Verification & Build | Full system testing, linting fixes, layout checks, final documentation, and demo. |

---

## 4. Interface Contracts

### A. Supabase Client Wrapper (`supabase_client.py`)
```python
import supabase
from typing import Dict, Any, Optional

class SupabaseAuthClient:
    def __init__(self, url: str = None, key: str = None, use_mock: bool = False):
        """Initializes the Supabase client or activates mock mode."""
        self.use_mock = use_mock
        # Initialize Supabase client if not use_mock
        ...
        
    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        """Registers a new user, automatically initializing 10 free credits."""
        ...
        
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Signs in a user and returns session data."""
        ...
        
    def sign_out(self) -> None:
        """Clears the session."""
        ...

class SupabaseWalletClient:
    def get_balance(self, user_id: str) -> int:
        """Retrieves credit balance for the user."""
        ...
        
    def deduct_credits(self, user_id: str, amount: int) -> bool:
        """Deducts credits upon successful high-res document export. Returns True if successful."""
        ...
        
    def add_credits(self, user_id: str, amount: int, payment_id: str) -> bool:
        """Adds purchased credits to the profile. Logs transaction details."""
        ...
```

### B. Razorpay Integration Enhancements (`payments.py`)
```python
def create_credit_payment_link(amount_paise: int, credits: int, user_email: str) -> Tuple[Optional[str], Optional[str]]:
    """Generates a Razorpay payment link for buying a credit package."""
    ...

def verify_payment_link(link_id: str) -> bool:
    """Verifies with Razorpay if the link has been completed."""
    ...
```

### C. PDF Parser with Formatting Retention (`utils.py`)
```python
from typing import List, Dict, Any

def extract_formatted_text_from_pdf(uploaded_file: Any) -> str:
    """
    Extracts text from PDF, mapping font attributes to Markdown tags:
    - Bold fonts/flags -> **bold**
    - Headings/large fonts -> # Heading
    """
    ...
```

### D. Handwriting Renderer Modifications (`renderer.py`)
```python
from PIL import Image
from typing import List, Tuple, Generator, Optional

def render_handwriting_generator(
    text: str, 
    font_size: int, 
    ink_color: str, 
    paper_style: str, 
    messiness: str, 
    margins: Tuple[int, int, int, int], 
    page_size: Tuple[int, int],
    # ... existing params ...
) -> Generator[Tuple[Image.Image, float], None, None]:
    """
    Yields (rendered_page_image, progress_percentage) iteratively.
    - Processes text rendering character-by-character with physical jitter.
    - Supports Markdown bolding (**text**) using a 3-pass draw process.
    - Supports headers (#) by increasing scale by 1.3x.
    """
    ...

def render_thumbnail(
    text: str,
    font_choice: str,
    ink_color: str,
    paper_style: str,
    messiness: str
) -> Image.Image:
    """
    Renders only the first line of text on a smaller scale background.
    Optimized to complete in < 50ms for live settings update previews.
    """
    ...
```
