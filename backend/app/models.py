from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.security import utcnow
from app.db.session import Base


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False, index=True)
    max_bots = Column(Integer, nullable=False)
    cpu = Column(Float, nullable=False)
    memory_mb = Column(Integer, nullable=False)
    storage_mb = Column(Integer, nullable=False)
    max_upload_size_mb = Column(Integer, nullable=False)
    runtime_per_credit_hours = Column(Integer, default=24, nullable=False)
    credit_multiplier = Column(Float, default=1.0, nullable=False)

    users = relationship("User", back_populates="plan")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    telegram_id = Column(String(64), unique=True, nullable=True, index=True)
    display_name = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)

    plan = relationship("Plan", back_populates="users")
    bots = relationship("Bot", back_populates="user")
    credit_account = relationship("CreditAccount", back_populates="user", uselist=False)


class CreditAccount(Base, TimestampMixin):
    __tablename__ = "credits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)

    user = relationship("User", back_populates="credit_account")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(String(120), nullable=False)
    reference = Column(String(160), nullable=True, index=True)
    reference_type = Column(String(80), nullable=True, index=True)
    visible_reason = Column(String(255), nullable=True)
    internal_reason = Column(Text, nullable=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    balance_after = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    admin = relationship("User", foreign_keys=[admin_id])


class AdReward(Base):
    __tablename__ = "ad_rewards"

    id = Column(Integer, primary_key=True)
    reward_id = Column(String(160), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credits_awarded = Column(Float, nullable=False)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User")


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_method = Column(String(80), nullable=False)
    payer_binance_id = Column(String(160), nullable=False)
    transaction_id = Column(String(180), nullable=False, index=True)
    amount_paid = Column(String(80), nullable=False)
    currency = Column(String(20), nullable=False)
    requested_credits = Column(Integer, nullable=False)
    proof_note = Column(Text, nullable=True)
    proof_image_url = Column(Text, nullable=True)
    status = Column(String(40), default="pending", nullable=False, index=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    reviewed_by_admin = relationship("User", foreign_keys=[reviewed_by_admin_id])


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True)
    code = Column(String(80), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    credit_amount = Column(Float, nullable=False)
    percent_bonus = Column(Float, nullable=True)
    max_uses_total = Column(Integer, nullable=True)
    max_uses_per_user = Column(Integer, default=1, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    created_by_admin = relationship("User")
    redemptions = relationship("CouponRedemption", back_populates="coupon")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id = Column(Integer, primary_key=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credits_added = Column(Float, nullable=False)
    redeemed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    coupon = relationship("Coupon", back_populates="redemptions")
    user = relationship("User")


class Bot(Base, TimestampMixin):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    start_command = Column(String(255), nullable=False)
    status = Column(String(40), default="created", nullable=False)
    active_until = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="bots")
    versions = relationship("BotVersion", back_populates="bot", order_by="BotVersion.version_number")
    deployments = relationship("Deployment", back_populates="bot")
    env_vars = relationship("BotEnvVar", back_populates="bot", cascade="all, delete-orphan")


class BotEnvVar(Base, TimestampMixin):
    __tablename__ = "bot_env_vars"
    __table_args__ = (UniqueConstraint("bot_id", "key", name="uq_bot_env_key"),)

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    key = Column(String(120), nullable=False)
    # TODO: encrypt values with a KMS-backed key before production.
    value = Column(Text, nullable=False)
    is_secret = Column(Boolean, default=True, nullable=False)

    bot = relationship("Bot", back_populates="env_vars")


class BotVersion(Base):
    __tablename__ = "bot_versions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    runtime = Column(String(20), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_path = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    scan_status = Column(String(40), default="clean", nullable=False)
    scan_severity = Column(String(20), default="low", nullable=False)
    scan_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    bot = relationship("Bot", back_populates="versions")
    deployments = relationship("Deployment", back_populates="version")


class WorkerNode(Base, TimestampMixin):
    __tablename__ = "worker_nodes"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    base_url = Column(String(255), nullable=False)
    token = Column(String(255), nullable=False)
    status = Column(String(40), default="unknown", nullable=False)
    cpu_percent = Column(Float, default=0.0, nullable=False)
    memory_total_mb = Column(Integer, default=0, nullable=False)
    memory_used_mb = Column(Integer, default=0, nullable=False)
    disk_total_mb = Column(Integer, default=0, nullable=False)
    disk_used_mb = Column(Integer, default=0, nullable=False)
    running_containers = Column(Integer, default=0, nullable=False)
    max_containers = Column(Integer, default=20, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    deployments = relationship("Deployment", back_populates="worker_node")


class Deployment(Base, TimestampMixin):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    bot_version_id = Column(Integer, ForeignKey("bot_versions.id"), nullable=False)
    worker_node_id = Column(Integer, ForeignKey("worker_nodes.id"), nullable=False)
    container_id = Column(String(255), nullable=True)
    container_name = Column(String(255), nullable=True)
    image_tag = Column(String(255), nullable=True)
    status = Column(String(40), default="pending", nullable=False)
    cpu = Column(Float, nullable=False)
    memory_mb = Column(Integer, nullable=False)
    storage_mb = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    last_credit_charge_at = Column(DateTime(timezone=True), nullable=True)
    restart_count = Column(Integer, default=0, nullable=False)

    bot = relationship("Bot", back_populates="deployments")
    version = relationship("BotVersion", back_populates="deployments")
    worker_node = relationship("WorkerNode", back_populates="deployments")


class BotLog(Base):
    __tablename__ = "bot_logs"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=True, index=True)
    level = Column(String(20), default="info", nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    bot = relationship("Bot")
    deployment = relationship("Deployment")


class AbuseFlag(Base):
    __tablename__ = "abuse_flags"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    bot_version_id = Column(Integer, ForeignKey("bot_versions.id"), nullable=True, index=True)
    severity = Column(String(20), nullable=False)
    status = Column(String(40), default="pending", nullable=False)
    reason = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    bot = relationship("Bot")
    version = relationship("BotVersion")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
