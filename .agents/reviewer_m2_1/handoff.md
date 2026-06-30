# Handoff Report — Review of User Authentication & Credit Wallet System (Milestone 2)

## 1. Observation

- **Implementation Code**:
  - `supabase_client.py`: Implements `SupabaseAuthClient` and `SupabaseWalletClient` with mock falls-backs.
  - `payments.py`: Implements `create_credit_payment_link` and `verify_payment_link`.
  - `app.py`: Streamlit application incorporating sidebar authentication (login/signup) and credit packages purchase.
  - `test_auth.py`: Unittest validating mock auth and wallet logic.
  - `test_stress.py`: Concurrency and adversarial stress tests.
  - `stress_test_suite.py`: Standalone stress test verification script.

- **Deduction and Check Logic (`supabase_client.py` lines 140-154)**:
  ```python
      def deduct_credits(self, user_id, amount) -> bool:
          """Deducts amount credits. Returns True if success, False if insufficient."""
          if self.use_mock:
              db = _get_mock_db()
              current_balance = db["balances"].get(user_id, 10)
              if current_balance >= amount:
                  db["balances"][user_id] = current_balance - amount
                  db["transactions"].append({
                      "user_id": user_id,
                      "amount": -amount,
                      "payment_link_id": None,
                      "type": "deduction"
                  })
                  return True
              return False
  ```

- **Silent Success in Update Failures (`supabase_client.py` lines 164-181)**:
  ```python
                  try:
                      res = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
                      if res.data:
                          updated = True
                  except Exception:
                      pass
                  
                  if not updated:
                      res = self.client.table("profiles").update({"balance": new_balance}).eq("id", user_id).execute()
                  
                  try:
                      self.client.table("transactions").insert({
                          "user_id": user_id,
                          "amount": -amount,
                          "type": "deduction"
                      }).execute()
                  except Exception:
                      pass
                  return True
  ```

- **Client-Side Credit Allocation (`app.py` lines 115-122)**:
  ```python
                      if verify_payment_link(st.session_state['payment_link_id']):
                          credits_to_add = st.session_state['payment_package_credits']
                          wallet_client.add_credits(user['id'], credits_to_add, st.session_state['payment_link_id'])
  ```

## 2. Logic Chain

- **Finding 1 (Negative Credit Deduction)**: Observing line 145 in `supabase_client.py` shows that `current_balance >= amount` is checked. If `amount` is negative (e.g. `-100`), the condition `current_balance >= -100` will be true. Line 146 calculates `db["balances"][user_id] = current_balance - (-100) = current_balance + 100`, adding credits directly through the deduction route.
- **Finding 2 (Double Spend / TOCTOU)**: Observing lines 144-146 in `supabase_client.py` shows that the balance reading, validation, and writing are three separate steps with no lock or critical section synchronization. Under high concurrency, these steps overlap, leading to race conditions.
- **Finding 3 (Silent Update Failures)**: Observing lines 164-181 in `supabase_client.py` shows that if the user record does not exist in `wallets` or `profiles`, both `update` statements will return empty arrays without raising exceptions. Since there is no assertion checking whether any rows were updated, the execution continues and returns `True`, allowing the transaction to succeed without deducting credits from any account.
- **Finding 4 (Amount Mismatch)**: Observing lines 115-117 in `app.py` shows that the number of credits to add is obtained from `st.session_state['payment_package_credits']` instead of checking the transaction payload from Razorpay or a database record of the link. This allows local session state tampering.
- **Finding 5 (Session State Loss)**: Storing `payment_link_id` and `payment_package_credits` in `st.session_state` (lines 98-100 of `app.py`) makes them vulnerable to page reloads and session timeouts.

## 3. Caveats

- Testing was performed using static code analysis, logic traces, and mock simulations. Direct execution of tests was not possible due to permission prompts timing out in the headless test environment.
- Live behaviors of Supabase database connection and Razorpay APIs were not tested since no keys/credentials were configured and network restrictions were active.

## 4. Conclusion

Milestone 2 User Authentication & Credit Wallet System is implemented but contains **critical vulnerabilities** (Negative credit deduction, Double-spend race condition, Silent database update failures, Client-side credit verification bypass, and Session state data loss). The final verdict is **REQUEST_CHANGES**.

## 5. Verification Method

- **To run tests**: Execute:
  ```bash
  python -m unittest test_auth.py
  python -m unittest test_stress.py
  python stress_test_suite.py
  ```
- **Files to Inspect**:
  - `supabase_client.py` (lines 140-226) for deduction validation and locks.
  - `payments.py` (lines 28-89) for payment verification logic.
  - `app.py` (lines 94-122) for session state dependency.
- **Invalidation Conditions**: If running `python -m unittest test_stress.py` passes all tests (meaning the race condition and negative deduction were successfully resolved), or if the mock/production deduction methods are secured.
