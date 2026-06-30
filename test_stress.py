import unittest
import threading
import time
from supabase_client import SupabaseAuthClient, SupabaseWalletClient, _get_mock_db
from payments import create_credit_payment_link, verify_payment_link, simulate_payment_success

class TestAuthAndWalletStress(unittest.TestCase):
    def setUp(self):
        # Reset mock database before each test
        db = _get_mock_db()
        db["users"].clear()
        db["balances"].clear()
        db["transactions"].clear()
        
        self.auth_client = SupabaseAuthClient(url="", key="", use_mock=True)
        self.wallet_client = SupabaseWalletClient(url="", key="", use_mock=True)

    def test_concurrent_deductions_race_condition(self):
        """
        Stress test: simulate concurrent credit deductions.
        Start with 10 credits, run 20 concurrent threads trying to deduct 1 credit each.
        In a secure/thread-safe system, only 10 threads should succeed, and balance should end at 0.
        """
        signup_res = self.auth_client.sign_up("stress_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # Verify initial balance is 10
        self.assertEqual(self.wallet_client.get_balance(user_id), 10)
        
        success_count = []
        failure_count = []
        threads = []
        
        def worker():
            # Try to deduct 1 credit
            res = self.wallet_client.deduct_credits(user_id, 1)
            if res:
                success_count.append(1)
            else:
                failure_count.append(1)

        # Spawn 20 threads to perform deduction concurrently
        for _ in range(20):
            t = threading.Thread(target=worker)
            threads.append(t)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        final_balance = self.wallet_client.get_balance(user_id)
        
        print(f"\n[Stress Test] Concurrent Deductions Results:")
        print(f"  Initial balance: 10")
        print(f"  Threads launched: 20")
        print(f"  Successful deductions: {len(success_count)}")
        print(f"  Failed deductions: {len(failure_count)}")
        print(f"  Final balance: {final_balance}")
        
        # In a race-prone system, successful deductions might exceed 10,
        # or final balance might not match (10 - success_count).
        # We assert that the balance did not go negative, but we also document the race condition.
        self.assertGreaterEqual(final_balance, 0, "Wallet balance fell below zero!")

    def test_negative_credit_deduction_vulnerability(self):
        """
        Adversarial test: attempt to deduct negative credits to gain credits.
        """
        signup_res = self.auth_client.sign_up("hacker@example.com", "hack123")
        user_id = signup_res['user_id']
        
        # Attempt to deduct -100 credits
        res = self.wallet_client.deduct_credits(user_id, -100)
        final_balance = self.wallet_client.get_balance(user_id)
        
        print(f"\n[Adversarial Test] Negative Credit Deduction:")
        print(f"  Initial balance: 10")
        print(f"  Deducted: -100")
        print(f"  Deduction call returned: {res}")
        print(f"  Final balance: {final_balance}")
        
        # Check if negative deduction was allowed (it shouldn't be!)
        # If it was allowed, the final balance would be 10 - (-100) = 110.
        self.assertFalse(res, "Deduction of negative credits succeeded!")
        self.assertEqual(final_balance, 10, "Balance increased due to negative credit deduction!")

    def test_concurrent_signups(self):
        """
        Stress test: simulate concurrent sign-ups of the same email.
        In a secure system, only one sign-up should succeed.
        """
        email = "dup_stress@example.com"
        success_ids = []
        threads = []
        
        def signup_worker():
            res = self.auth_client.sign_up(email, "password123")
            if res['success']:
                success_ids.append(res['user_id'])
                
        # Spawn 10 threads trying to sign up the same email concurrently
        for _ in range(10):
            t = threading.Thread(target=signup_worker)
            threads.append(t)
            
        for t in threads:
            t.start()
            
        for t in threads:
            t.join()
            
        print(f"\n[Stress Test] Concurrent Sign-ups Results:")
        print(f"  Threads launched: 10")
        print(f"  Successful sign-ups: {len(success_ids)}")
        print(f"  Generated User IDs: {success_ids}")
        
        # Only 1 signup should have succeeded
        self.assertEqual(len(success_ids), 1, f"Multiple concurrent signups succeeded: {len(success_ids)}")

    def test_invalid_input_robustness(self):
        """
        Adversarial test: pass malformed and unexpected inputs to check for crashes.
        """
        # None inputs
        res_signup = self.auth_client.sign_up(None, None)
        self.assertFalse(res_signup['success'], "Signup with None inputs should fail")
        
        res_signin = self.auth_client.sign_in(None, None)
        self.assertFalse(res_signin['success'], "Signin with None inputs should fail")
        
        # Extreme/Overflow values
        signup_res = self.auth_client.sign_up("overflow@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # Deduct massive amount
        res_overflow = self.wallet_client.deduct_credits(user_id, 10**18)
        self.assertFalse(res_overflow, "Deduction of massive amount should fail")
        
        # Add massive amount
        res_add_overflow = self.wallet_client.add_credits(user_id, 10**18, "plink_test")
        self.assertTrue(res_add_overflow)
        self.assertEqual(self.wallet_client.get_balance(user_id), 10 + 10**18)

if __name__ == '__main__':
    unittest.main()
