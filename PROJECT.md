# Project: Text-to-Handwriting SaaS Upgrade

## Architecture
The application is structured as a Streamlit frontend with backend processing modules:
1. **`app.py`**: Streamlit frontend. Orchestrates the wizard form, user session state, Supabase auth/wallet UI, and background task progress bar polling.
2. **`supabase_client.py`**: Handles connection to Supabase for authentication (sign up, sign in, sign out) and persistent database ledger checks (profiles, transactions).
3. **`payments.py`**: Razorpay integrations. Handles creation of credit-package payment links and verification.
4. **`renderer.py`**: Core rendering engine. Generates handwriting pages using character-by-character drawing with rotation/offset jitter, supports Markdown token rendering (bolding via PIL stroke/multidraw and headers via scale factor), and filters images/drawings using OpenCV pencil sketch filters.
5. **`utils.py`**: Layout parsing and text extraction. Uses PyMuPDF's `page.get_text("dict")` to extract layout blocks, retaining headers (`#`) and bold elements (`**bold**`).
6. **`tasks.py`**: Thread-safe background generator tracking. Runs rendering jobs asynchronously and updates state.

## Code Layout
- `app.py` - Frontend UI and session state coordinator.
- `renderer.py` - Rendering algorithm, character-level transformations, markdown token styling, and sketch filters.
- `utils.py` - PDF/Docx/Txt text extraction with formatting detection.
- `payments.py` - Razorpay billing logic.
- `supabase_client.py` - Database profile and transaction tracking, user authentication client.
- `tasks.py` - Background task runner & progress monitor.
- `test_auth.py` - Authentication and billing validation tests.
- `requirements.txt` - Python project dependencies (includes supabase, opencv-python, PyMuPDF, etc.).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Exploration & Architecture | Codebase exploration, design architecture and interfaces | None | DONE |
| 2 | Auth & Wallet System | Supabase authentication, database schema, credit packages, payments, and `test_auth.py` | M1 | DONE (af893b1e-ab43-4642-ab18-ddf51619fde8) |
| 3 | AI & Output Enhancements | Character-level jitter/variance, PDF bold/header retention, OpenCV sketch filter | M2 | IN_PROGRESS (170b1e5c-5d1c-4bcf-a792-65beff754d83) |
| 4 | UX & Performance | Live thumbnail auto-previews, background processing task runner and UI progress bar | M3 | PLANNED |
| 5 | E2E Verification & Auditing | Verification of variance, bolding, preview latency, and integrity forensics | M4 | PLANNED |

## Interface Contracts

### `supabase_client.py` ↔ `app.py`
- `class SupabaseAuthClient(url: str, key: str, use_mock: bool = False)`
  - `sign_up(email, password) -> dict`: Returns `{'success': bool, 'user_id': str, 'error': str}`
  - `sign_in(email, password) -> dict`: Returns `{'success': bool, 'session': dict, 'error': str}`
  - `sign_out() -> None`
- `class SupabaseWalletClient(url: str, key: str, use_mock: bool = False)`
  - `get_balance(user_id) -> int`: Returns current credit balance.
  - `deduct_credits(user_id, amount) -> bool`: Deducts `amount` credits. Returns `True` if success, `False` if insufficient.
  - `add_credits(user_id, amount, payment_link_id) -> bool`: Logs transaction and updates balance.

### `payments.py` ↔ `app.py`
- `create_credit_payment_link(amount_paise: int, credits: int, user_email: str) -> Tuple[Optional[str], Optional[str]]`: Generates Razorpay payment link. Returns `(payment_link_id, payment_url)`.
- `verify_payment_link(link_id: str) -> bool`: Returns `True` if completed, `False` otherwise.

### `utils.py` ↔ `app.py`
- `extract_formatted_text_from_pdf(uploaded_file) -> str`: Reads PDF via PyMuPDF dict structure and returns formatted Markdown text with `#` and `**` markup.

### `renderer.py` ↔ `app.py` / `tasks.py`
- `parse_markdown_line(line: str) -> List[Dict[str, Any]]`: Returns list of tokens (text, bold flags, header flags).
- `apply_sketch_effect(image: PIL.Image) -> PIL.Image`: Applies OpenCV sketch-like pencil filter.
- `render_handwriting_cached(...) -> Tuple[List[PIL.Image], float]`: Main rendering method, supporting:
  - `is_preview: bool`: If `True`, renders only the first page's first 3-4 lines without rotations for <100ms response time.
  - `messiness: str`: Dictates range of character rotation jitter and baseline shifts.

### `tasks.py` ↔ `app.py`
- `BACKGROUND_TASKS: dict`: Thread-safe registry mapping `task_id` to its status/progress.
- `start_background_generation(task_id, text, settings, user_id)`: Spawns thread to render handwriting.
- `get_task_status(task_id) -> dict`: Returns `{'status': str, 'progress': int, 'total': int, 'images': list, 'error': str}`.
