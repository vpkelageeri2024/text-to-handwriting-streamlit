import streamlit as st
import razorpay

# Try to get credentials, but don't set dummy ones if they fail.
# We'll use this to check if payments are enabled.
try:
    RAZORPAY_KEY_ID = st.secrets.get("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = st.secrets.get("RAZORPAY_KEY_SECRET")
    PAYMENTS_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
except Exception:
    RAZORPAY_KEY_ID = None
    RAZORPAY_KEY_SECRET = None
    PAYMENTS_ENABLED = False

def create_payment_link(amount_paise, description):
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

def check_payment_status(link_id):
    if not PAYMENTS_ENABLED:
        return False
        
    try:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        link = rzp_client.payment_link.fetch(link_id)
        return link.get('status') == 'paid'
    except Exception as e:
        st.error(f"Failed to check payment status: {e}")
        return False
