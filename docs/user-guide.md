# User Guide

## Add Credits

Open the dashboard and go to `Buy Credits`.

You can add credits in three MVP ways:

- Rewarded ads: claim a rewarded-ad credit through the fake callback flow.
- Manual payment: send payment using the displayed manual payment instructions, then submit your Binance ID, transaction ID, amount, currency, requested credits, and proof note or proof image path.
- Coupon: redeem a coupon code provided by an admin or campaign.

Manual payment requests stay pending until an admin reviews them. Pending requests do not add credits.

## Redeem Runtime

Wallet credits do not run bots automatically. Open `My Bots`, enter the number of credits to redeem beside a bot, and submit the runtime redemption before deploying or restarting.

Runtime is calculated as `credits_redeemed * 6 / credit_multiplier` hours:

- 1x Basic: 4 credits = 24 hours
- 2x Plus: 8 credits = 24 hours
- 4x Boost: 16 credits = 24 hours
- 8x Max: 32 credits = 24 hours

The bot list shows the bot's active expiry time. When that time passes, the scheduler stops the bot.

## Check Requests and History

Use `Payments` to see your manual payment requests and their status.

Use `Credit History` to see credit additions, deductions, runtime redemptions, coupons, manual payments, and admin adjustments.

## Bot Hosting Rules

AdBotHost is only for small Telegram bots. It is not a VPS and does not allow shell access, custom Dockerfiles, proxies, browser automation, crypto mining, phishing, spam, malware, or AI model hosting.
