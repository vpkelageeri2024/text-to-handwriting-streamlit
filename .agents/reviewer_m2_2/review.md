# Milestone 2 Review: User Authentication & Credit Wallet System

## Review Summary

**Verdict**: REQUEST_CHANGES

The implementation of the Supabase Authentication and Credit Wallet system conforms structurally to the interface contracts in `PROJECT.md`. The design includes dual-mode operation (real integration vs. mock fallback) which is convenient for local development.

However, several critical and major security vulnerabilities have been identified in the credit wallet transaction ledger and payment processing logic (detailed below). These must be addressed before the code is ready for production.

---

## Quality Review Report

### Findings

#### [Critical] Finding 1: Client-Side Read-Modify-Write Race Condition in Wallet Balance Updates
- **What**: The wallet client retrieves the balance, modifies it locally, and writes the new balance back.
- **Where**: `supabase_client.py` (lines 140–184 and 185–225)
- **Why**: Under concurrent requests (e.g., if a user triggers multiple document generation threads simultaneously or performs actions in multiple browser tabs), multiple processes can read the same initial balance, perform calculations, and overwrite each other's updates. This can lead to:
  1. Users generating multiple documents for the cost of a single credit.
  2. Users losing credits if a credit addition and a credit deduction occur concurrently, where one overwrites the other.
- **Suggestion**: Implement atomic updates directly in the database (e.g., using a Supabase PostgreSQL function (RPC) or a raw update command like `UPDATE wallets SET balance = balance - :amount WHERE user_id = :user_id AND balance >= :amount`).

#### [Major] Finding 2: Lack of Double Spending / Replay Prevention on Payments
- **What**: The credit addition method `add_credits` updates the user's balance before trying to log the transaction ledger, and does not check for payment link reuse.
- **Where**: `supabase_client.py` (lines 185–225)
- **Why**: 
  1. If the database update to the balance succeeds but the insertion of the transaction ledger fails (e.g., due to unique constraint or connection dropout), the user is awarded the credits without any record.
  2. If there is no unique constraint on `payment_link_id` in the database, `add_credits` can be called repeatedly with the same `payment_link_id` to add infinite credits.
  3. If there is a unique constraint, the transaction insertion will fail, but since it is called *after* the balance update and catches exceptions silently, the user still receives the credits.
- **Suggestion**: Ensure that the transaction insertion (with a unique constraint on `payment_link_id`) occurs *before* or atomically *with* the wallet balance update inside a single transaction.

#### [Major] Finding 3: Silent Mock Fallback in Production Payments
- **What**: When `PAYMENTS_ENABLED` is True but the Razorpay API call fails (e.g., rate limit, timeout, DNS resolution error), the system silently falls back to generating a mock link.
- **Where**: `payments.py` (lines 52–54)
- **Why**: A production application should not fall back to mock behaviors when the real gateway is failing. Since mock payment simulation is disabled when `use_mock = False` in the frontend, the user will be presented with a mock `plink_...` URL that they cannot complete or verify, resulting in a broken user experience.
- **Suggestion**: Propagate the exception or return `(None, None)` when Razorpay creation fails under production configurations, allowing the Streamlit frontend to display a user-friendly error message.

#### [Minor] Finding 4: Missing Input Validation for Email on Sign Up
- **What**: The registration system does not check for empty emails or invalid email formats.
- **Where**: `supabase_client.py` (line 46) & `app.py` (line 59)
- **Why**: In mock mode, a user can register with an empty email address `""`, which becomes a valid account and gets 10 credits.
- **Suggestion**: Add a simple regex validation for email addresses and check for empty email/password strings before proceeding.

---

### Verified Claims

- **Mock database persistence across Streamlit reruns** → verified via code inspection of `_get_mock_db()` caching in `st.session_state` → **PASS**
- **Authentication & billing client contracts conformance** → verified by matching classes, methods, and return formats against `PROJECT.md` → **PASS**
- **Credit deduction blocking at zero balance** → verified by inspecting logic in `deduct_credits` returning `False` and frontend displaying the error → **PASS**
- **Unit test execution** → verified by dry-running `test_auth.py` logic step-by-step against mock implementation → **PASS** (all 6 tests pass logically)

---

### Coverage Gaps

- **Database RLS (Row Level Security) and Schema constraints** — risk level: **Medium** — recommendation: **Investigate** (ensure `wallets` and `transactions` tables have appropriate constraints and security policies to prevent users from modifying their balances directly via Supabase API).

---

### Unverified Items

- **Real Supabase / Razorpay execution** — reason not verified: No API keys configured in environment or secrets.

---
---

## Adversarial Challenge Report

## Challenge Summary

**Overall risk assessment**: HIGH

While the functional tests pass cleanly under single-threaded mock conditions, the system's reliance on client-side state manipulation for database updates makes it highly vulnerable to race conditions and double-spending.

---

## Challenges

### [Critical] Challenge 1: Concurrent Generation Credit Bypass
- **Assumption challenged**: Wallet balance updates are isolated and sequential.
- **Attack scenario**: A user opens two tabs of the Streamlit app. Both tabs show a balance of 1 credit. The user submits a document generation in both tabs at the exact same moment. Both threads fetch the balance (1 credit), pass the validation (`balance > 0`), render the document, and then write back `balance - 1` (0).
- **Blast radius**: User successfully gets 2 pages rendered for the cost of 1 credit, bypassing billing constraints.
- **Mitigation**: Use SQL atomic decrements: `UPDATE wallets SET balance = balance - 1 WHERE user_id = :user_id AND balance >= 1`.

### [High] Challenge 2: Payment Replay Vulnerability
- **Assumption challenged**: The client-side payment verification workflow is tamper-proof.
- **Attack scenario**: A user makes one legitimate purchase of 10 credits (payment link ID: `plink_abc`). They trigger the verification endpoint multiple times. Since the code does not enforce `payment_link_id` uniqueness before updating the balance, the user can replay the same link multiple times to add 10, 20, 30 credits.
- **Blast radius**: Multi-credit inflation from a single payment.
- **Mitigation**: Log the payment link ID in a unique-constrained transaction table *prior* to updating the balance.

---

## Stress Test Results

- **Simultaneous balance deduction requests** → Expect: Single deduction succeeds, second fails. → Predicted behavior: Both succeed, resulting in negative balance or double generation. → **FAIL**
- **Replayed verify_payment_link calls** → Expect: Second call returns already processed. → Predicted behavior: Re-awards credits if transaction tracking fails to block it. → **FAIL**
