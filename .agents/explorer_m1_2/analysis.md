# Technical Analysis & Architecture Proposal: SaaS Upgrade

This document outlines the detailed findings from the codebase analysis and provides a complete technical architecture, interface contracts, and implementation milestones for upgrading the Text-to-Handwriting application into a commercial SaaS product.

---

## 1. Existing Codebase Analysis

The application is structured into four main modules:
- **`app.py`**: Streamlit frontend interface. Handles UI structure, multi-step chat setup (font, paper, ink color, messiness selection), canvas drawing, and payment status checks.
- **`renderer.py`**: Core rendering engine. Downloads fonts from Google Fonts, sets up the page backgrounds, writes text line-by-line using PIL's `ImageDraw`, adds noise texture, and watermarks preview images if they are not paid.
- **`payments.py`**: Contains integration helper functions for Razorpay (creation and verification of payment links).
- **`utils.py`**: Helper utility to extract raw text from uploaded TXT, DOCX, and PDF (via PyMuPDF) files.

### Critical Observations & Bottlenecks
1. **Synchronous Rendering (UX Lag)**: Currently, rendering occurs inside the Streamlit session thread. For a multi-page document, this locks the UI. There is no progress bar showing incremental page generation.
2. **Stateless Billing**: Currently, payments are document-based. The application computes a hash of the text and settings (`current_state_id`) and stores whether that specific state has been paid in `st.session_state`. This is highly volatile and doesn't support a user account balance.
3. **No Character Variety**: The renderer draws words using `ImageDraw.Draw.text` with a standard TTF font. Each occurrence of a character (e.g., 'e') is identical, which ruins the realism of the handwriting.
4. **Loss of PDF Formatting**: The `utils.py` text extractor uses `fitz` PyMuPDF's `get_text("text")` which discards font style (bold, weight) and headings.
5. **No Layout Parsing**: There is no built-in Markdown/formatting parser in the rendering engine; styling is currently limited to basic asterisks (`*text*` turns text red).

---

## 2. SaaS Upgrade Technical Architecture

The proposed architecture introduces **Supabase** for user state management, upgrades **Razorpay** to a credit packages model, adds local **AI/OpenCV** image processing for handwriting variance and diagram styling, and implements **background threading** for seamless Streamlit performance.

```
                  ┌───────────────────────┐
                  │     Streamlit UI      │
                  │  (app.py / tasks.py)  │
                  └───────────┬───────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│ Auth & Wallet    ││ Markdown Parser  ││ Background Task  │
│ (supabase-py)    ││ (utils.py)       ││ Engine (tasks.py)│
└─────────┬────────┘└─────────┬────────┘└─────────┬────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│ DB (Profiles &   ││ Text Renderer    ││ Rendering Thread │
│ Transactions)    ││ & OpenCV Sketch  ││ (ThreadPool)     │
└──────────────────┘└──────────────────┘└──────────────────┘
```

### R1. Authentication & Credit Wallet Schema (Supabase)
We will define two database tables in Supabase: `profiles` and `transactions`.

#### `profiles` Table
Stores user profile information and their current wallet balance.
```sql
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  credits integer not null default 0 check (credits >= 0),
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable Row Level Security (RLS)
alter table public.profiles enable row level security;

create policy "Users can view their own profile." on public.profiles
  for select using (auth.uid() = id);

create policy "Users can update their own profile." on public.profiles
  for update using (auth.uid() = id);
```

#### `transactions` Table
Tracks credit purchases via Razorpay to ensure idempotency.
```sql
create table public.transactions (
  id text primary key, -- Razorpay Payment Link ID
  user_id uuid references public.profiles(id) on delete cascade not null,
  amount integer not null, -- amount in paise
  credits_added integer not null,
  status text not null check (status in ('pending', 'completed', 'failed')),
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

alter table public.transactions enable row level security;

create policy "Users can view their own transactions." on public.transactions
  for select using (auth.uid() = user_id);
```

