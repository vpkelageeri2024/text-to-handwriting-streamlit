import unittest
import threading
import time
import sys
from supabase_client import SupabaseAuthClient, SupabaseWalletClient, _get_mock_db
from payments import create_credit_payment_link, verify_payment_link, simulate_payment_success

class TestAuthAndWalletSystem(unittest.TestCase):
    def setUp(self):
        db = _get_mock_db()
        db["users"].clear()
        db["balances"].clear()
        db["transactions"].clear()
        self.auth_client = SupabaseAuthClient(url="", key="", use_mock=True)
        self.wallet_client = SupabaseWalletClient(url="", key="", use_mock=True)

    def test_account_creation(self):
        result = self.auth_client.sign_up("user@example.com", "securepassword123")
        self.assertTrue(result['success'])
        self.assertNotEqual(result['user_id'], '')
        self.assertEqual(result['error'], '')
        
        result_duplicate = self.auth_client.sign_up("user@example.com", "anotherpassword")
        self.assertFalse(result_duplicate['success'])
        self.assertEqual(result_duplicate['user_id'], '')
        self.assertEqual(result_duplicate['error'], 'User already exists')

    def test_login_logout(self):
        signup_res = self.auth_client.sign_up("login_user@example.com", "mypassword")
        self.assertTrue(signup_res['success'])
        
        login_res = self.auth_client.sign_in("login_user@example.com", "mypassword")
        self.assertTrue(login_res['success'])
        self.assertIsNotNone(login_res['session'])
        self.assertEqual(login_res['session']['user']['email'], "login_user@example.com")
        self.assertEqual(login_res['session']['user']['id'], signup_res['user_id'])
        self.assertEqual(login_res['error'], '')
        
        login_fail_pwd = self.auth_client.sign_in("login_user@example.com", "wrongpassword")
        self.assertFalse(login_fail_pwd['success'])
        self.assertIsNone(login_fail_pwd['session'])
        self.assertEqual(login_fail_pwd['error'], 'Invalid email or password')
        
        login_fail_email = self.auth_client.sign_in("nonexistent@example.com", "password")
        self.assertFalse(login_fail_email['success'])
        self.auth_client.sign_out()

    def test_credit_initialization(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        balance = self.wallet_client.get_balance(user_id)
        self.assertEqual(balance, 10)

    def test_credit_deduction(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        deduct_res = self.wallet_client.deduct_credits(user_id, 1)
        self.assertTrue(deduct_res)
        self.assertEqual(self.wallet_client.get_balance(user_id), 9)
        
        deduct_res2 = self.wallet_client.deduct_credits(user_id, 5)
        self.assertTrue(deduct_res2)
        self.assertEqual(self.wallet_client.get_balance(user_id), 4)

    def test_blocking_generation_when_credits_zero(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        self.assertTrue(self.wallet_client.deduct_credits(user_id, 10))
        self.assertEqual(self.wallet_client.get_balance(user_id), 0)
        
        deduct_fail = self.wallet_client.deduct_credits(user_id, 1)
        self.assertFalse(deduct_fail)
        self.assertEqual(self.wallet_client.get_balance(user_id), 0)

    def test_payment_and_credit_addition(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        credits_to_buy = 20
        amount_paise = 10000
        link_id, payment_url = create_credit_payment_link(amount_paise, credits_to_buy, "wallet_user@example.com")
        self.assertIsNotNone(link_id)
        self.assertTrue(payment_url.startswith("https://"))
        self.assertFalse(verify_payment_link(link_id))
        self.assertTrue(simulate_payment_success(link_id))
        self.assertTrue(verify_payment_link(link_id))
        
        add_res = self.wallet_client.add_credits(user_id, credits_to_buy, link_id)
        self.assertTrue(add_res)
        self.assertEqual(self.wallet_client.get_balance(user_id), 30)

def run_unittests():
    print("=== Running Unit Tests ===")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAuthAndWalletSystem)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

def stress_test_concurrency():
    print("\n=== Running Concurrency Stress Tests ===")
    db = _get_mock_db()
    db["users"].clear()
    db["balances"].clear()
    db["transactions"].clear()
    
    auth = SupabaseAuthClient(url="", key="", use_mock=True)
    wallet = SupabaseWalletClient(url="", key="", use_mock=True)
    
    # Create a user
    signup_res = auth.sign_up("stress@example.com", "password")
    user_id = signup_res['user_id']
    print(f"Created stress user {user_id} with initial balance {wallet.get_balance(user_id)}")
    
    # We will spin up 10 threads. Each thread attempts to deduct 2 credits.
    # Total deduction requested: 20 credits. Initial balance is 10.
    # If the system is thread-safe and correct, only 5 deductions should succeed,
    # and the remaining balance should be 0.
    # If there is a race condition, more than 5 deductions might succeed, or balance could be incorrect.
    
    success_count = 0
    failure_count = 0
    lock = threading.Lock()
    
    def worker():
        nonlocal success_count, failure_count
        # Introduce a slight delay to align threads
        time.sleep(0.01)
        res = wallet.deduct_credits(user_id, 2)
        with lock:
            if res:
                success_count += 1
            else:
                failure_count += 1

    threads = []
    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    final_balance = wallet.get_balance(user_id)
    print(f"Results of concurrent deductions (10 threads trying to deduct 2 credits each from balance 10):")
    print(f"  - Successful deductions: {success_count} (expected: 5)")
    print(f"  - Failed deductions: {failure_count} (expected: 5)")
    print(f"  - Final balance: {final_balance} (expected: 0)")
    
    concurrency_bug_detected = (success_count != 5) or (final_balance != 0)
    if concurrency_bug_detected:
        print("❌ CONCURRENCY BUG DETECTED: Race condition in mock client allowed double-spending or corrupted state!")
    else:
        print("✅ Concurrency check passed (no race condition observed in this run).")
        
    # Stress test duplicate signup race condition
    print("\n=== Running Duplicate Signup Concurrency Test ===")
    db["users"].clear()
    db["balances"].clear()
    
    signup_success_count = 0
    signup_fail_count = 0
    
    def signup_worker():
        nonlocal signup_success_count, signup_fail_count
        time.sleep(0.01)
        res = auth.sign_up("dup@example.com", "password")
        with lock:
            if res['success']:
                signup_success_count += 1
            else:
                signup_fail_count += 1
                
    threads = []
    for _ in range(10):
        t = threading.Thread(target=signup_worker)
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    print(f"Results of concurrent signups (10 threads registering same email 'dup@example.com'):")
    print(f"  - Successful signups: {signup_success_count} (expected: 1)")
    print(f"  - Failed signups: {signup_fail_count} (expected: 9)")
    
    signup_bug_detected = signup_success_count != 1
    if signup_bug_detected:
        print("❌ CONCURRENCY BUG DETECTED: Multiple concurrent signups for same email succeeded!")
    else:
        print("✅ Duplicate signup check passed.")

    return not (concurrency_bug_detected or signup_bug_detected)

if __name__ == '__main__':
    unit_ok = run_unittests()
    stress_ok = stress_test_concurrency()
    if not unit_ok or not stress_ok:
        sys.exit(1)
    sys.exit(0)
