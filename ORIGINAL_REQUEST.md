# Original User Request

## Initial Request — 2026-06-30T17:00:56+05:30

Upgrade the existing Text-to-Handwriting Streamlit application into a full-fledged SaaS platform with user authentication, a wallet/subscription system, AI-enhanced handwriting variance, and background processing.

Working directory: /home/vishal/text-to-handwriting-streamlit
Integrity mode: development

## Requirements

### R1. Monetization & Authentication
Integrate Supabase for user authentication. Implement a credit/wallet system where users can purchase credits via Razorpay to generate documents.

### R2. AI & Output Enhancements
Use local Python libraries (like OpenCV and PIL) to introduce realistic letter variability and sketch-like styling for hand-drawn diagrams (no external APIs). Ensure text formatting (bolding/headers) from uploaded PDFs is retained in the final handwriting output.

### R3. UX & Performance
Implement instantaneous auto-previews within the chat setup so users see settings changes immediately without waiting for the full document. Add a progress bar and background processing mechanism for handling large document generations smoothly.

## Acceptance Criteria

### Authentication & Billing
- [ ] `test_auth.py` (to be written by the team) passes, proving a dummy user can be created, credits can be deducted, and generation is blocked when balance is zero.

### Output & AI Enhancements
- [ ] Generating the same document twice with the exact same settings yields two mathematically non-identical image arrays (proving true algorithmic letter variability is active).
- [ ] Extracted text from a test PDF with bold text successfully renders with a thicker font-weight or corresponding bold font in the handwriting output.

### UX & Performance
- [ ] The app renders a fast thumbnail preview instantly when chat settings change, bypassing the full multi-page generation loop.
