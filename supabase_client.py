import streamlit as st
import uuid
import threading
import re
from typing import Optional

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

_LOCK = threading.RLock()

def validate_auth_inputs(email: Optional[str], password: Optional[str]) -> Optional[str]:
    """Validates email and password inputs. Returns error message if invalid, else None."""
    if email is None or not isinstance(email, str) or not email.strip():
        return "Email cannot be empty"
    if password is None or not isinstance(password, str) or not password.strip():
        return "Password cannot be empty"
        
    email_regex = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    if not email_regex.match(email.strip()):
        return "Invalid email format"
        
    return None

# Module-level store (primarily for unit tests and simple persistence)
_MOCK_DB = {
    "users": {},       # email -> {password, user_id}
    "balances": {},    # user_id -> balance
    "transactions": [] # list of transaction dicts
}

def _get_mock_db():
    try:
        if hasattr(st, "session_state"):
            if "_mock_supabase_db" not in st.session_state:
                st.session_state["_mock_supabase_db"] = _MOCK_DB
            return st.session_state["_mock_supabase_db"]
    except Exception:
        pass
    return _MOCK_DB

class SupabaseAuthClient:
    def __init__(self, url: str, key: str, use_mock: bool = False):
        self.url = url
        self.key = key
        self.use_mock = use_mock or not url or not key or not SUPABASE_AVAILABLE
        self.client = None
        if not self.use_mock:
            try:
                self.client = create_client(self.url, self.key)
            except Exception:
                self.use_mock = True

    def sign_up(self, email, password) -> dict:
        """Returns {'success': bool, 'user_id': str, 'error': str}"""
        validation_error = validate_auth_inputs(email, password)
        if validation_error:
            return {'success': False, 'user_id': '', 'error': validation_error}

        if self.use_mock:
            with _LOCK:
                db = _get_mock_db()
                if email in db["users"]:
                    return {'success': False, 'user_id': '', 'error': 'User already exists'}
                user_id = str(uuid.uuid4())
                db["users"][email] = {'password': password, 'user_id': user_id}
                # Credit initialization (default: 10 free credits)
                db["balances"][user_id] = 10
                return {'success': True, 'user_id': user_id, 'error': ''}
        else:
            try:
                response = self.client.auth.sign_up({
                    "email": email,
                    "password": password,
                })
                if response.user and response.user.id:
                    user_id = response.user.id
                    # Initialize default wallet balance in the database if possible
                    try:
                        self.client.table("wallets").insert({"user_id": user_id, "balance": 10}).execute()
                    except Exception:
                        try:
                            self.client.table("profiles").insert({"id": user_id, "balance": 10}).execute()
                        except Exception:
                            pass
                    return {'success': True, 'user_id': user_id, 'error': ''}
                else:
                    return {'success': False, 'user_id': '', 'error': 'Signup failed'}
            except Exception as e:
                return {'success': False, 'user_id': '', 'error': str(e)}

    def sign_in(self, email, password) -> dict:
        """Returns {'success': bool, 'session': dict, 'error': str}"""
        validation_error = validate_auth_inputs(email, password)
        if validation_error:
            return {'success': False, 'session': None, 'error': validation_error}

        if self.use_mock:
            with _LOCK:
                db = _get_mock_db()
                if email in db["users"] and db["users"][email]['password'] == password:
                    user_id = db["users"][email]['user_id']
                    session = {'user': {'id': user_id, 'email': email}}
                    return {'success': True, 'session': session, 'error': ''}
                return {'success': False, 'session': None, 'error': 'Invalid email or password'}
        else:
            try:
                response = self.client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if response.session:
                    session_dict = {
                        'user': {
                            'id': response.user.id,
                            'email': response.user.email
                        },
                        'access_token': response.session.access_token
                    }
                    return {'success': True, 'session': session_dict, 'error': ''}
                else:
                    return {'success': False, 'session': None, 'error': 'Invalid sign in response'}
            except Exception as e:
                return {'success': False, 'session': None, 'error': str(e)}

    def sign_out(self) -> None:
        """Signs out the current user session."""
        if not self.use_mock:
            try:
                self.client.auth.sign_out()
            except Exception:
                pass

