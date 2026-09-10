from unittest.mock import patch

from redis.exceptions import ConnectionError as RedisConnectionError


class _FakeRedis:
    """Minimal in-memory Redis stub (idempotency set + rate limit incr/expire)."""

    def __init__(self):
        self._keys = set()
        self.counts = {}
        self.ttls = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self._keys:
            return None
        self._keys.add(key)
        return True

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    async def close(self):
        return None


class _BrokenRedis:
    """Redis stub that simulates a connection failure on every call."""

    async def incr(self, key):
        raise RedisConnectionError("down")


class TestAuth:
    def test_register(self, client):
        resp = client.post("/auth/register", json={"email": "t@x.com", "password": "abcdefgh"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_register_short_password_rejected(self, client):
        resp = client.post("/auth/register", json={"email": "t@x.com", "password": "abcde"})
        assert resp.status_code == 422

    def test_register_creates_inactive_license(self, client, db_session):
        """A registered-but-unpaid user must NOT get a working license."""
        from mvp.backend.models import License, User

        resp = client.post("/auth/register", json={"email": "unpaid@x.com", "password": "abcdefgh"})
        assert resp.status_code == 200
        user = db_session.query(User).filter(User.email == "unpaid@x.com").first()
        assert user is not None
        lic = db_session.query(License).filter(License.user_id == user.id).first()
        assert lic is not None
        assert lic.is_active is False
        r = client.post("/license/validate", json={"license_key": lic.key})
        assert r.status_code == 200
        payload = r.json().get("signed_payload") or r.json()
        assert payload["valid"] is False


class TestLicense:
    def test_validate_good(self, client, db_session):
        from mvp.backend.models import License, User

        u = User(email="good@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LZ-TEST01", is_active=True)
        db_session.add(lic)
        db_session.commit()
        r = client.post("/license/validate", json={"license_key": "LZ-TEST01"})
        assert r.status_code == 200
        payload = r.json().get("signed_payload") or r.json()
        assert payload["valid"] is True

    def test_validate_future_expiry_ok(self, client, db_session):
        from datetime import UTC, datetime, timedelta

        from mvp.backend.models import License, User

        u = User(email="future@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(
            user_id=u.id,
            key="LZ-FUT1",
            is_active=True,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db_session.add(lic)
        db_session.commit()
        # SQLite round-trip: datetimes come back naive (no tzinfo) - no TypeError expected.
        db_session.refresh(lic)
        assert lic.expires_at is not None
        assert lic.expires_at.tzinfo is None
        r = client.post("/license/validate", json={"license_key": "LZ-FUT1"})
        assert r.status_code == 200
        body = r.json().get("signed_payload") or r.json()
        assert body["valid"] is True
        assert body["message"] == "OK"
        assert body["expires_at"] is not None

    def test_validate_grace_period_ok(self, client, db_session):
        from datetime import UTC, datetime, timedelta

        from mvp.backend.models import License, User

        u = User(email="grace@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(
            user_id=u.id,
            key="LZ-GRACE1",
            is_active=True,
            expires_at=datetime.now(UTC) - timedelta(hours=12),
        )
        db_session.add(lic)
        db_session.commit()
        r = client.post(
            "/license/validate",
            json={"license_key": "LZ-GRACE1", "hwid": "HW-GRACE"},
        )
        assert r.status_code == 200
        body = r.json().get("signed_payload") or r.json()
        assert body["valid"] is True
        assert body["message"] == "License in grace period"
        # Grace still runs the normal flow: hwid binding + last_validated_at update.
        db_session.refresh(lic)
        assert lic.hwid == "HW-GRACE"
        assert lic.last_validated_at is not None

    def test_validate_expired_beyond_grace_rejected(self, client, db_session):
        from datetime import UTC, datetime, timedelta

        from mvp.backend.models import License, User

        u = User(email="expired@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(
            user_id=u.id,
            key="LZ-EXP1",
            is_active=True,
            expires_at=datetime.now(UTC) - timedelta(hours=48),
        )
        db_session.add(lic)
        db_session.commit()
        r = client.post("/license/validate", json={"license_key": "LZ-EXP1"})
        assert r.status_code == 200
        body = r.json().get("signed_payload") or r.json()
        assert body["valid"] is False
        assert body["message"] == "License expired"

    def test_validate_fail_closed_without_signing_key(self, client, db_session, monkeypatch):
        """No signing key + unsigned responses disallowed -> 503 (fail-closed)."""
        import mvp.backend.config as config_module
        from mvp.backend.models import License, User

        u = User(email="fc@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LZ-FC1", is_active=True)
        db_session.add(lic)
        db_session.commit()
        monkeypatch.setattr(config_module.settings, "license_private_key_pem", "")
        monkeypatch.setattr(config_module.settings, "allow_unsigned_license_response", False)
        r = client.post("/license/validate", json={"license_key": "LZ-FC1"})
        assert r.status_code == 503


class TestWebhook:
    def test_invoice_success(self, client, db_session):
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="inv@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-INV1", is_active=False)
        db_session.add(lic)
        sc = StripeCustomer(
            user_id=u.id, stripe_customer_id="cs_88", subscription_status="inactive"
        )
        db_session.add(sc)
        db_session.commit()
        with (
            patch("stripe.Webhook.construct_event") as mk,
            patch("mvp.backend.main._check_event_idempotent", return_value=True),
        ):
            mk.return_value = {
                "id": "evt_test_123",
                "type": "invoice.payment_succeeded",
                "data": {"object": {"customer": "cs_88"}},
            }
            resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
            assert resp.status_code == 200
        db_session.refresh(sc)
        assert sc.subscription_status == "active"
        db_session.refresh(lic)
        assert lic.is_active is True

    def test_invoice_paid_activates_license(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="paid@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-PAID1", is_active=False)
        db_session.add(lic)
        sc = StripeCustomer(
            user_id=u.id, stripe_customer_id="cs_paid", subscription_status="inactive"
        )
        db_session.add(sc)
        db_session.commit()
        main_module.redis_client = _FakeRedis()
        try:
            with patch("stripe.Webhook.construct_event") as mk:
                mk.return_value = {
                    "id": "evt_paid_1",
                    "type": "invoice.paid",
                    "data": {"object": {"customer": "cs_paid"}},
                }
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
                assert resp.status_code == 200
        finally:
            main_module.redis_client = None
        db_session.refresh(sc)
        assert sc.subscription_status == "active"
        db_session.refresh(lic)
        assert lic.is_active is True
        assert lic.expires_at is not None

    def test_invoice_payment_failed_suspends_license(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="fail@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-FAIL1", is_active=True)
        db_session.add(lic)
        sc = StripeCustomer(
            user_id=u.id, stripe_customer_id="cs_fail", subscription_status="active"
        )
        db_session.add(sc)
        db_session.commit()
        main_module.redis_client = _FakeRedis()
        try:
            with patch("stripe.Webhook.construct_event") as mk:
                mk.return_value = {
                    "id": "evt_fail_1",
                    "type": "invoice.payment_failed",
                    "data": {"object": {"customer": "cs_fail"}},
                }
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
                assert resp.status_code == 200
        finally:
            main_module.redis_client = None
        db_session.refresh(sc)
        assert sc.subscription_status == "past_due"
        db_session.refresh(lic)
        assert lic.is_active is False

    def test_subscription_updated_canceled_suspends_license(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="sub@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-SUB1", is_active=True)
        db_session.add(lic)
        sc = StripeCustomer(user_id=u.id, stripe_customer_id="cs_sub", subscription_status="active")
        db_session.add(sc)
        db_session.commit()
        main_module.redis_client = _FakeRedis()
        try:
            with patch("stripe.Webhook.construct_event") as mk:
                mk.return_value = {
                    "id": "evt_sub_1",
                    "type": "customer.subscription.updated",
                    "data": {"object": {"customer": "cs_sub", "status": "canceled"}},
                }
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
                assert resp.status_code == 200
        finally:
            main_module.redis_client = None
        db_session.refresh(sc)
        assert sc.subscription_status == "canceled"
        db_session.refresh(lic)
        assert lic.is_active is False

    def test_subscription_updated_active_keeps_license_active(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="sub2@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-SUB2", is_active=True)
        db_session.add(lic)
        sc = StripeCustomer(
            user_id=u.id, stripe_customer_id="cs_sub2", subscription_status="active"
        )
        db_session.add(sc)
        db_session.commit()
        main_module.redis_client = _FakeRedis()
        try:
            with patch("stripe.Webhook.construct_event") as mk:
                mk.return_value = {
                    "id": "evt_sub_2",
                    "type": "customer.subscription.updated",
                    "data": {"object": {"customer": "cs_sub2", "status": "active"}},
                }
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
                assert resp.status_code == 200
        finally:
            main_module.redis_client = None
        db_session.refresh(sc)
        assert sc.subscription_status == "active"
        db_session.refresh(lic)
        assert lic.is_active is True

    def test_webhook_fail_closed_without_redis(self, client):
        from starlette.testclient import TestClient

        import mvp.backend.main as main_module

        # Expect the app to raise (not re-raise) on unhandled exceptions, so
        # build a dedicated client with raise_server_exceptions=False.
        local_client = TestClient(main_module.app, raise_server_exceptions=False)
        with local_client:
            main_module.redis_client = None  # no Redis — fail-closed
            with patch("stripe.Webhook.construct_event") as mk:
                mk.return_value = {
                    "id": "evt_dup",
                    "type": "invoice.paid",
                    "data": {"object": {"customer": "cs_none"}},
                }
                resp = local_client.post(
                    "/stripe/webhook", json={}, headers={"stripe-signature": "sig"}
                )
        assert resp.status_code in (500, 503)

    def test_duplicate_event_id_is_rejected(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, StripeCustomer, User

        u = User(email="dup@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-DUP1", is_active=False)
        db_session.add(lic)
        sc = StripeCustomer(
            user_id=u.id, stripe_customer_id="cs_dup", subscription_status="inactive"
        )
        db_session.add(sc)
        db_session.commit()
        main_module.redis_client = _FakeRedis()
        try:
            event = {
                "id": "evt_dup_1",
                "type": "invoice.paid",
                "data": {"object": {"customer": "cs_dup"}},
            }
            with patch("stripe.Webhook.construct_event", return_value=event):
                first = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
                second = client.post(
                    "/stripe/webhook", json={}, headers={"stripe-signature": "sig"}
                )
            assert first.status_code == 200
            assert first.json() == {"status": "ok"}
            assert second.status_code == 200
            assert second.json() == {"status": "ignored", "reason": "duplicate_event"}
        finally:
            main_module.redis_client = None
        db_session.refresh(lic)
        assert lic.is_active is True


class TestRateLimit:
    def test_429_on_excess(self, client):
        import mvp.backend.main as main_module

        fake = _FakeRedis()
        main_module.redis_client = fake
        try:
            for _ in range(5):
                resp = client.post("/license/validate", json={"license_key": "fake-99"})
                assert resp.status_code == 200
            assert fake.ttls["rate:license:fake-99"] == 60
            resp = client.post("/license/validate", json={"license_key": "fake-99"})
            assert resp.status_code == 429
        finally:
            main_module.redis_client = None

    def test_fail_open_when_redis_down(self, client):
        import mvp.backend.main as main_module

        main_module.redis_client = _BrokenRedis()
        try:
            resp = client.post("/license/validate", json={"license_key": "fake-99"})
            assert resp.status_code == 200
        finally:
            main_module.redis_client = None

    def test_503_when_fail_closed_and_redis_down(self, client):
        import mvp.backend.config as config_module
        import mvp.backend.main as main_module

        main_module.redis_client = None
        with patch.object(config_module.settings, "rate_limit_fail_closed", True):
            resp = client.post("/license/validate", json={"license_key": "fake-99"})
        assert resp.status_code == 503

    def test_503_when_fail_closed_and_redis_errors(self, client):
        import mvp.backend.config as config_module
        import mvp.backend.main as main_module

        main_module.redis_client = _BrokenRedis()
        try:
            with patch.object(config_module.settings, "rate_limit_fail_closed", True):
                resp = client.post("/license/validate", json={"license_key": "fake-99"})
            assert resp.status_code == 503
        finally:
            main_module.redis_client = None


class TestAdminCreateLicense:
    def test_admin_create_license_via_body(self, client, db_session):
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        admin = User(email="admin2@x.com", password_hash="x", is_admin=True)
        target = User(email="buyer@x.com", password_hash="x")
        db_session.add_all([admin, target])
        db_session.commit()

        token = create_access_token(admin.id)
        resp = client.post(
            "/admin/licenses",
            json={"user_email": "buyer@x.com", "expires_in_days": 7},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["user_email"] == "buyer@x.com"
        assert body["license_key"].startswith("LZ-")

    def test_admin_create_license_forbidden(self, client, db_session):
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="plain2@x.com", password_hash="x", is_admin=False)
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)
        resp = client.post(
            "/admin/licenses",
            json={"user_email": "buyer@x.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestAdminResetHwid:
    def test_admin_reset_hwid_ok(self, client, db_session):
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import License, User

        admin = User(email="admin@x.com", password_hash="x", is_admin=True)
        db_session.add(admin)
        db_session.flush()
        lic = License(user_id=admin.id, key="LZ-RESET1", is_active=True, hwid="HW-OLD")
        db_session.add(lic)
        db_session.commit()

        token = create_access_token(admin.id)
        resp = client.post(
            "/admin/licenses/reset-hwid",
            json={"license_key": "LZ-RESET1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        db_session.refresh(lic)
        assert lic.hwid is None

    def test_admin_reset_hwid_forbidden(self, client, db_session):
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import License, User

        u = User(email="plain@x.com", password_hash="x", is_admin=False)
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LZ-RESET2", is_active=True, hwid="HW-OLD")
        db_session.add(lic)
        db_session.commit()

        token = create_access_token(u.id)
        resp = client.post(
            "/admin/licenses/reset-hwid",
            json={"license_key": "LZ-RESET2"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestAuthRateLimit:
    def test_login_429_after_10_attempts(self, client):
        import mvp.backend.main as main_module

        fake = _FakeRedis()
        main_module.redis_client = fake
        try:
            for _ in range(10):
                resp = client.post(
                    "/auth/login", json={"email": "rl@x.com", "password": "abcdefgh"}
                )
                assert resp.status_code == 401
            assert fake.ttls["rate:auth:rl@x.com"] == 300
            resp = client.post("/auth/login", json={"email": "rl@x.com", "password": "abcdefgh"})
            assert resp.status_code == 429
        finally:
            main_module.redis_client = None


class TestCheckoutSession:
    def test_create_session_requires_auth(self, client):
        resp = client.post(
            "/checkout/session",
            json={"success_url": "https://localhost/s", "cancel_url": "https://localhost/c"},
        )
        assert resp.status_code == 401

    def test_create_session_rejects_untrusted_domain(self, client, db_session):
        import mvp.backend.config as config_module
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="buyer@x.com", password_hash="x")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)

        with patch.object(config_module.settings, "checkout_allowed_domains", "localhost"):
            resp = client.post(
                "/checkout/session",
                json={"success_url": "https://evil.example/s", "cancel_url": "https://localhost/c"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid checkout URL domain"

    def test_create_session_rejects_non_http_url(self, client, db_session):
        import mvp.backend.config as config_module
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="buyer2@x.com", password_hash="x")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)

        with patch.object(config_module.settings, "checkout_allowed_domains", "localhost"):
            resp = client.post(
                "/checkout/session",
                json={"success_url": "javascript:alert(1)", "cancel_url": "https://localhost/c"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 422

    def test_create_session_ok(self, client, db_session):
        import mvp.backend.config as config_module
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="buyer@x.com", password_hash="x")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)

        class _Session:
            url = "https://checkout.stripe.com/c/pay/test"

        with (
            patch("stripe.checkout.Session.create", return_value=_Session()),
            patch.object(config_module.settings, "stripe_price_id", "price_test"),
            patch.object(config_module.settings, "checkout_allowed_domains", "localhost"),
        ):
            resp = client.post(
                "/checkout/session",
                json={"success_url": "https://localhost/s", "cancel_url": "https://localhost/c"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"].startswith("https://checkout.stripe.com")

    def test_create_session_no_price_configured(self, client, db_session):
        import mvp.backend.config as config_module
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="noprice@x.com", password_hash="x")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)
        with (
            patch.object(config_module.settings, "stripe_price_id", ""),
            patch.object(config_module.settings, "checkout_allowed_domains", "localhost"),
        ):
            resp = client.post(
                "/checkout/session",
                json={"success_url": "https://localhost/s", "cancel_url": "https://localhost/c"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Stripe price ID is not configured"

    def test_create_session_stripe_error_does_not_leak(self, client, db_session):
        import mvp.backend.config as config_module
        from mvp.backend.auth import create_access_token
        from mvp.backend.models import User

        u = User(email="stripefail@x.com", password_hash="x")
        db_session.add(u)
        db_session.commit()
        token = create_access_token(u.id)

        import stripe

        with (
            patch.object(config_module.settings, "stripe_price_id", "price_test"),
            patch.object(config_module.settings, "checkout_allowed_domains", "localhost"),
            patch(
                "stripe.checkout.Session.create",
                side_effect=stripe.StripeError("sk_live_secret_should_not_leak"),
            ),
        ):
            resp = client.post(
                "/checkout/session",
                json={"success_url": "https://localhost/s", "cancel_url": "https://localhost/c"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert detail == "Failed to create Stripe checkout session"
        assert "sk_live" not in detail

    def test_checkout_completed_activates_by_client_reference_id(self, client, db_session):
        import mvp.backend.main as main_module
        from mvp.backend.models import License, User

        u = User(email="cr@x.com", password_hash="x")
        db_session.add(u)
        db_session.flush()
        lic = License(user_id=u.id, key="LK-CR1", is_active=False)
        db_session.add(lic)
        db_session.commit()

        main_module.redis_client = _FakeRedis()
        try:
            event = {
                "id": "evt_cr_1",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer_email": "inny@x.com",
                        "customer": "cs_cr",
                        "client_reference_id": u.id,
                    }
                },
            }
            with patch("stripe.Webhook.construct_event", return_value=event):
                resp = client.post("/stripe/webhook", json={}, headers={"stripe-signature": "sig"})
            assert resp.status_code == 200
        finally:
            main_module.redis_client = None

        from mvp.backend.models import StripeCustomer

        sc = db_session.query(StripeCustomer).filter(StripeCustomer.user_id == u.id).first()
        assert sc is not None
        assert sc.stripe_customer_id == "cs_cr"
        db_session.refresh(lic)
        assert lic.is_active is True