### R2. Algorithmic Letter Variance & Bold Styling (PIL & OpenCV)
To satisfy the requirement of "two mathematically non-identical image arrays" for the same inputs:
1. **Character-Level Transforms**:
   - Rather than rendering full words as strings, the renderer will draw text character-by-character.
   - For each character, we draw it onto a small transparent scratch canvas, apply random transformations using OpenCV or PIL (small rotation `[-2°, 2°]`, scale `[0.98, 1.02]`, and a vertical offset/jitter), and then composite it onto the page.
2. **Text Formatting Extraction**:
   - The PDF extractor will use PyMuPDF's detailed `page.get_text("dict")` structure.
   - It will identify bold spans (by checking `span["flags"] & 2` or font names containing "Bold") and headers (by comparing font sizes against body sizes).
   - The extracted text will be formatted into standard Markdown: `# Header` and `**bold**`.
3. **Markdown Handwriting Renderer**:
   - The rendering engine will parse Markdown tokens.
   - For `# Header`, it will temporarily scale the font size and draw the text line.
   - For `**bold**` text, it will draw the character using PIL's `stroke_width` parameter (e.g. `stroke_width=2`). This renders a thicker font weight naturally.
4. **Sketch-like Diagram Filter**:
   - When drawing canvas images or uploading custom sketches, we will apply an OpenCV pencil sketch effect:
     ```python
     gray = cv2.cvtColor(img_np, cv2.COLOR_RGBA2GRAY)
     inv_gray = 255 - gray
     blurred = cv2.GaussianBlur(inv_gray, (21, 21), 0)
     sketch = cv2.divide(gray, 255 - blurred, scale=256)
     ```

### R3. UX, Previews & Background Processing
1. **Instant Thumbnail Preview**:
   - As the user adjusts settings in the chat wizard, the app automatically triggers a preview render of a short, fixed text (e.g., "The quick brown fox...") or the first page's initial 3 lines.
   - The preview runs with `max_pages=1` and skips character-by-character transformations to ensure sub-100ms response times.
2. **Background Processing Engine**:
   - A thread-safe global registry `BACKGROUND_TASKS` tracks generation progress.
   - When a user submits a document, a background thread is spawned using `threading.Thread`.
   - The user interface polls this state using `st.fragment` (or a short-wait loop) and renders a `st.progress` bar.

---

## 3. Interface Contracts

### 3.1. Authentication & Wallet (`auth_wallet.py`)

```python
import supabase
from typing import Dict, Any, Optional

def get_supabase_client() -> supabase.Client:
    """Initializes and returns the Supabase client using secrets."""
    ...

def sign_up_user(email: str, password: str) -> Dict[str, Any]:
    """Registers a new user and creates an entry in profiles table.
    Returns a dict with 'success' (bool) and 'error' or 'user_id'."""
    ...

def sign_in_user(email: str, password: str) -> Dict[str, Any]:
    """Authenticates user. Returns session data or error."""
    ...

def get_user_credits(user_id: str) -> int:
    """Retrieves user's credit balance from the profiles table."""
    ...

def deduct_user_credits(user_id: str, credits_to_deduct: int) -> bool:
    """Deducts credits from user's balance inside a transaction.
    Returns True if successful, False if insufficient credits."""
    ...

def create_credit_order(user_id: str, package_id: str) -> Dict[str, Any]:
    """Generates a Razorpay payment link for a credit package (e.g. 50 credits for 100 INR)
    and logs a 'pending' transaction in Supabase."""
    ...

def verify_and_credit_wallet(payment_link_id: str) -> bool:
    """Checks Razorpay status for the payment link.
    If paid and transaction is 'pending', updates transaction to 'completed'
    and increments the user's profiles.credits. Returns True if successful."""
    ...
```

### 3.2. File Utilities (`utils.py`)

```python
from typing import Any

def extract_text_from_file(uploaded_file: Any) -> str:
    """Extracts text from files. If PDF, uses page.get_text("dict") to preserve
    bold styles as '**text**' and headers as '# text'."""
    ...
```

