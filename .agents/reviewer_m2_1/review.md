## Review Summary

**Verdict**: REQUEST_CHANGES

The implementation of the User Authentication & Credit Wallet System (Milestone 2) successfully establishes the architectural scaffolding (frontend UI, client libraries, payment integration, and test suite). However, several critical security vulnerabilities, correctness bugs, and reliability issues exist that must be addressed before this work can be approved for production.

---

## Findings

### [Critical] Finding 1: Negative Credit Deduction (Credit Injection Vulnerability)

- **What**: The credit deduction process accepts negative values without validation, resulting in credit addition instead of deduction.
- **Where**: `supabase_client.py`, lines 140-183 (inside `SupabaseWalletClient.deduct_credits`).
- **Why**: The method calculates `new_balance = balance - amount`. If a negative number is supplied for `amount` (e.g., `-100`), the calculation evaluates to `balance - (-100) = balance + 100`, effectively injecting 100 credits into the user's wallet. This is a severe billing exploit.
- **Suggestion**: Add a sanity check at the beginning of the `deduct_credits` method to ensure the deduction amount is strictly positive:
  ```python
  if amount <= 0:
      return False  # or raise ValueError
  ```

### [Critical] Finding 2: Double Spend / TOCTOU Race Condition in Mock Client

- **What**: The mock credit deduction process reads and writes balances in a non-atomic manner without synchronization locks.
- **Where**: `supabase_client.py`, lines 142-154 (inside `SupabaseWalletClient.deduct_credits` mock branch).
- **Why**: Under concurrent request execution (e.g., rapid clicks or API calls), multiple threads can query `db["balances"].get(user_id)` simultaneously, read the same balance, pass the validation check, and overwrite the balance. This permits users to generate far more pages than their credit limit.
- **Suggestion**: Implement a threading lock around mock database reads/writes:
  ```python
  import threading
  _MOCK_DB_LOCK = threading.Lock()
  
  # Inside deduct_credits mock branch:
  with _MOCK_DB_LOCK:
      # perform read, check, write
  ```

### [Major] Finding 3: Credit Bypass via Silent Update Failures in Production Client

- **What**: The production `deduct_credits` method returns `True` and logs a deduction transaction even if database balance updates match 0 rows.
- **Where**: `supabase_client.py`, lines 155-183 (inside `SupabaseWalletClient.deduct_credits` production branch).
- **Why**: If a user's record does not exist in the `wallets` or `profiles` tables, the `update` queries fail to modify any rows (returning success but with empty `data`). The code does not verify whether rows were actually modified; it continues to log a transaction and returns `True`, giving the user unlimited free handwriting generation.
- **Suggestion**: Verify that the update query returned non-empty data or affected rows. If the user record does not exist, insert it or raise an error instead of returning `True` silently.

### [Major] Finding 4: Client-Side Credit Allocation & Amount Mismatch Vulnerability

- **What**: Credit package additions rely on volatile frontend session state instead of the actual paid amount or a secure registry.
- **Where**: `app.py`, lines 115-122.
- **Why**: When a payment link is verified, the app reads `st.session_state['payment_package_credits']` to determine how many credits to add. A user could manipulate the session state to buy a ₹50 package but get credited 100 credits. Furthermore, `payments.py` does not verify if the paid amount matches the package credits being awarded.
- **Suggestion**: Retrieve the package credits and purchase details directly from the payment link details returned by the payment gateway (e.g., matching the payment amount) or from a database table tracking pending payment links.

### [Medium] Finding 5: Session State Data Loss

- **What**: Streamlit session state is volatile and can cause users to lose purchased credits if their browser page refreshes or times out before they click "Verify Payment".
- **Where**: `app.py`, lines 94-122.
- **Why**: The app stores the generated `payment_link_id` and `payment_package_credits` in `st.session_state`. If the session times out, the user has no way to verify their payment or claim their credits upon reconnecting.
- **Suggestion**: Persist pending payment links in a `payment_links` database table mapping `link_id` to `user_id` and `credits`, so users can verify them even after session recreation.

---

## Verified Claims

- **Authentication UI and Flow** → verified via code trace and mock client structure. Signup and Login correctly record and check user passwords and assign unique user IDs. → **PASS**
- **Default Credit Initialization** → verified via `test_auth.py` and `supabase_client.py`. Users are initialized with 10 credits upon registration. → **PASS**
- **Generation Blocking on Zero Balance** → verified via `app.py` form handling and `test_auth.py`. Users are prevented from triggering handwriting generation if their balance is 0 or less. → **PASS**
- **Payment Link Generation** → verified via `payments.py` and `test_auth.py`. Razorpay links are created with fallback mocks. → **PASS**

---

## Coverage Gaps

- **State Leakage across Sessions** — risk level: **Medium** — The mock DB uses a shared global dictionary `_MOCK_DB` across all Streamlit sessions. If multiple users test the mock client concurrently, their account credentials and credit balances will leak across sessions. Recommendation: Isolate mock database states within unique session identifiers.
- **Database Schema and Migration** — risk level: **Medium** — No SQL script or migration documentation is provided to create the `wallets`, `profiles`, and `transactions` tables in Supabase. Recommendation: Add a `schema.sql` file defining the schema, foreign keys, and unique constraints.

---

## Unverified Items

- **Real Supabase DB Live Behavior** — Reason not verified: No live credentials were provided, and testing was conducted under offline code-only network constraints.
- **Live Razorpay Webhook/Client Actions** — Reason not verified: No live API keys were configured.
