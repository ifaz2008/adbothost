import {
  Bot,
  Coins,
  CreditCard,
  Gauge,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Percent,
  ScrollText,
  Settings,
  ShieldAlert,
  Ticket,
  Upload,
} from "lucide-react";

const nav = [
  ["home", LayoutDashboard, "Home"],
  ["bots", Bot, "My Bots"],
  ["create", Upload, "Create Bot"],
  ["upload", Upload, "Upload ZIP"],
  ["settings", Settings, "Settings"],
  ["env", KeyRound, "Env Vars"],
  ["logs", ScrollText, "Logs"],
  ["credits", Coins, "Credits"],
  ["buyCredits", CreditCard, "Buy Credits"],
  ["paymentRequests", CreditCard, "Payments"],
  ["redeemCoupon", Ticket, "Coupon"],
  ["creditHistory", ScrollText, "Credit History"],
  ["admin", ShieldAlert, "Admin"],
  ["adminPayments", CreditCard, "Admin Payments"],
  ["adminAdjustment", Coins, "Credit Adjust"],
  ["adminCoupons", Percent, "Admin Coupons"],
];

export function Shell({ view, setView, user, onLogout, children }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-white">
              <Gauge size={20} />
            </div>
            <div>
              <div className="text-lg font-semibold">AdBotHost</div>
              <div className="text-xs text-slate-500">Small Telegram bots only</div>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-600 sm:inline">{user?.display_name || user?.email || "User"}</span>
            <button
              className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-line bg-white text-slate-700 hover:bg-panel"
              onClick={onLogout}
              title="Log out"
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[220px_1fr]">
        <nav className="flex gap-2 overflow-x-auto rounded-md border border-line bg-white p-2 lg:block lg:overflow-visible">
          {nav.map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setView(id)}
              className={`focus-ring mb-0 inline-flex h-10 shrink-0 items-center gap-2 rounded-md px-3 text-sm lg:mb-1 lg:w-full ${
                view === id ? "bg-brand text-white" : "text-slate-700 hover:bg-panel"
              }`}
              title={label}
            >
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <main>{children}</main>
      </div>
    </div>
  );
}
