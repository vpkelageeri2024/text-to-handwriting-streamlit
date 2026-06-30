## Challenge Summary

**Overall risk assessment**: HIGH

While the mock database implementation in `supabase_client.py` uses a reentrant module lock (`_LOCK = threading.RLock()`) to serialize accesses and prevent race conditions (meaning the mock tests in `test_stress.py` will pass successfully), the production (non-mock) fallback pathways in `supabase_client.py` contain severe race conditions and design issues that present significant security and reliability risks in a live deployment.

## Challenges

### [High] Challenge 1: Query-Based Fallback TOCTOU Double-Spend Race Condition in Deductions

- **Assumption challenged**: The fallback logic assumes that standard read-then-write query operations on the database table will behave atomically under concurrent execution.
- **Attack scenario**: If the atomic RPC function `deduct_wallet_credits` fails, is misconfigured, or fails to connect, the code falls back to `deduct_credits` query-based logic:
  ```python
  balance = self.get_balance(user_id)
  if balance < amount:
      return False
  new_balance = balance - amount
  self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
  ```
  If a user launches concurrent handwriting generation tasks (or rapidly clicks generate), multiple requests can execute the balance check simultaneously. Both read the same balance (e.g., 10), both pass the check (10 >= 8), both calculate the new balance as 2, and both write 2. The user successfully generates 16 credits worth of content while only being charged 8 credits.
- **Blast radius**: High. Direct financial loss (credit leakage) and bypass of credit-based paywalls under load.
- **Mitigation**: 
  1. Avoid query-based read-then-write fallback in the application layer.
  2. Implement a PostgreSQL database-level check constraint on the wallets table (e.g., `CONSTRAINT check_positive_balance CHECK (balance >= 0)`). This ensures that any update resulting in a negative balance fails at the database level regardless of application race conditions.
  3. Use an atomic SQL update command (e.g., `UPDATE wallets SET balance = balance - amount WHERE user_id = user_id AND balance >= amount`) rather than querying the value and updating with a hardcoded new balance.

### [High] Challenge 2: Lost Update and Replay Vulnerability in Non-Mock Additions

- **Assumption challenged**: Logging the transaction record first is sufficient to prevent concurrent credit replay attacks without database-level transactions or locks.
- **Attack scenario**: In the non-mock fallback addition path (`add_credits` lines 268-302):
  1. Two concurrent calls with the same `payment_link_id` check if the transaction exists: `self.client.table("transactions").select("id").eq("payment_link_id", payment_link_id).execute()`.
  2. Neither call finds the transaction yet, so both proceed to insert the transaction log.
  3. If there is no unique constraint on `payment_link_id` in the database schema, both inserts succeed and both add the credit amount, leading to duplicate credit allocation (double-spend/double-credit).
  4. Even if there is a unique constraint, the balance update itself is non-atomic:
     ```python
     balance = self.get_balance(user_id)
     new_balance = balance + amount
     self.client.table("wallets").update({"balance": new_balance}).execute()
     ```
     This is prone to a "lost update" where a concurrent deduction/addition is overwritten by this update.
- **Blast radius**: High. Credit inflation, financial exploitation by replaying payment link IDs.
- **Mitigation**:
  1. Ensure a `UNIQUE` constraint is strictly enforced on `payment_link_id` in the Supabase transactions database schema.
  2. Perform balance increments using atomic database updates: `UPDATE wallets SET balance = balance + amount WHERE user_id = user_id`.

### [Medium] Challenge 3: Silent Failure Fallback to Mock Database in Production

- **Assumption challenged**: If the Supabase client instantiation throws an exception, it is safe to silently fall back to mock mode.
- **Attack scenario**: In `SupabaseAuthClient.__init__` and `SupabaseWalletClient.__init__`:
  ```python
  try:
      self.client = create_client(self.url, self.key)
  except Exception:
      self.use_mock = True
  ```
  If the Supabase database is temporarily down or experiences transient DNS failure during app initialization, the production app will silently flip into mock mode. Users will sign up and have their balances tracked in-memory (`_MOCK_DB`).
  1. Different workers in a multi-instance Streamlit deployment will have completely disjoint user sets and balances.
  2. All users, balances, and transaction logs generated during this time will be wiped out when the Streamlit app restarts or scales down.
  3. Attackers can abuse the temporary mock state to log in with arbitrary passwords or gain free default credits since the mock database starts empty and grants 10 credits by default.
- **Blast radius**: High (for service integrity and user data persistence).
- **Mitigation**:
  - Remove silent exception-to-mock fallbacks. If production environment variables (`SUPABASE_URL` and `SUPABASE_KEY`) are present, initialization failures must raise an error and halt application startup or display a maintenance screen rather than silently running in mock mode.

## Stress Test Results

- **Concurrent Deductions Race Condition (`test_concurrent_deductions_race_condition`)**
  - Expected behavior: Only 10 of 20 concurrent threads succeed in deducting credits. Final balance is exactly 0, never negative.
  - Actual/predicted behavior: Pass. (Since `with _LOCK:` is used in mock mode, execution is serialized. In production mode, the RPC call `deduct_wallet_credits` is atomic).
  - Status: **PASS**

- **Negative Credit Deduction Vulnerability (`test_negative_credit_deduction_vulnerability`)**
  - Expected behavior: Deduction of negative amount (e.g. -100) fails. Balance remains unchanged (10).
  - Actual/predicted behavior: Pass. (Guard clause `if amount <= 0: return False` blocks negative credits).
  - Status: **PASS**

- **Concurrent Sign-Ups (`test_concurrent_signups`)**
  - Expected behavior: Only 1 of 10 concurrent signup attempts with the same email succeeds.
  - Actual/predicted behavior: Pass. (Serialized by `with _LOCK:` in mock mode. In production, Supabase auth handles user uniqueness constraints).
  - Status: **PASS**

- **Invalid Input Robustness (`test_invalid_input_robustness`)**
  - Expected behavior: Reject `None` email/password inputs without crashing; reject deduction of extremely large integer (`10**18`) due to insufficient balance; permit addition of large amount.
  - Actual/predicted behavior: Pass. (Inputs are validated via `validate_auth_inputs` and overflow balance check is respected).
  - Status: **PASS**

## Unchallenged Areas

- **Supabase Real Connection (Non-Mock)** — The unit tests run exclusively in mock mode (`use_mock=True`) because the tests are run without active live API credentials. Consequently, actual remote Supabase database trigger behavior, RPC schema, and network-level packet loss cannot be empirically tested in this suite.
