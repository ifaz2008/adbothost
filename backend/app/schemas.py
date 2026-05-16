from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    max_bots: int
    cpu: float
    memory_mb: int
    storage_mb: int
    max_upload_size_mb: int
    runtime_per_credit_hours: int
    credit_multiplier: float


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str]
    telegram_id: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    is_suspended: bool
    plan: Optional[PlanRead] = None


class AuthRequest(BaseModel):
    email: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TelegramLoginRequest(BaseModel):
    telegram_id: str
    display_name: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_command: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class BotUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    start_command: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None


class BotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    start_command: str
    status: str
    active_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class EnvVarUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(max_length=4096)
    is_secret: bool = True


class EnvVarRead(BaseModel):
    id: int
    key: str
    value: str = "********"
    is_secret: bool
    updated_at: datetime


class BotVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bot_id: int
    version_number: int
    runtime: str
    filename: str
    sha256: str
    scan_status: str
    scan_severity: str
    scan_summary: Optional[str]
    created_at: datetime


class DeployRequest(BaseModel):
    version_id: Optional[int] = None


class DeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bot_id: int
    bot_version_id: int
    worker_node_id: int
    container_id: Optional[str]
    container_name: Optional[str]
    image_tag: Optional[str]
    status: str
    cpu: float
    memory_mb: int
    storage_mb: int
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    restart_count: int


class CreditSummary(BaseModel):
    balance: float
    runtime_per_credit_hours: int
    credit_multiplier: float
    plan_name: Optional[str] = None


class RuntimeRedeemRequest(BaseModel):
    credits: float = Field(gt=0, le=100000)


class RuntimeRedeemResponse(BaseModel):
    bot_id: int
    credits_redeemed: float
    runtime_hours_added: float
    active_until: datetime
    balance: float


class CreditTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    amount: float
    reason: str
    reference: Optional[str]
    reference_type: Optional[str] = None
    visible_reason: Optional[str] = None
    balance_after: float
    created_at: datetime


class AdminCreditTransactionRead(CreditTransactionRead):
    internal_reason: Optional[str] = None
    admin_id: Optional[int] = None


class AdRewardCallback(BaseModel):
    reward_id: str = Field(min_length=1, max_length=160)
    user_id: Optional[int] = None
    email: Optional[str] = None
    telegram_id: Optional[str] = None
    credits: Optional[float] = None
    metadata: Dict[str, Any] = {}


class AdRewardResponse(BaseModel):
    credited: bool
    balance: float
    reward_id: str


class PaymentConfigRead(BaseModel):
    enabled: bool
    provider_name: str
    receiver_id: str
    instructions: str
    currency: str


class PaymentRequestCreate(BaseModel):
    payment_method: str = Field(default="binance_manual", min_length=1, max_length=80)
    payer_binance_id: str = Field(min_length=1, max_length=160)
    transaction_id: str = Field(min_length=1, max_length=180)
    amount_paid: str = Field(min_length=1, max_length=80)
    currency: str = Field(default="USDT", min_length=1, max_length=20)
    requested_credits: int = Field(gt=0, le=100000)
    proof_note: Optional[str] = Field(default=None, max_length=4000)
    proof_image_url: Optional[str] = Field(default=None, max_length=1000)


class PaymentRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    payment_method: str
    payer_binance_id: str
    transaction_id: str
    amount_paid: str
    currency: str
    requested_credits: int
    proof_note: Optional[str]
    proof_image_url: Optional[str]
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime]


class AdminPaymentRequestRead(PaymentRequestRead):
    admin_note: Optional[str]
    reviewed_by_admin_id: Optional[int]


class PaymentReviewRequest(BaseModel):
    admin_note: Optional[str] = Field(default=None, max_length=4000)


class CreditAdjustmentRequest(BaseModel):
    amount: float
    internal_reason: str = Field(min_length=1, max_length=4000)
    visible_reason: Optional[str] = Field(default=None, max_length=255)
    reference_type: str = Field(default="manual_adjustment", pattern="^(manual_adjustment|abuse_penalty|refund|bonus|correction)$")


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    description: Optional[str] = None
    credit_amount: float = Field(gt=0)
    percent_bonus: Optional[float] = Field(default=None, ge=0, le=1000)
    max_uses_total: Optional[int] = Field(default=None, gt=0)
    max_uses_per_user: int = Field(default=1, gt=0)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    active: bool = True


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    credit_amount: Optional[float] = Field(default=None, gt=0)
    percent_bonus: Optional[float] = Field(default=None, ge=0, le=1000)
    max_uses_total: Optional[int] = Field(default=None, gt=0)
    max_uses_per_user: Optional[int] = Field(default=None, gt=0)
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    active: Optional[bool] = None


class CouponRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: Optional[str]
    credit_amount: float
    percent_bonus: Optional[float]
    max_uses_total: Optional[int]
    max_uses_per_user: int
    starts_at: Optional[datetime]
    expires_at: Optional[datetime]
    active: bool
    created_by_admin_id: int
    created_at: datetime


class CouponRedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=80)


class CouponRedemptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coupon_id: int
    user_id: int
    credits_added: float
    redeemed_at: datetime


class CouponRedeemResponse(BaseModel):
    redeemed: bool
    credits_added: float
    balance: float
    code: str


class WorkerNodeCreate(BaseModel):
    name: str
    base_url: str
    token: str
    max_containers: int = 20


class WorkerNodeHeartbeat(BaseModel):
    status: str = "healthy"
    cpu_percent: float
    memory_total_mb: int
    memory_used_mb: int
    disk_total_mb: int
    disk_used_mb: int
    running_containers: int
    max_containers: Optional[int] = None


class WorkerNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    status: str
    cpu_percent: float
    memory_total_mb: int
    memory_used_mb: int
    disk_total_mb: int
    disk_used_mb: int
    running_containers: int
    max_containers: int
    is_active: bool
    last_heartbeat_at: Optional[datetime]


class BotLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bot_id: int
    deployment_id: Optional[int]
    level: str
    message: str
    created_at: datetime


class AbuseFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    bot_id: int
    bot_version_id: Optional[int]
    severity: str
    status: str
    reason: str
    details: Optional[str]
    created_at: datetime
