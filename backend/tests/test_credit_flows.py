import os
from datetime import timedelta
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///./test_credit_flows.db"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "secret"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ALLOW_NEGATIVE_CREDITS"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Bot, BotVersion, Deployment, User, WorkerNode  # noqa: E402
from app.scheduler.jobs import stop_expired_bots  # noqa: E402
from app.core.security import utcnow  # noqa: E402
from app.services.plans import ensure_default_plans, get_free_plan  # noqa: E402


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_plans(db)
    finally:
        db.close()


def auth_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/dev-login", json={"email": email})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def credit_balance(client: TestClient, headers: dict[str, str]) -> float:
    response = client.get("/credits/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["balance"]


def test_coupon_redemption_creates_credit_transaction() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client, "coupon-user@example.test")

        created = client.post(
            "/admin/coupons",
            headers=admin,
            json={"code": "launch5", "credit_amount": 5, "max_uses_total": 10, "max_uses_per_user": 1},
        )
        assert created.status_code == 200, created.text

        redeemed = client.post("/coupons/redeem", headers=user, json={"code": "LaUnCh5"})
        assert redeemed.status_code == 200, redeemed.text
        assert redeemed.json()["credits_added"] == 5
        assert credit_balance(client, user) == 5

        transactions = client.get("/credits/transactions", headers=user)
        assert transactions.status_code == 200, transactions.text
        assert transactions.json()[0]["reason"] == "coupon_redemption"


def test_duplicate_coupon_use_limit_is_blocked() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client, "coupon-limit@example.test")

        response = client.post(
            "/admin/coupons",
            headers=admin,
            json={"code": "ONCE", "credit_amount": 2, "max_uses_total": 10, "max_uses_per_user": 1},
        )
        assert response.status_code == 200, response.text

        assert client.post("/coupons/redeem", headers=user, json={"code": "once"}).status_code == 200
        duplicate = client.post("/coupons/redeem", headers=user, json={"code": "once"})
        assert duplicate.status_code == 400
        assert "maximum number of times" in duplicate.json()["detail"]


def test_manual_payment_approve_adds_credits_once() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client, "pay-user@example.test")

        request = client.post(
            "/payment-requests",
            headers=user,
            json={
                "payment_method": "binance_manual",
                "payer_binance_id": "payer-1",
                "transaction_id": " tx-pay-1 ",
                "amount_paid": "10",
                "currency": "USDT",
                "requested_credits": 10,
            },
        )
        assert request.status_code == 200, request.text
        assert credit_balance(client, user) == 0

        approved = client.post(f"/admin/payment-requests/{request.json()['id']}/approve", headers=admin, json={"admin_note": "ok"})
        assert approved.status_code == 200, approved.text
        assert credit_balance(client, user) == 10

        approved_again = client.post(f"/admin/payment-requests/{request.json()['id']}/approve", headers=admin, json={})
        assert approved_again.status_code == 200, approved_again.text
        assert credit_balance(client, user) == 10


def test_duplicate_approved_transaction_id_is_blocked() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client, "duplicate-payment@example.test")

        payload = {
            "payment_method": "binance_manual",
            "payer_binance_id": "payer-2",
            "transaction_id": "same-tx",
            "amount_paid": "4",
            "currency": "USDT",
            "requested_credits": 4,
        }
        first = client.post("/payment-requests", headers=user, json=payload)
        second = client.post("/payment-requests", headers=user, json={**payload, "payer_binance_id": "payer-3"})
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text

        assert client.post(f"/admin/payment-requests/{first.json()['id']}/approve", headers=admin, json={}).status_code == 200
        duplicate = client.post(f"/admin/payment-requests/{second.json()['id']}/approve", headers=admin, json={})
        assert duplicate.status_code == 409


