# Handoff Report: Milestone 2 Verification and Stress Testing

## 1. Observation
- **Test File Path**: `/home/vishal/text-to-handwriting-streamlit/test_auth.py`
- **Stress Test File Path**: `/home/vishal/text-to-handwriting-streamlit/test_stress.py`
- **Supabase Client File Path**: `/home/vishal/text-to-handwriting-streamlit/supabase_client.py`
- **App Frontend File Path**: `/home/vishal/text-to-handwriting-streamlit/app.py`
- **Command Output (Run Command)**:
  `Permission prompt for action 'command' on target 'python -m unittest test_auth.py' timed out waiting for user response. The user was not able to provide permission on time. You should proceed as much as possible without access to this resource.`
- **Code Observations**:
  - In `supabase_client.py`, lines 140-154:
    ```python
    def deduct_credits(self, user_id, amount) -> bool:
        """Deducts amount credits. Returns True if success, False if insufficient."""
        if self.use_mock:
            db = _get_mock_db()
            current_balance = db["balances"].get(user_id, 10)
            if current_balance >= amount:
                db["balances"][user_id] = current_balance - amount
    ```
  - In `supabase_client.py`, lines 157-164 (real DB client):
    ```python
    def deduct_credits(self, user_id, amount) -> bool:
        ...
        try:
            balance = self.get_balance(user_id)
            if balance < amount:
                return False
            new_balance = balance - amount
            
            updated = False
            try:
                res = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
    ```
  - In `app.py`, lines 343-388:
    ```python
            user_id = st.session_state['user']['id']
            balance = wallet_client.get_balance(user_id)
            if balance <= 0:
                ...
            else:
                with st.spinner("Generating Handwriting..."):
                    ...
                    images, last_y = render_handwriting_cached(...)
                    ...
                    deducted = wallet_client.deduct_credits(user_id, 1)
    ```

---

## 2. Logic Chain
1. **Deduction logic race condition**:
   - As observed in `supabase_client.py` (lines 140-154 for mock and lines 157-164 for real DB), the credit balance is read first (e.g. `get_balance`), compared against `amount` inside python code, and then written back via `update` or dictionary assignment.
   - Because these steps are separate and lack atomic execution block / transaction locks, multiple parallel invocations for the same user can execute the read concurrently.
   - Consequently, both requests will read the same high balance, pass the comparison, and subtract the same credit, resulting in a double-spend race condition.
2. **Negative credit deduction exploit**:
   - As observed in `supabase_client.py`, neither the mock nor the real database client checks if `amount` is positive.
   - Because `new_balance = balance - amount`, passing a negative amount (e.g., `-100`) leads to `balance - (-100) = balance + 100`.
   - This increases the user's credits without payment, validating an exploit vector.
3. **Billing timing order vulnerability**:
   - As observed in `app.py` (lines 343-388), `wallet_client.deduct_credits(user_id, 1)` is called only *after* `render_handwriting_cached` finishes execution.
   - Since rendering is CPU/GPU-intensive, this allows a user to trigger rendering resources and avoid being billed if the execution is cancelled or if the browser disconnects before the write finishes.

---

## 3. Caveats
- **Live Database execution**: Live testing against a real Supabase database could not be conducted since no credentials were provided and network connectivity is restricted to offline (CODE_ONLY).
- **Execution restrictions**: Terminal commands could not be run synchronously or in the background because the user permission prompts timed out (due to a non-interactive automation harness).

---

## 4. Conclusion
While the unit tests in `test_auth.py` are logically sound and would pass under sequential execution in mock mode, the system contains critical vulnerabilities:
1. **TOCTOU Double-Spend**: Concurrent requests can bypass credit balance checks.
2. **Negative Credit Injection**: Passing negative amounts artificially inflates the credit balance.
3. **Late billing**: Expensive rendering tasks are run before credit verification/deduction occurs, creating a DoS vector.

Actionable recommendation: Fix these vulnerabilities by ensuring atomic updates (e.g., single SQL `UPDATE` statement with a check constraints), enforcing positive values in `deduct_credits`, and reserving credits before beginning execution in `app.py`.

---

## 5. Verification Method
1. Run the test suite:
   ```bash
   python -m unittest test_auth.py
   ```
2. Run the newly added stress test suite to verify the vulnerabilities:
   ```bash
   python -m unittest test_stress.py
   ```
   - **Invalidation Condition**: If `test_stress.py` fails on `test_negative_credit_deduction_vulnerability`, `test_concurrent_deductions_race_condition`, or `test_concurrent_signups`, it confirms the bugs exist. Once mitigated, all tests in `test_stress.py` must pass.