class SupabaseWalletClient:
    def __init__(self, url: str, key: str, use_mock: bool = False):
        self.url = url
        self.key = key
        self.use_mock = use_mock or not url or not key or not SUPABASE_AVAILABLE
        self.client = None
        if not self.use_mock:
            try:
                self.client = create_client(self.url, self.key)
            except Exception:
                self.use_mock = True

    def get_balance(self, user_id) -> int:
        """Returns current credit balance."""
        if self.use_mock:
            with _LOCK:
                db = _get_mock_db()
                if user_id not in db["balances"]:
                    db["balances"][user_id] = 10
                return db["balances"][user_id]
        else:
            try:
                res = self.client.table("wallets").select("balance").eq("user_id", user_id).execute()
                if res.data:
                    return int(res.data[0]["balance"])
                res = self.client.table("profiles").select("balance").eq("id", user_id).execute()
                if res.data:
                    return int(res.data[0]["balance"])
                return 10
            except Exception:
                return 10

    def deduct_credits(self, user_id, amount) -> bool:
        """Deducts amount credits. Returns True if success, False if insufficient."""
        if amount <= 0:
            return False
            
        if self.use_mock:
            with _LOCK:
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
        else:
            try:
                # 1. Try atomic database update via RPC
                try:
                    res = self.client.rpc("deduct_wallet_credits", {
                        "p_user_id": user_id,
                        "p_amount": amount
                    }).execute()
                    if res.data is not None:
                        return bool(res.data)
                except Exception:
                    pass # Fallback to standard check-and-update
                
                # 2. Query-based fallback (check-and-update)
                balance = self.get_balance(user_id)
                if balance < amount:
                    return False
                new_balance = balance - amount
                
                updated = False
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
            except Exception:
                return False

    def add_credits(self, user_id, amount, payment_link_id) -> bool:
        """Logs transaction and updates balance."""
        if amount <= 0:
            return False
            
        if self.use_mock:
            with _LOCK:
                db = _get_mock_db()
                if payment_link_id:
                    for tx in db["transactions"]:
                        if tx.get("payment_link_id") == payment_link_id:
                            return False
                
                # Record transaction log entry BEFORE updating balance
                db["transactions"].append({
                    "user_id": user_id,
                    "amount": amount,
                    "payment_link_id": payment_link_id,
                    "type": "addition"
                })
                
                current_balance = db["balances"].get(user_id, 10)
                db["balances"][user_id] = current_balance + amount
                return True
        else:
            try:
                # 1. Try atomic database update via RPC
                try:
                    res = self.client.rpc("add_wallet_credits", {
                        "p_user_id": user_id,
                        "p_amount": amount,
                        "p_payment_link_id": payment_link_id
                    }).execute()
                    if res.data is not None:
                        return bool(res.data)
                except Exception:
                    pass # Fallback to query-based update
                
                # 2. Check if payment transaction already exists
                if payment_link_id:
                    res_tx = self.client.table("transactions").select("id").eq("payment_link_id", payment_link_id).execute()
                    if res_tx.data:
                        # Transaction already logged/completed
                        return False
                
                # 3. Log transaction FIRST (Payment Replay Prevention)
                try:
                    self.client.table("transactions").insert({
                        "user_id": user_id,
                        "amount": amount,
                        "payment_link_id": payment_link_id,
                        "type": "addition"
                    }).execute()
                except Exception:
                    # If transaction log insert fails, do not proceed (e.g. UNIQUE constraint violation)
                    return False
                
                # 4. Update wallet balance
                balance = self.get_balance(user_id)
                new_balance = balance + amount
                
                updated = False
                try:
                    res = self.client.table("wallets").update({"balance": new_balance}).eq("user_id", user_id).execute()
                    if res.data:
                        updated = True
                except Exception:
                    pass
                
                if not updated:
                    res = self.client.table("profiles").update({"balance": new_balance}).eq("id", user_id).execute()
                
                return True
            except Exception:
                return False
