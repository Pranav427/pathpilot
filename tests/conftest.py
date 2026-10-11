import os

# The pre-existing suites exercise the India market. Tests for the UK default
# live in test_market.py and select the market explicitly.
os.environ.setdefault("PATHPILOT_COUNTRY", "IN")
