import streamlit as st
import razorpay
from typing import Tuple, Optional

try:
    RAZORPAY_KEY_ID: Optional[str] = st.secrets.get("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: Optional[str] = st.secrets.get("RAZORPAY_KEY_SECRET")
    PAYMENTS_ENABLED: bool = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
except Exception:
    RAZORPAY_KEY_ID = None
    RAZORPAY_KEY_SECRET = None
    PAYMENTS_ENABLED = False

def create_payment_link(amount_paise: int, description: str) -> Tuple[Optional[str], Optional[str]]:
    """Generates a Razorpay payment link for unlocking high-res exports."""
    if not PAYMENTS_ENABLED:
        st.error("Payments are currently disabled by the administrator.")
        return None, None
        
    try:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        payment_data = {
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "customer": {"name": "User", "email": "user@example.com"},
            "notify": {"email": False, "sms": False},
            "reminder_enable": False
        }
        payment_link = rzp_client.payment_link.create(payment_data)
        return payment_link['id'], payment_link['short_url']
    except Exception as e:
        st.error(f"Razorpay Error: {e}")
        return None, None

def check_payment_status(link_id: str) -> bool:
    """Checks if a given payment link has been successfully paid."""
    if not PAYMENTS_ENABLED:
        return False
        
    try:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        link = rzp_client.payment_link.fetch(link_id)
        return link.get('status') == 'paid'
    except Exception as e:
        st.error(f"Failed to check payment status: {e}")
        return False
