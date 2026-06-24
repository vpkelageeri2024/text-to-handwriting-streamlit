import streamlit as st
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="Text to Handwriting", layout="wide")

# Path to the directory containing index.html
frontend_dir = os.path.dirname(os.path.abspath(__file__))

# declare_component serves the directory and renders index.html
# It automatically handles CSS, JS, and image relative paths!
try:
    component_func = components.declare_component(
        "text_to_handwriting",
        path=frontend_dir
    )
    # Render the component
    component_func()
except Exception as e:
    st.error(f"Error loading component: {e}")
