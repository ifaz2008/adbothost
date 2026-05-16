# Credits, Ads, Payments, and Coupons

AdBotHost keeps small Telegram bots online with credits. Credits are not a cash equivalent; they are wallet units that users manually redeem into prepaid runtime for a specific bot.

## Runtime Redemption

Credits stay in the user wallet until the user redeems them from the dashboard. Redeeming credits sets or extends the bot's `active_until` time.

Runtime formula:

```text
runtime_hours = credits_redeemed * 6 / credit_multiplier
```

Plan examples for 24 hours of runtime:

| Plan | Credit multiplier | Credits for 24 hours |
| --- | ---: | ---: |
| 1x Basic | 1 | 4 |
| 2x Plus | 2 | 8 |
| 4x Boost | 4 | 16 |
| 8x Max | 8 | 32 |

The scheduler stops running bots after `active_until` expires. It restarts crashed bots only while redeemed runtime is still active.

## Rewarded Ads

The MVP includes a fake rewarded-ad callback at `POST /ad-rewards/callback`. The callback is idempotent by `reward_id`, so the same reward cannot be credited twice.

Production deployments must replace this with a real rewarded-ad provider signature check before granting credits.

## Manual Payments

Users can submit manual payment requests from the dashboard. The default configuration is for Binance Pay/manual Binance payment:

- `MANUAL_PAYMENT_ENABLED`
- `MANUAL_PAYMENT_PROVIDER_NAME`
- `MANUAL_PAYMENT_RECEIVER_ID`
- `MANUAL_PAYMENT_INSTRUCTIONS`
- `MANUAL_PAYMENT_CURRENCY`

Pending payment requests do not add credits. Only an admin approval adds credits and creates a `credit_transactions` row. Rejected requests do not add credits. A `transaction_id` cannot be approved twice.

## Coupons

Admins can create coupon codes with fixed credit amounts and optional percent bonuses. Coupon codes are stored uppercase and redeemed case-insensitively.

Coupon redemption enforces:

- active or inactive state
- start and expiry dates
- max total uses
- max uses per user

A successful redemption creates a `credit_transactions` row.

## Admin Credit Adjustments

Admins can add or deduct credits from any user. Every adjustment is stored in `credit_transactions` with a private internal reason and optional user-visible reason.

By default, balances cannot go below zero. Set `ALLOW_NEGATIVE_CREDITS=true` only if you intentionally want negative balances.

Admins may deduct credits for abuse, refunds, corrections, policy penalties, or fraud response. Transaction history should never be deleted.
