from typing import Any
from pydantic import BaseModel, Field, model_validator, field_validator
from .config import CSRF_DEFAULT, ANON_DEFAULT, IMPERSONATE


class Filtry(BaseModel):
    brand_ids: list[int] = Field(default_factory=list)
    size_ids: list[int] = Field(default_factory=list)
    status_ids: list[int] = Field(default_factory=list)
    search_text: str | None = None
    price_from: float | None = None
    price_to: float | None = None

    def query_params(self) -> dict:
        params = {}
        if self.brand_ids:
            params["brand_ids"] = ",".join(map(str, self.brand_ids))
        if self.size_ids:
            params["size_ids"] = ",".join(map(str, self.size_ids))
        if self.status_ids:
            params["status_ids"] = ",".join(map(str, self.status_ids))
        if self.search_text:
            params["search_text"] = self.search_text
        if self.price_from is not None:
            params["price_from"] = self.price_from
        if self.price_to is not None:
            params["price_to"] = self.price_to
        return params


class Oferta(BaseModel):
    id: int
    title: str
    price: dict
    brand_title: str | None = None
    seller_id: int | None = None
    # Telemetria z etapu wykrycia oferty
    detection_span: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _wyciagnij_seller(cls, v):
        if isinstance(v, dict) and "seller_id" not in v and isinstance(v.get("user"), dict):
            v = dict(v)
            v["seller_id"] = v["user"].get("id")
        return v

    @field_validator("price")
    @classmethod
    def _price_dict(cls, v):
        return v

    @property
    def cena(self) -> float:
        return float(self.price.get("amount", 0))


class KonfiguracjaKonta(BaseModel):
    csrf: str = CSRF_DEFAULT
    anon_id: str = ANON_DEFAULT
    impersonate: str = IMPERSONATE
    cookies: dict[str, str] = Field(default_factory=dict)
    # Adres odbioru (stały per konto) — do równoległego pickup_point bez czekania na build.
    lat: float | None = None
    lon: float | None = None
    # Numeryczne ID użytkownika (z /users/current) — wymagane przez check_availability (O2).
    user_id: int | None = None

    @model_validator(mode="after")
    def _uzupelnij_z_cookies(self) -> "KonfiguracjaKonta":
        """Automatycznie uzupełnia anon_id i csrf z cookies jeśli nie zostały jawnie ustawione."""
        from .config import csrf_z_cookies as _csrf_z_cookies  # lokalny import unika cyrkularności
        cookies = self.cookies
        # anon_id z cookies ma priorytet nad ANON_DEFAULT
        if self.anon_id == ANON_DEFAULT and cookies.get("anon_id"):
            self.anon_id = cookies["anon_id"]
        # csrf z JWT access_token_web ma priorytet nad CSRF_DEFAULT
        if self.csrf == CSRF_DEFAULT:
            csrf_jwt = _csrf_z_cookies(cookies)
            if csrf_jwt:
                self.csrf = csrf_jwt
        return self



class WynikCheckoutu(BaseModel):
    purchase_id: str | None = None
    checkout_id: str | None = None
    transaction_id: str | None = None
    status_build: int | None = None
    status_payment_method: int | None = None
    status_pickup_details: int | None = None
    status_payment: int | None = None
    payment_status: str | None = None
    redirect_url: str | None = None
    action_type: str | None = None
    action_payload: dict | None = None
    correlation_id: str | None = None
    error_code: int | None = None
    # Fragment odpowiedzi gdy build != 200 (diagnostyka 403 DataDome vs Vinted).
    build_error: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    # Szczegółowe timestampy każdego kroku: {"krok": {"start_ms", "end_ms", "dur_ms", "iso"}}
    step_marks: dict[str, dict] = Field(default_factory=dict)

    # Rozszerzona telemetria v2 (Full-Lifecycle Distributed Trace)
    trace_id: str | None = None
    spans: dict[str, dict[str, Any]] = Field(default_factory=dict)
    summary_timings: dict[str, Any] = Field(default_factory=dict)
    network_telemetry: dict[str, Any] = Field(default_factory=dict)
