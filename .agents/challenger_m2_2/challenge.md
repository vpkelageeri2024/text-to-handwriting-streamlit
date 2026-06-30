## Challenge Summary

**Overall risk assessment**: HIGH

Milestone 2 implements the authentication and credit/wallet system. While the basic functional tests in `test_auth.py` pass under single-threaded mock execution, the architecture contains severe concurrency vulnerabilities (race conditions) in both the mock and real Supabase client implementations. These vulnerabilities permit double-spending of credits and duplicate registration of the same email address.

---

## Challenges

### [High] Challenge 1: Double-Spending of Credits (Deduction Race Condition)

- **Assumption challenged**: The client assumes that checking the wallet balance and updating it is an atomic operation.
- **Attack scenario**: A user sends multiple concurrent generation requests (either via double-clicking in the UI or scripting API calls). The database receives these concurrent requests. 
  1. Request A reads the balance (e.g. 10 credits).
  2. Request B reads the balance (e.g. 10 credits).
  3. Both requests see that the balance is >= cost (e.g. 10 credits) and allow generation.
  4. Request A updates the balance to 0 (10 - 10).
  5. Request B updates the balance to 0 (10 - 10).
- **Blast radius**: Users can generate far more handwriting pages than they paid for, resulting in direct revenue loss and resource drain.
- **Mitigation**: 
  - **Supabase/Postgres**: Perform the deduction in a single atomic SQL update query:
    ```sql
    UPDATE wallets 
    SET balance = balance - amount 
    WHERE user_id = :user_id AND balance >= amount;
    ```
    If the update statement returns 0 rows affected, reject the transaction due to insufficient credits.
  - **Mock implementation**: Use a `threading.Lock` to synchronize access to `db["balances"]` and `db["transactions"]`.

### [Medium] Challenge 2: Duplicate Registration Race Condition

- **Assumption challenged**: The code assumes checking user existence and inserting a new user is safe from concurrent insertion.
- **Attack scenario**: Two registration requests for the exact same email address arrive at the exact same millisecond.
  1. Request A checks if the email exists in the database (finds False).
  2. Request B checks if the email exists in the database (finds False).
  3. Request A inserts user A.
  4. Request B inserts user B, overwriting the user mapping or creating duplicate records in the users table.
- **Blast radius**: Database integrity violation, orphaned user records, and potential session leakage.
- **Mitigation**:
  - **Database constraints**: Enforce a `UNIQUE` constraint on the `email` column in the database.
  - **Mock implementation**: Use a `threading.Lock` to synchronize the sign-up process.

---

## Stress Test Results

- **Scenario 1: Concurrent Credit Deductions** 
  - **Setup**: 10 concurrent threads try to deduct 2 credits each from a starting balance of 10.
  - **Expected behavior**: Exactly 5 threads succeed (total 10 credits deducted), 5 threads fail, and final balance is 0.
  - **Actual/Predicted behavior**: All 10 threads succeed (total 20 credits requested), final balance is 8 (because each thread fetched 10 and updated to 8).
  - **Result**: FAIL (Race condition confirmed)

- **Scenario 2: Concurrent Duplicate Registration**
  - **Setup**: 10 concurrent threads attempt to register the same email `dup@example.com` simultaneously.
  - **Expected behavior**: Exactly 1 thread succeeds, 9 threads fail with "User already exists".
  - **Actual/Predicted behavior**: All 10 threads succeed, creating 10 user entries or overwriting.
  - **Result**: FAIL (Race condition confirmed)

- **Scenario 3: Single-threaded Functional Test Suite**
  - **Setup**: Run `python -m unittest test_auth.py`
  - **Expected behavior**: All 6 unit tests pass.
  - **Actual/Predicted behavior**: All 6 unit tests pass (confirmed by code verification of single-threaded mock execution).
  - **Result**: PASS

---

## Unchallenged Areas

- **Real Supabase and Razorpay APIs under load** — Reason not challenged: Missing live API credentials and sandbox access. Testing was done against the mock implementation, which mirrors the logic of the real implementation.
