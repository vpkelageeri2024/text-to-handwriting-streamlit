import unittest
import os
from supabase_client import SupabaseAuthClient, SupabaseWalletClient, _get_mock_db
from payments import create_credit_payment_link, verify_payment_link, simulate_payment_success

class TestAuthAndWalletSystem(unittest.TestCase):
    def setUp(self):
        # Reset mock database before each test
        db = _get_mock_db()
        db["users"].clear()
        db["balances"].clear()
        db["transactions"].clear()
        
        # Instantiate clients in mock mode for testing
        self.auth_client = SupabaseAuthClient(url="", key="", use_mock=True)
        self.wallet_client = SupabaseWalletClient(url="", key="", use_mock=True)

    def test_account_creation(self):
        # 1. Successful account creation
        result = self.auth_client.sign_up("user@example.com", "securepassword123")
        self.assertTrue(result['success'])
        self.assertNotEqual(result['user_id'], '')
        self.assertEqual(result['error'], '')
        
        # 2. Duplicate account creation should fail
        result_duplicate = self.auth_client.sign_up("user@example.com", "anotherpassword")
        self.assertFalse(result_duplicate['success'])
        self.assertEqual(result_duplicate['user_id'], '')
        self.assertEqual(result_duplicate['error'], 'User already exists')

    def test_login_logout(self):
        # Setup user
        signup_res = self.auth_client.sign_up("login_user@example.com", "mypassword")
        self.assertTrue(signup_res['success'])
        
        # 1. Login success
        login_res = self.auth_client.sign_in("login_user@example.com", "mypassword")
        self.assertTrue(login_res['success'])
        self.assertIsNotNone(login_res['session'])
        self.assertEqual(login_res['session']['user']['email'], "login_user@example.com")
        self.assertEqual(login_res['session']['user']['id'], signup_res['user_id'])
        self.assertEqual(login_res['error'], '')
        
        # 2. Login failure (wrong password)
        login_fail_pwd = self.auth_client.sign_in("login_user@example.com", "wrongpassword")
        self.assertFalse(login_fail_pwd['success'])
        self.assertIsNone(login_fail_pwd['session'])
        self.assertEqual(login_fail_pwd['error'], 'Invalid email or password')
        
        # 3. Login failure (non-existent email)
        login_fail_email = self.auth_client.sign_in("nonexistent@example.com", "password")
        self.assertFalse(login_fail_email['success'])
        
        # 4. Logout (does not crash/throw errors)
        self.auth_client.sign_out()

    def test_credit_initialization(self):
        # Signup user
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # Verify default credits is 10
        balance = self.wallet_client.get_balance(user_id)
        self.assertEqual(balance, 10)

    def test_credit_deduction(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # 1. Deduct 1 credit (e.g. for generating one page/document)
        deduct_res = self.wallet_client.deduct_credits(user_id, 1)
        self.assertTrue(deduct_res)
        self.assertEqual(self.wallet_client.get_balance(user_id), 9)
        
        # 2. Deduct multiple credits
        deduct_res2 = self.wallet_client.deduct_credits(user_id, 5)
        self.assertTrue(deduct_res2)
        self.assertEqual(self.wallet_client.get_balance(user_id), 4)

    def test_blocking_generation_when_credits_zero(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # 1. Deduct all 10 credits
        self.assertTrue(self.wallet_client.deduct_credits(user_id, 10))
        self.assertEqual(self.wallet_client.get_balance(user_id), 0)
        
        # 2. Try to deduct another credit (should fail/block generation)
        deduct_fail = self.wallet_client.deduct_credits(user_id, 1)
        self.assertFalse(deduct_fail)
        self.assertEqual(self.wallet_client.get_balance(user_id), 0)
        
        # 3. Simulate generation blocking logic
        def attempt_generation(user_id, pages):
            # Generate logic: we charge 1 credit per page
            cost = pages
            if self.wallet_client.get_balance(user_id) >= cost:
                self.wallet_client.deduct_credits(user_id, cost)
                return True, "Handwriting generated successfully"
            else:
                return False, "Insufficient credits. Please purchase a credit package."
                
        # Generate with 0 credits should fail
        success, msg = attempt_generation(user_id, 1)
        self.assertFalse(success)
        self.assertEqual(msg, "Insufficient credits. Please purchase a credit package.")
        
    def test_payment_and_credit_addition(self):
        signup_res = self.auth_client.sign_up("wallet_user@example.com", "pass123")
        user_id = signup_res['user_id']
        
        # 1. Create a payment link for adding 20 credits (cost: ₹100, i.e., 10000 paise)
        credits_to_buy = 20
        amount_paise = 10000
        link_id, payment_url = create_credit_payment_link(amount_paise, credits_to_buy, "wallet_user@example.com")
        self.assertIsNotNone(link_id)
        self.assertTrue(payment_url.startswith("https://"))
        
        # 2. Verify payment link before paying -> should be False
        self.assertFalse(verify_payment_link(link_id))
        
        # 3. Simulate successful payment completion
        self.assertTrue(simulate_payment_success(link_id))
        
        # 4. Verify payment link after paying -> should be True
        self.assertTrue(verify_payment_link(link_id))
        
        # 5. Add credits to wallet based on the payment success
        add_res = self.wallet_client.add_credits(user_id, credits_to_buy, link_id)
        self.assertTrue(add_res)
        
        # 6. Verify updated balance is now 10 + 20 = 30 credits
        self.assertEqual(self.wallet_client.get_balance(user_id), 30)

if __name__ == '__main__':
    unittest.main()
