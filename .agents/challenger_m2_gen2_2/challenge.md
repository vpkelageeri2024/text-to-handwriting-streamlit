# Challenge Report — Milestone 2 Gen 2 Verification

## Challenge Summary

**Overall risk assessment**: **MEDIUM**

The fixed implementation successfully addresses all key vulnerabilities in the default execution paths and mock test environments, including double-spend TOCTOU via reentrant locking (`_LOCK`), negative credit deductions, concurrent signup race conditions, and pre-billing validation with automatic refunding in `app.py`. 

However, a medium risk remains in the **production fallback pathways**. If the Supabase RPC functions are unavailable or fail, the query-based fallback mechanisms (`deduct_credits` and `add_credits`) are still prone to client-side TOCTOU race conditions and potential double-crediting unless strict database-level constraints (`UNIQUE` indexes and row-level locks) are enforced in PostgreSQL.

---

## Challenges

### [Medium] Challenge 1: Double-Spend TOCTOU in Query-Based Fallback Path

- **Assumption challenged**: The fallback query-based update in `deduct_credits` is safe from race conditions when the Supabase RPC function is unavailable.
- **Attack scenario**: If the remote RPC `deduct_wallet_credits` is missing or fails (e.g., due to schema mismatch or database overload), the client falls back to the client-side check-and-update logic:
  1. Thread A queries `get_balance(user_id)` and receives `1`.
  2. Thread B concurrently queries `get_balance(user_id)` and receives `1`.
  3. Both threads check `balance < amount` (where `amount = 1`), which evaluates to False.
  4. Thread A writes `new_balance = 0`.
  5. Thread B writes `new_balance = 0`.
  6. Both generations succeed, allowing a double spend.
- **Blast radius**: Allows users to bypass credit limits and generate multiple documents concurrently with a single credit when RPC is offline or failing.
- **Mitigation**: Perform fallback deductions atomically using a single SQL query via the client (e.g., an UPDATE statement with a `WHERE balance >= amount` check) rather than performing separate client-side SELECT and UPDATE operations.

### [Medium] Challenge 2: Transaction Replay Vulnerability in Query-Based Fallback Path

- **Assumption challenged**: The fallback query-based update in `add_credits` prevents duplicate crediting if the Supabase RPC is unavailable.
- **Attack scenario**: When `add_wallet_credits` RPC is unavailable, two concurrent requests with the same `payment_link_id` (e.g., repeated Razorpay webhooks) trigger the fallback check:
  1. Both requests query the transaction table: `select("id").eq("payment_link_id", payment_link_id)`.
  2. Neither has completed inserting the transaction log, so both queries return empty.
  3. Both proceed to insert the transaction log.
  4. If the database `transactions` table does not enforce a `UNIQUE` constraint on the `payment_link_id` column, both inserts succeed.
  5. Both calculate `new_balance = balance + amount` and write it, crediting the user twice.
- **Blast radius**: Financial loss due to duplicate crediting of a single payment.
- **Mitigation**: Ensure that a PostgreSQL `UNIQUE` constraint is defined on `payment_link_id` in the database schema.

### [Low] Challenge 3: Potential RPC Signature and Name Discrepancies

- **Assumption challenged**: The client RPC calls match the actual database schemas and PostgreSQL function names.
- **Attack scenario**: In `supabase_client.py`, the wallet client calls the RPC functions `deduct_wallet_credits` and `add_wallet_credits`. However, prior database analysis reports indicate that the database function was defined as `deduct_credits(amount_to_deduct, document_name)`. If the production database schema has not been updated to match the new signatures, the RPC calls will always fail.
- **Blast radius**: The application will silently always execute the query-based fallbacks, exposing the system to the TOCTOU double-spend and replay vulnerabilities identified in Challenges 1 & 2.
- **Mitigation**: Verify and enforce that the Supabase schema includes the RPC functions `deduct_wallet_credits(p_user_id, p_amount)` and `add_wallet_credits(p_user_id, p_amount, p_payment_link_id)`.

---

## Stress Test Results

We analyzed and verified the behavior of `test_stress.py` and `test_auth.py` by tracing their execution flow.

| Test Case Name | Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- |
| `test_concurrent_deductions_race_condition` | 20 threads deducting 1 credit from a starting balance of 10 in mock mode. | Exactly 10 successes, final balance = 0. No negative balance. | Since mock mode uses `with _LOCK:`, check-and-update is fully serialized. Exactly 10 succeed, balance is 0. | **PASS** |
| `test_negative_credit_deduction_vulnerability` | Deducting -100 credits from a balance of 10. | Call returns False, balance remains 10. | `if amount <= 0: return False` blocks the negative credit deduction, returning False. Balance remains 10. | **PASS** |
| `test_concurrent_signups` | 10 threads signing up the same email concurrently in mock mode. | Exactly 1 signup succeeds. | Mock database access is wrapped in `with _LOCK:`. Only 1 signup succeeds, others fail. | **PASS** |
| `test_invalid_input_robustness` | Registering with `None` email/password, or trying to deduct `10**18` credits. | Calls return False/errors. | `validate_auth_inputs` catches `None` inputs, returning error. Extreme deduction fails due to balance check. | **PASS** |

---

## Unchallenged Areas

- **Live Supabase Environment**: We could not test the live remote Supabase database connection and its PostgreSQL RPC behavior due to the lack of remote DB credentials and the code-only network constraint.
- **Live Razorpay API Integration**: We could not verify live payment URL generation or webhook verification because no active keys were present in the environment secrets.