def test_admin_credit_deduction_cannot_go_below_zero_by_default() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user_response = client.post("/auth/dev-login", json={"email": "deduct-user@example.test"})
        assert user_response.status_code == 200, user_response.text
        user_id = user_response.json()["user"]["id"]

        response = client.post(
            f"/admin/users/{user_id}/credit-adjustment",
            headers=admin,
            json={
                "amount": -1,
                "reference_type": "abuse_penalty",
                "internal_reason": "test deduction",
                "visible_reason": "Policy adjustment",
            },
        )
        assert response.status_code == 400
        assert "cannot go below 0" in response.json()["detail"]


def test_redeem_credits_for_bot_runtime_deducts_wallet_and_sets_expiry() -> None:
    reset_db()
    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client, "runtime-user@example.test")
        user_id = client.get("/users/me", headers=user).json()["id"]

        adjustment = client.post(
            f"/admin/users/{user_id}/credit-adjustment",
            headers=admin,
            json={
                "amount": 6,
                "reference_type": "bonus",
                "internal_reason": "test runtime wallet top-up",
                "visible_reason": "Runtime test",
            },
        )
        assert adjustment.status_code == 200, adjustment.text

        bot = client.post("/bots", headers=user, json={"name": "runtime bot", "start_command": "python bot.py"})
        assert bot.status_code == 200, bot.text

        redeemed = client.post(f"/bots/{bot.json()['id']}/redeem-credits", headers=user, json={"credits": 4})
        assert redeemed.status_code == 200, redeemed.text
        body = redeemed.json()
        assert body["credits_redeemed"] == 4
        assert body["runtime_hours_added"] == 24
        assert body["active_until"]
        assert credit_balance(client, user) == 2

        transactions = client.get("/credits/transactions", headers=user)
        assert transactions.status_code == 200, transactions.text
        assert transactions.json()[0]["reason"] == "runtime_redemption"
        assert transactions.json()[0]["amount"] == -4


def test_redeem_credits_cannot_overdraw_wallet() -> None:
    reset_db()
    with TestClient(app) as client:
        user = auth_headers(client, "runtime-overdraw@example.test")
        bot = client.post("/bots", headers=user, json={"name": "empty wallet bot", "start_command": "python bot.py"})
        assert bot.status_code == 200, bot.text

        response = client.post(f"/bots/{bot.json()['id']}/redeem-credits", headers=user, json={"credits": 1})
        assert response.status_code == 400
        assert "cannot go below 0" in response.json()["detail"]


def test_scheduler_stops_bots_after_active_until_expires() -> None:
    reset_db()
    db = SessionLocal()
    try:
        plan = get_free_plan(db)
        user = User(email="expired-runtime@example.test", plan_id=plan.id)
        db.add(user)
        db.flush()
        bot = Bot(user_id=user.id, name="expired", start_command="python bot.py", status="running", active_until=utcnow() - timedelta(minutes=1))
        db.add(bot)
        db.flush()
        version = BotVersion(
            bot_id=bot.id,
            version_number=1,
            runtime="python",
            filename="bot.zip",
            storage_path="/tmp/bot.zip",
            sha256="0" * 64,
        )
        node = WorkerNode(name="local", base_url="http://worker:9000", token="token", status="healthy")
        db.add_all([version, node])
        db.flush()
        deployment = Deployment(
            bot_id=bot.id,
            bot_version_id=version.id,
            worker_node_id=node.id,
            status="running",
            cpu=plan.cpu,
            memory_mb=plan.memory_mb,
            storage_mb=plan.storage_mb,
        )
        db.add(deployment)
        db.commit()
        deployment_id = deployment.id
        bot_id = bot.id
    finally:
        db.close()

    stop_expired_bots()

    db = SessionLocal()
    try:
        deployment = db.get(Deployment, deployment_id)
        bot = db.get(Bot, bot_id)
        assert deployment.status == "stopped"
        assert bot.status == "stopped"
    finally:
        db.close()


def teardown_module() -> None:
    Path("test_credit_flows.db").unlink(missing_ok=True)
