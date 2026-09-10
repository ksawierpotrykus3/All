# coding: utf-8
"""Wyciaga funkcje initiatePayment z 0m6z-r2_~i3np.js."""
from pathlib import Path

js = Path("chunks_har/0m6z-r2_~i3np.js").read_text(encoding="utf-8", errors="replace")
print(f"LEN: {len(js)}")

# Pozycja 58357 - glowne wywolanie z updateSingleCheckoutPaymentFailure
i = js.find("updateSingleCheckoutPaymentFailure")
print("=" * 90)
print(f"### updateSingleCheckoutPaymentFailure @ {i} - 4500 przed, 1500 po ###")
print(js[max(0, i - 4500):i + 1500])
