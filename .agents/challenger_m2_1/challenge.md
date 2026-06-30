# Milestone 2 Verification and Stress Test Report

## Challenge Summary

**Overall risk assessment**: **CRITICAL**

We conducted a detailed static code analysis and designed a stress test suite (`test_stress.py`) to verify the correctness, concurrency limits, and robustness of the Milestone 2 Auth & Wallet implementation. 

*Note: Execution of terminal commands via `run_command` timed out due to the non-interactive environment requiring user approval prompts. Consequently, the verification was performed via complete logical trace/simulation of the unit tests and stress tests, identifying multiple critical logic and security flaws in the implementation.*

---

## Identified Vulnerabilities and Challenges

### [Critical] Challenge 1: Double Spend / TOCTOU Race Condition in Credit Deduction
- **Assumption challenged**: The credit deduction process is atomic and prevents double-spending.
- **Attack scenario**: A user with a small balance (e.g. 1 credit) makes concurrent page generation requests (e.g. by clicking the "Generate" button multiple times quickly or scripting API calls). 
- **Blast radius**: The application reads the balance, checks if `balance >= amount`, and then updates the balance. Under concurrent execution, multiple threads/requests read the same balance, pass the check, perform the heavy rendering work, and overwrite the balance with `balance - amount`, allowing the user to generate many more pages than their credit limit allows.
- **Mitigation**: 
  - For the database client: Perform the deduction atomically in a single SQL query (e.g., `UPDATE wallets SET balance = balance - :amount WHERE user_id = :user_id AND balance >= :amount`) rather than doing a separate `SELECT` followed by `UPDATE`.
  - For the mock client: Implement a threading lock (`threading.Lock`) around the `_MOCK_DB` modifications.

### [Critical] Challenge 2: Negative Credit Deduction (Credit Injection Vulnerability)
- **Assumption challenged**: The wallet client only allows positive values for credit deductions.
- **Attack scenario**: A user or internal component calls `deduct_credits(user_id, -100)`.
- **Blast radius**: 
  - In `supabase_client.py` (both mock and real implementations), there is no check that `amount` must be positive.
  - The calculation performs `new_balance = balance - amount`. Since subtracting a negative number is equivalent to addition, the user's balance becomes `balance + 100`.
  - This allows an attacker to exploit the credit check to inject arbitrary credits into their wallet without paying.
- **Mitigation**: Add a sanity check at the beginning of `deduct_credits` to reject negative amounts:
  ```python
  if amount <= 0:
      raise ValueError("Deduction amount must be positive.")
  ```

### [High] Challenge 3: Concurrent Sign-ups Race Condition
- **Assumption challenged**: The email unique constraint is handled gracefully by the auth provider/mock client.
- **Attack scenario**: Concurrent signup requests for the same email address are processed simultaneously.
- **Blast radius**:
  - In the mock auth client, the check `if email in db["users"]` and the write `db["users"][email] = ...` are not thread-safe.
  - Two threads can check the email concurrently, find it doesn't exist, and both create different user accounts/IDs for the same email, overwriting each other and leading to database inconsistency.
- **Mitigation**: Use thread-safe data structures or locking mechanisms for the mock implementation, and ensure proper database unique constraints are defined in Supabase.

### [Medium] Challenge 4: Absence of Input Validation in Auth Client
- **Assumption challenged**: Inputs to `sign_up` and `sign_in` are validated prior to execution.
- **Attack scenario**: Malformed or `None` values are sent as emails/passwords.
- **Blast radius**:
  - The mock implementation accepts `None` as a valid email and password and creates a user entry with `None` as the key.
  - While the database version might throw errors, the mock version allows registering and logging in as user `None`, causing unit tests to behave differently from production.
- **Mitigation**: Enforce string type and format checks on email and password inputs.

### [Medium] Challenge 5: Heavy CPU/GPU Rendering Cost Incurred Before Credit Deduction
- **Assumption challenged**: Wallet billing is secure against denial-of-service/resource-exhaustion.
- **Attack scenario**: A user with 1 credit requests rendering a large document, but terminates their session or causes the connection to close during the rendering step.
- **Blast radius**:
  - In `app.py`, the rendering step `render_handwriting_cached` is executed *before* `wallet_client.deduct_credits` is called.
  - The server spends high processing time rendering multiple pages, and only charges the wallet afterwards. If the user disconnects or an exception occurs post-render, the credits are never deducted.
- **Mitigation**: Deduct/reserve the credit *before* starting the intensive rendering operation. If rendering fails completely, refund the credit.

---

## Stress Test Results (Simulated/Predicted)

We created a custom stress-test suite `test_stress.py` containing tests matching these scenarios:

| Test Case Name | Scenario | Expected Behavior | Simulated/Predicted Behavior | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- |
| `test_concurrent_deductions_race_condition` | 20 threads deducting 1 credit from a starting balance of 10. | Exactly 10 successes, final balance = 0. | > 10 successes, final balance = 0 (due to overwritten decrements). | **FAIL** (Safety violated) |
| `test_negative_credit_deduction_vulnerability` | Deducting -100 credits from a balance of 10. | Call returns False, balance remains 10. | Call returns True, balance becomes 110. | **FAIL** (Vulnerability confirmed) |
| `test_concurrent_signups` | 10 threads signing up the same email concurrently. | Exactly 1 signup succeeds. | Multiple signups succeed and return success user IDs. | **FAIL** (Concurrency check bypassed) |
| `test_invalid_input_robustness` | Registering with `None` email/password. | Call returns False/errors out. | Call returns True, registers `None` user. | **FAIL** (Validation missing in mock) |

---

## Unchallenged Areas

- **Real Supabase DB Live Behavior**: Not tested due to lack of Supabase credentials and offline code-only network constraint.
- **Razorpay Integration Live Webhooks**: Not tested since the network is code-only and credentials are not configured.
