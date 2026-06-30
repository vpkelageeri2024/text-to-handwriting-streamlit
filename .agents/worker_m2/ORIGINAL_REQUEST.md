## 2026-06-30T11:34:21Z
You are a teamwork_preview_worker agent.
Your workspace directory is /home/vishal/text-to-handwriting-streamlit/.agents/worker_m2/.
Your objective is to implement the User Authentication & Credit Wallet System (Milestone 2) as defined in PROJECT.md at /home/vishal/text-to-handwriting-streamlit/PROJECT.md and following the interface contracts.
Specifically:
1. Implement supabase_client.py handling user signup, login, signout, getting balance, and credit addition/deduction. Make sure it supports both actual Supabase operations (using streamlit secrets) and a mock fallback/simulation mode when credentials are missing or for testing purposes.
2. Implement credit package payments in payments.py (simulating Razorpay payment flow or using the actual Razorpay client if configured).
3. Connect the authentication and credit check logic in app.py. Introduce login/signup tabs in the Streamlit interface (e.g. in the sidebar).
4. Implement a comprehensive test file test_auth.py containing tests for:
   - Account creation
   - Login/logout
   - Credit initialization (default: 10 free credits)
   - Credit deduction (charging 1 credit per generated page/document)
   - Blocking generation when credits are 0
5. Run the tests in test_auth.py and ensure they pass. Note: you must run the tests yourself inside your workspace and verify.
6. Verify layout compliance with PROJECT.md.
7. Output your handoff in handoff.md and progress in progress.md inside your workspace directory.
8. Report completion back to the parent (conversation ID: a98b1c63-4eac-4812-903f-0f83bf77a532) using the send_message tool.
