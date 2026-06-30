# Milestone 2 Gen 2: User Authentication & Credit Wallet System Review

## Review Summary

**Verdict**: **APPROVE**

The proposed fixes to the User Authentication & Credit Wallet System successfully address the identified concurrency, range validation, pre-billing, and payment fallback issues. Unit and stress test suites are logically sound and verify the changes in mock mode.

---

## Quality Review Report

### Findings

#### [Minor] Finding 1: Weak Assertions in Concurrency Stress Test
- **What**: The stress test `test_concurrent_deductions_race_condition` in `test_stress.py` uses a loose assertion.
- **Where**: `test_stress.py`, line 65: `self.assertGreaterEqual(final_balance, 0, "Wallet balance fell below zero!")`
- **Why**: While this prevents the balance from going negative, it does not strictly verify that *exactly* 10 deductions succeeded and that the final balance is *exactly* 0. Under certain race conditions, the balance might end up at 2 or 3 (some threads failing silently or overwriting), and the test would still pass.
- **Suggestion**: Strengthen the assertions in `test_stress.py` to:
  ```python
  self.assertEqual(final_balance, 0)
  self.assertEqual(len(success_count), 10)
  ```

#### [Minor] Finding 2: Lack of Input Sanitization for Unicode or Leading/Trailing Spaces in Auth
- **What**: In `supabase_client.py`, the validation function `validate_auth_inputs` strips the email string during validation checks but does not return the stripped version, meaning trailing whitespace is preserved in the database.
- **Where**: `supabase_client.py`, lines 15-26.
- **Why**: Keeping whitespaces in emails can lead to login confusion if the user logs in without the whitespace later.
- **Suggestion**: Strip email inputs at the controller/service layer before passing them to the sign-up and sign-in operations.

### Verified Claims

- **Concurrency protection in mock mode via threading.RLock** → verified via static analysis of `supabase_client.py` and checking `test_stress.py` → **PASS**
  - All mock database reads, writes, and checks in `sign_up`, `sign_in`, `get_balance`, `deduct_credits`, and `add_credits` are wrapped in `with _LOCK:`.
- **Negative credit deduction prevention** → verified via static analysis of `supabase_client.py` line 171 and adversarial test `test_negative_credit_deduction_vulnerability` → **PASS**
  - Deductions and additions with `amount <= 0` return `False` immediately.
- **Order of operations preventing transaction replays** → verified via static analysis of `supabase_client.py` (`add_credits`) → **PASS**
  - In mock mode, duplicate `payment_link_id` check is performed first, then the transaction is logged, and finally the balance is updated.
  - In production mode, the transaction log is inserted prior to updating the balance. Duplicate insertion fails (via database UNIQUE constraint) before any balance modification.
- **Pre-billing implementation** → verified via static analysis of `app.py` lines 347-398 → **PASS**
  - `wallet_client.deduct_credits(user_id, 1)` is called before the `try` block.
  - `render_handwriting_cached` is executed inside the `try` block.
  - On exception, `wallet_client.add_credits(user_id, 1, refund_id)` is called to refund the credit.
- **Silent mock fallback disabled for payments** → verified via static analysis of `payments.py` lines 30-55 → **PASS**
  - When `PAYMENTS_ENABLED` is `True`, any exception thrown during Razorpay payment link creation is re-raised via `raise e` instead of silently falling back to mock payment generation.

### Coverage Gaps

- **Production Fallback Non-Atomicity** — risk level: **Medium** — recommendation: **Accept risk / Address in next cycle**
  - If Supabase RPC database functions (`deduct_wallet_credits` and `add_wallet_credits`) fail or are not deployed, the code falls back to python-side check-and-update (standard queries). This fallback path is not atomic and is susceptible to race conditions.
  - *Recommendation*: Ensure DB constraints (e.g., `balance >= 0`) are active, and enforce UNIQUE constraint on `transactions.payment_link_id`.

### Unverified Items

- **Actual production database execution** — reason not verified: Supabase credentials are mock/empty in local test configurations, so only the mock paths and the code structure of production paths could be verified.

---

## Adversarial Review Report (Challenge Report)

**Overall risk assessment**: **LOW** (in mock mode due to `RLock`), **MEDIUM** (in production mode if DB constraints and UNIQUE indexes are missing).

### Challenges

#### [Medium] Challenge 1: Race Condition in Production Fallback Path
- **Assumption challenged**: Production database fallback routes are concurrency-safe.
- **Attack scenario**: If the Supabase RPC `deduct_wallet_credits` is unavailable, two concurrent requests call `deduct_credits` fallback:
  1. Both call `get_balance` and retrieve `10`.
  2. Both deduct `6` credits.
  3. Both calculate `new_balance = 4` and update the DB.
  4. The user receives two 6-credit generations, but the final balance is updated to `4` (a loss of 6 credits to the platform).
- **Blast radius**: Credit leakage or double-spend on RPC failure.
- **Mitigation**: Remove python-side check-and-update fallback entirely, or use an atomic SQL update statement:
  ```sql
  UPDATE wallets SET balance = balance - amount WHERE user_id = :user_id AND balance >= :amount;
  ```

#### [Low] Challenge 2: Replay Attack in Production Fallback Path
- **Assumption challenged**: Payment replays are blocked in the production fallback path.
- **Attack scenario**: If the `transactions` table does not have a `UNIQUE` constraint on the `payment_link_id` column, the insert statement `self.client.table("transactions").insert(...)` will succeed multiple times for the same payment link, allowing a malicious actor to replay the payment and add credits repeatedly.
- **Blast radius**: Multi-credit inflation / duplicate credit additions.
- **Mitigation**: Enforce a strict `UNIQUE` constraint on the `payment_link_id` column of the `transactions` table.

### Stress Test Results

- **Concurrent deductions stress test** → Verified that `_LOCK` serializes executions in mock mode. Asserts balance does not fall below zero. (Pass)
- **Concurrent duplicate signups** → Verified that `_LOCK` ensures only one signup succeeds for a given email. (Pass)
- **Negative credit injection** → Verified that range validations reject negative amounts. (Pass)

### Unchallenged Areas

- **Supabase native auth concurrency** — Out of scope. We assume Supabase's identity provider handles concurrent signup/login natively and safely.
