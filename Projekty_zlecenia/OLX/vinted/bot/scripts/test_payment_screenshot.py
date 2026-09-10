import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from vintedbot.evidence import zapisz_dowody, _wypal_timestamp
from vintedbot.models import WynikCheckoutu
from PIL import Image

output_dir = REPO / "output" / "screens"
output_dir.mkdir(parents=True, exist_ok=True)

# 1. Tworzymy przykładowy obraz bazowy (jak screenshot z Camoufox)
sample_img = output_dir / "sample_payment_proof.png"
img = Image.new("RGB", (1280, 720), color=(30, 30, 40))
img.save(sample_img)

# 2. Definiujemy wynik płatności ze wszystkimi timingami kroków
w = WynikCheckoutu(
    checkout_id="chk_live_9859793702",
    status_build=200,
    status_pickup_details=200,
    status_payment=200,
    payment_status="SUCCESS",
    action_type="REDIRECT",
    redirect_url="https://live.adyen.com/hpp/pay.shtml?brandCode=visa",
    timings={
        "transaction": 969,
        "build+pickup_point": 1266,
        "put_pickup_details": 984,
        "payment": 320,
    },
    step_marks={
        "transaction": {"start_iso": "00:24:10.100Z", "end_iso": "00:24:11.069Z", "dur_ms": 969},
        "build+pickup_point": {"start_iso": "00:24:11.070Z", "end_iso": "00:24:12.336Z", "dur_ms": 1266},
        "put_pickup_details": {"start_iso": "00:24:12.337Z", "end_iso": "00:24:13.321Z", "dur_ms": 984},
        "payment": {"start_iso": "00:24:13.322Z", "end_iso": "00:24:13.642Z", "dur_ms": 320},
    }
)

# 3. Wypalamy timestampy na obrazie dowodowym
_wypal_timestamp(
    sample_img,
    kind="bramka_platnosci",
    url=w.redirect_url,
    step_marks=w.step_marks,
    timings=w.timings,
    payment_info=w.model_dump(),
)

# 4. Zapisujemy raport timingów
p = zapisz_dowody(w, prefix="payment_demo", timings=True, screenshot=False, payment=True)

print(f"Wygenerowano dowód ze screenshotem: {sample_img}")
print(f"Zapisano raport timingów: {p.get('timing_report')}")
