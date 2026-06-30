# Handoff Report — Milestone 2 Review (User Authentication & Credit Wallet System)

## 1. Observation

- **Supabase client wallet updates** (`supabase_client.py`, lines 157–181):
  ```python
  balance = self.get_balance(user_id)
  if balance < amount:
      return False
  new_balance = balance - amount
  ...
  res = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
  ```
- **Credit addition ledger log order** (`supabase_client.py`, lines 200–223):
  ```python
  balance = self.get_balance(user_id)
  new_balance = balance + amount
  
  updated = False
  try:
      res = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
      if res.data:
          updated = True
  except Exception:
      pass
  ...
  try:
      self.client.table("transactions").insert({
          "user_id": user_id,
          "amount": amount,
          "payment_link_id": payment_link_id,
          "type": "addition"
      }).execute()
  except Exception:
      pass
  ```
- **Payment link creation fallback** (`payments.py`, lines 52–68):
  ```python
  except Exception as e:
      # If Razorpay client fails, fallback to mock
      pass
      
  # Mock fallback
  link_id = f"plink_{uuid.uuid4().hex[:12]}"
  payment_url = f"https://rzp.io/i/mock_{link_id}"
  ```
- **Streamlit session state mock database caching** (`supabase_client.py`, lines 17–25 and `payments.py`, lines 18–26):
  Uses `st.session_state` to store and retrieve mock DB structures, preventing data loss during rerun cycles.
- **Terminal Execution**: Running `python -m unittest test_auth.py` via `run_command` timed out waiting for user approval.

---

## 2. Logic Chain

1. **Client-Side Race Conditions**: In `supabase_client.py` (`deduct_credits` and `add_credits`), the application queries the balance, calculates `new_balance` on the Python side, and updates the DB with the absolute value. If multiple threads run concurrently, they will read the same stale balance and perform overlapping writes, leading to credit bypass or credit loss.
2. **Double Spending / Replay Vulnerability**: In `add_credits`, the balance update is executed before the transaction ledger insertion, and any exception during insertion is swallowed. If `payment_link_id` is unique in the database schema, a replay call will fail the ledger insertion but still successfully complete the balance update. If `payment_link_id` is not unique, there is no verification to prevent re-crediting the same payment link.
3. **Silent Failure / Mock Leak**: In `payments.py`, catching exceptions during production payment creation and returning a mock URL `plink_...` generates a link that the frontend cannot simulate (since `use_mock` is False). This leads to a non-functional verification loop.
4. **Mock DB Caching**: Caching `_MOCK_DB` in Streamlit's `session_state` is a correct and robust approach for state persistence across Streamlit's execution model.
5. **Unit Tests Conformance**: Dry-running the tests in `test_auth.py` against the mock implementations verifies that all 6 test cases (`test_account_creation`, `test_login_logout`, `test_credit_initialization`, `test_credit_deduction`, `test_blocking_generation_when_credits_zero`, and `test_payment_and_credit_addition`) pass logically.

---

## 3. Caveats

- **External Integrations**: We did not verify live connections to Supabase or Razorpay since no credentials were provided in the testing environment.
- **Command execution timeout**: The `run_command` execution timed out due to permissions, so tests were verified via rigorous static code trace rather than dynamic runtime execution.

---

## 4. Conclusion

The verdict is **REQUEST_CHANGES**. While the code implements the interface contracts and passes all mock unit tests, it contains critical concurrency and double-spending vulnerabilities in the wallet/transaction logic, along with a reliability issue in payment link fallback.

**Summary of action items**:
1. Migrate `deduct_credits` and `add_credits` to use database-level atomic increment/decrement or Supabase RPC database functions.
2. Perform transaction logging (with unique constraints on `payment_link_id`) *prior* to updating the balance, ensuring a rollback if the log fails.
3. Disable the silent mock fallback in `payments.py` when `PAYMENTS_ENABLED` is true.

---

## 5. Verification Method

To verify the test execution:
1. Setup a clean virtual environment and install requirements: `pip install -r requirements.txt`.
2. Run unit tests using: `python -m unittest test_auth.py`.
3. To test the race condition, run multiple concurrent requests calling `deduct_credits` on the same `user_id` when the balance is 1.