### 3.3. Text & Sketch Processing (`renderer.py`)

```python
from PIL import Image, ImageFont
from typing import List, Tuple, Dict, Optional

def parse_markdown_line(line: str) -> List[Dict[str, Any]]:
    """Parses a single line of text into tokens, identifying bold tags and headers.
    Returns: [{'text': 'hello ', 'bold': False, 'header': False}, {'text': 'world', 'bold': True, 'header': False}]"""
    ...

def apply_sketch_effect(image: Image.Image) -> Image.Image:
    """Applies a grayscale OpenCV pencil sketch effect to hand-drawn canvas/images."""
    ...

def draw_char_with_variance(
    draw: Any, 
    char: str, 
    position: Tuple[float, float], 
    font: ImageFont.FreeTypeFont, 
    color: Tuple[int, int, int, int], 
    stroke_width: int,
    messiness: str
) -> Tuple[float, float]:
    """Draws a single character onto a scratch image, applies random rotation/scaling based
    on messiness settings, and pastes it onto the main draw surface.
    Returns the new (x, y) coordinates for the next character."""
    ...

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
    is_preview: bool = False
) -> Tuple[List[Image.Image], float]:
    """Renders the text to page images. If is_preview is True, it generates only
    the first few lines on a single page, skipping heavy OpenCV/PIL transformations
    for maximum responsiveness."""
    ...
```

### 3.4. Background Processor (`tasks.py`)

```python
from typing import Dict, Any

# Global thread-safe registry
BACKGROUND_TASKS: Dict[str, Dict[str, Any]] = {}

def start_background_generation(task_id: str, text: str, settings: Dict[str, Any], user_id: str) -> None:
    """Spawns a background thread that deducts credits (if not preview), 
    runs render_handwriting_cached, and stores images in BACKGROUND_TASKS."""
    ...

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Retrieves current progress and status of a task:
    { "status": "processing"|"completed"|"failed", "progress": 2, "total": 10, "images": [...], "error": None }"""
    ...
```

---

## 4. Implementation Milestones

### Milestone 1: Database Setup & Authentication Integration
- Set up local/hosted Supabase tables (`profiles`, `transactions`) and trigger logic.
- Integrate `supabase-py` package.
- Build sidebar login/signup components in `app.py`.
- Write `test_auth.py` to verify:
  - Account registration.
  - Credit initialization.
  - Verification that generation is blocked at `credits == 0`.

### Milestone 2: Credit Wallet & Razorpay Lifecycle
- Modify `payments.py` to support credit package structures rather than raw file transactions.
- Implement `verify_and_credit_wallet` handler.
- Integrate balance check and credit deduction flow into the document generation loop.
- Hook verification checks into the Streamlit session flow (allowing manual/automatic credit refresh).

### Milestone 3: Algorithmic Variance & Markdown PDF Extraction
- Implement PyMuPDF `get_text("dict")` parsing in `utils.py` to extract headings and bold runs into Markdown tags.
- Update `renderer.py` to support Markdown text tokenization.
- Add character-by-character PIL layout rendering with random affine transformations (rotation, scaling, noise) and baseline shift based on messiness levels.
- Add sketch filter option using OpenCV to make canvas inputs and uploaded drawings look sketch-like.

### Milestone 4: Instant Previews & Background Processing
- Build `is_preview` fast rendering path into `renderer.py` (skips letter rotations, renders max 1 page).
- Update chat setup UI to trigger and show this fast preview dynamically upon any parameter modification.
- Implement background threading and status tracking in `tasks.py`.
- Add an animated progress bar in `app.py` for long generations, polling the background task thread.

### Milestone 5: Verification & End-to-End Testing
- Validate that two sequential generations with the same settings produce mathematically different arrays (using structural similarity indices or simply pixel-wise difference hashes).
- Run the full test suite (`test_auth.py` and regression tests) to verify correctness.
