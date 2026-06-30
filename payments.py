import streamlit as st
import razorpay
import uuid
from typing import Tuple, Optional

try:
    RAZORPAY_KEY_ID: Optional[str] = st.secrets.get("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: Optional[str] = st.secrets.get("RAZORPAY_KEY_SECRET")
    PAYMENTS_ENABLED: bool = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
except Exception:
    RAZORPAY_KEY_ID = None
    RAZORPAY_KEY_SECRET = None
    PAYMENTS_ENABLED = False

# Mock payment database
_MOCK_PAYMENTS = {}

def _get_mock_payment_db():
    try:
        if hasattr(st, "session_state"):
            if "_mock_payments_db" not in st.session_state:
                st.session_state["_mock_payments_db"] = _MOCK_PAYMENTS
            return st.session_state["_mock_payments_db"]
    except Exception:
        pass
    return _MOCK_PAYMENTS

def create_credit_payment_link(amount_paise: int, credits: int, user_email: str) -> Tuple[Optional[str], Optional[str]]:
    """Generates Razorpay payment link. Returns (payment_link_id, payment_url)."""
    if PAYMENTS_ENABLED:
        try:
            rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            payment_data = {
                "amount": amount_paise,
                "currency": "INR",
                "description": f"Purchase of {credits} credits for {user_email}",
                "customer": {"name": "User", "email": user_email},
                "notify": {"email": False, "sms": False},
                "reminder_enable": False
            }
            payment_link = rzp_client.payment_link.create(payment_data)
            link_id = payment_link['id']
            # Register in our mock DB too to keep metadata
            db = _get_mock_payment_db()
            db[link_id] = {
                'amount_paise': amount_paise,
                'credits': credits,
                'email': user_email,
                'status': 'created'
            }
            return link_id, payment_link['short_url']
        except Exception as e:
            # Do not swallow payment link errors in production mode. Raise the exception!
            raise e
            
    # Mock fallback
    link_id = f"plink_{uuid.uuid4().hex[:12]}"
    payment_url = f"https://rzp.io/i/mock_{link_id}"
    
    db = _get_mock_payment_db()
    db[link_id] = {
        'amount_paise': amount_paise,
        'credits': credits,
        'email': user_email,
        'status': 'created'
    }
    
    return link_id, payment_url

def verify_payment_link(link_id: str) -> bool:
    """Returns True if completed, False otherwise."""
    db = _get_mock_payment_db()
    if link_id in db:
        if db[link_id]['status'] == 'paid':
            return True
            
    if PAYMENTS_ENABLED and not str(link_id).startswith("plink_"):
        try:
            rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
            link = rzp_client.payment_link.fetch(link_id)
            is_paid = link.get('status') == 'paid'
            if is_paid and link_id in db:
                db[link_id]['status'] = 'paid'
            return is_paid
        except Exception:
            return False
            
    return False

def simulate_payment_success(link_id: str) -> bool:
    """Simulates a successful payment for mock/test flows."""
    db = _get_mock_payment_db()
    if link_id in db:
        db[link_id]['status'] = 'paid'
        return True
    return False

# Legacy wrappers to maintain backward compatibility if needed
def create_payment_link(amount_paise: int, description: str, currency: str = "INR") -> Tuple[Optional[str], Optional[str]]:
    """Generates a generic payment link."""
    link_id, payment_url = create_credit_payment_link(amount_paise, amount_paise // 100, "user@example.com")
    return link_id, payment_url

def check_payment_status(link_id: str) -> bool:
    """Checks if a given payment link has been successfully paid."""
    return verify_payment_link(link_id)
