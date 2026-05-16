import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Bot, CheckCircle2, Coins, CreditCard, Play, RefreshCw, Save, Square, Ticket, Upload } from "lucide-react";

import { API_BASE, apiFetch, getToken, setToken } from "./lib/api";
import { Badge, Button, Input, Panel, Textarea } from "./components/Panel";
import { Shell } from "./components/Shell";
import "./styles/index.css";

function statusTone(status) {
  if (["running", "healthy", "clean", "approved"].includes(status)) return "good";
  if (["pending", "review", "flagged", "unknown"].includes(status)) return "warn";
  if (["failed", "blocked", "unhealthy", "rejected", "suspended"].includes(status)) return "bad";
  return "neutral";
}

function Login({ onLogin }) {
  const [mode, setMode] = useState("admin");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("user@example.com");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const data =
        mode === "admin"
          ? await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) })
          : await apiFetch("/auth/dev-login", { method: "POST", body: JSON.stringify({ email }) });
      setToken(data.access_token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-md border border-line bg-white p-5">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-brand text-white">
            <Bot size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold">AdBotHost</h1>
            <p className="text-sm text-slate-500">Small Telegram bot hosting console</p>
          </div>
        </div>
        <div className="mb-4 grid grid-cols-2 rounded-md border border-line p-1">
          <button type="button" className={`h-9 rounded ${mode === "admin" ? "bg-brand text-white" : ""}`} onClick={() => setMode("admin")}>
            Admin
          </button>
          <button type="button" className={`h-9 rounded ${mode === "dev" ? "bg-brand text-white" : ""}`} onClick={() => setMode("dev")}>
            Dev user
          </button>
        </div>
        {mode === "admin" ? (
          <div className="space-y-3">
            <Input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Admin username" />
            <Input value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Admin password" />
          </div>
        ) : (
          <Input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="Email" />
        )}
        {error ? <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        <Button tone="primary" className="mt-4 w-full" type="submit">
          <CheckCircle2 size={17} /> Sign in
        </Button>
        <p className="mt-4 text-xs leading-5 text-slate-500">
          This MVP is positioned only for small Telegram bots. Prohibited workloads are blocked before deployment.
        </p>
      </form>
    </div>
  );
}

function Home({ bots, credits }) {
  const running = bots.filter((bot) => bot.status === "running").length;
  return (
    <Panel title="Dashboard">
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Bots" value={bots.length} />
        <Metric label="Running" value={running} />
        <Metric label="Credits" value={credits?.balance?.toFixed?.(4) ?? "0"} />
      </div>
      <div className="mt-4 rounded-md border border-line bg-panel p-4 text-sm leading-6 text-slate-700">
        Upload Python or Node.js Telegram bot ZIP files, save environment variables, deploy to a locked-down worker container, and redeem wallet credits into prepaid bot runtime.
      </div>
    </Panel>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-md border border-line bg-panel p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function formatDateTime(value) {
  if (!value) return "Not active";
  return new Date(value).toLocaleString();
}

function BotsView({ bots, selectedBotId, setSelectedBotId, refresh }) {
  const [redeemAmounts, setRedeemAmounts] = useState({});

  async function action(bot, path) {
    await apiFetch(`/bots/${bot.id}/${path}`, {
      method: "POST",
      body: path === "deploy" ? JSON.stringify({}) : undefined,
    });
    await refresh();
  }

  async function redeem(event, bot) {
    event.preventDefault();
    const credits = Number(redeemAmounts[bot.id] || 1);
    await apiFetch(`/bots/${bot.id}/redeem-credits`, {
      method: "POST",
      body: JSON.stringify({ credits }),
    });
    setRedeemAmounts({ ...redeemAmounts, [bot.id]: "" });
    await refresh();
  }

  return (
    <Panel title="My Bots">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="text-slate-500">
            <tr>
              <th className="border-b border-line py-2">Name</th>
              <th className="border-b border-line py-2">Status</th>
              <th className="border-b border-line py-2">Active until</th>
              <th className="border-b border-line py-2">Start command</th>
              <th className="border-b border-line py-2">Redeem runtime</th>
              <th className="border-b border-line py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {bots.map((bot) => (
              <tr key={bot.id}>
                <td className="border-b border-line py-2">
                  <button className="font-medium text-brand" onClick={() => setSelectedBotId(bot.id)}>
                    {bot.name}
                  </button>
                </td>
                <td className="border-b border-line py-2">
                  <Badge tone={statusTone(bot.status)}>{bot.status}</Badge>
                </td>
                <td className="border-b border-line py-2 text-xs">{formatDateTime(bot.active_until)}</td>
                <td className="border-b border-line py-2 font-mono text-xs">{bot.start_command}</td>
                <td className="border-b border-line py-2">
                  <form onSubmit={(event) => redeem(event, bot)} className="flex max-w-52 gap-2">
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={redeemAmounts[bot.id] ?? ""}
                      onChange={(event) => setRedeemAmounts({ ...redeemAmounts, [bot.id]: event.target.value })}
                      placeholder="Credits"
                      required
                    />
                    <Button type="submit">Redeem</Button>
                  </form>
                </td>
                <td className="border-b border-line py-2">
                  <div className="flex gap-2">
                    <Button type="button" onClick={() => action(bot, "deploy")} title="Deploy">
                      <Play size={16} />
                    </Button>
                    <Button type="button" onClick={() => action(bot, "restart")} title="Restart">
                      <RefreshCw size={16} />
                    </Button>
                    <Button type="button" onClick={() => action(bot, "stop")} title="Stop">
                      <Square size={16} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!bots.length ? <p className="text-sm text-slate-500">No bots yet.</p> : null}
    </Panel>
  );
}

function CreateBot({ onCreated }) {
  const [name, setName] = useState("");
  const [startCommand, setStartCommand] = useState("python bot.py");
  const [description, setDescription] = useState("");

  async function submit(event) {
    event.preventDefault();
    const bot = await apiFetch("/bots", {
      method: "POST",
      body: JSON.stringify({ name, start_command: startCommand, description }),
    });
    setName("");
    setDescription("");
    onCreated(bot);
  }

  return (
    <Panel title="Create Bot">
      <form onSubmit={submit} className="grid max-w-2xl gap-3">
        <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Bot name" required />
        <Input value={startCommand} onChange={(event) => setStartCommand(event.target.value)} placeholder="python bot.py or npm start" required />
        <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
        <Button tone="primary" type="submit">
          <Save size={17} /> Create
        </Button>
      </form>
    </Panel>
  );
}

function SettingsView({ bot, refresh }) {
  const [name, setName] = useState(bot?.name || "");
  const [startCommand, setStartCommand] = useState(bot?.start_command || "");
  const [description, setDescription] = useState(bot?.description || "");

  useEffect(() => {
    setName(bot?.name || "");
    setStartCommand(bot?.start_command || "");
    setDescription(bot?.description || "");
  }, [bot?.id]);

  if (!bot) return <Panel title="Bot Settings"><p className="text-sm text-slate-500">Select a bot first.</p></Panel>;

  async function save(event) {
    event.preventDefault();
    await apiFetch(`/bots/${bot.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name, start_command: startCommand, description }),
    });
    await refresh();
  }

  return (
    <Panel title="Bot Settings">
      <form onSubmit={save} className="grid max-w-2xl gap-3">
        <Input value={name} onChange={(event) => setName(event.target.value)} />
        <Input value={startCommand} onChange={(event) => setStartCommand(event.target.value)} />
        <Textarea value={description || ""} onChange={(event) => setDescription(event.target.value)} />
        <Button tone="primary" type="submit">
          <Save size={17} /> Save
        </Button>
      </form>
    </Panel>
  );
}

function UploadView({ bot, refresh }) {
  const [file, setFile] = useState(null);
  const [versions, setVersions] = useState([]);

  useEffect(() => {
    if (bot) apiFetch(`/bots/${bot.id}/versions`).then(setVersions).catch(() => setVersions([]));
  }, [bot?.id]);

  if (!bot) return <Panel title="Upload ZIP"><p className="text-sm text-slate-500">Select or create a bot first.</p></Panel>;

  async function submit(event) {
    event.preventDefault();
    const body = new FormData();
    body.append("file", file);
    await apiFetch(`/bots/${bot.id}/upload`, { method: "POST", body });
    setFile(null);
    const nextVersions = await apiFetch(`/bots/${bot.id}/versions`);
    setVersions(nextVersions);
    await refresh();
  }

  return (
    <Panel title="Upload ZIP">
      <form onSubmit={submit} className="mb-4 flex flex-wrap items-center gap-3">
        <Input type="file" accept=".zip" onChange={(event) => setFile(event.target.files[0])} required />
        <Button tone="primary" type="submit">
          <Upload size={17} /> Upload
        </Button>
      </form>
      <div className="space-y-2">
        {versions.map((version) => (
          <div key={version.id} className="flex items-center justify-between rounded-md border border-line px-3 py-2 text-sm">
            <span>v{version.version_number} - {version.runtime} - {version.filename}</span>
            <Badge tone={statusTone(version.scan_status)}>{version.scan_status}</Badge>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function EnvView({ bot }) {
  const [items, setItems] = useState([]);
  const [key, setKey] = useState("TELEGRAM_BOT_TOKEN");
  const [value, setValue] = useState("");

  async function load() {
    if (bot) setItems(await apiFetch(`/bots/${bot.id}/env`));
  }
  useEffect(() => { load().catch(() => setItems([])); }, [bot?.id]);
  if (!bot) return <Panel title="Env Variables"><p className="text-sm text-slate-500">Select a bot first.</p></Panel>;

  async function save(event) {
    event.preventDefault();
    await apiFetch(`/bots/${bot.id}/env`, { method: "POST", body: JSON.stringify({ key, value, is_secret: true }) });
    setValue("");
    await load();
  }

  return (
    <Panel title="Env Variables">
      <form onSubmit={save} className="mb-4 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <Input value={key} onChange={(event) => setKey(event.target.value)} placeholder="KEY" />
        <Input value={value} onChange={(event) => setValue(event.target.value)} type="password" placeholder="Value" />
        <Button tone="primary" type="submit"><Save size={17} /> Save</Button>
      </form>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.id} className="flex justify-between rounded-md border border-line px-3 py-2 text-sm">
            <span className="font-mono">{item.key}</span>
            <span>{item.value}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function LogsView({ bot }) {
  const [logs, setLogs] = useState([]);
  async function load() {
    if (bot) setLogs(await apiFetch(`/logs/bots/${bot.id}?include_worker=true`));
  }
  useEffect(() => { load().catch(() => setLogs([])); }, [bot?.id]);
  return (
    <Panel title="Logs" actions={bot ? <Button onClick={load}><RefreshCw size={16} /> Refresh</Button> : null}>
      {!bot ? <p className="text-sm text-slate-500">Select a bot first.</p> : null}
      <pre className="max-h-[520px] overflow-auto rounded-md bg-ink p-4 text-xs leading-5 text-slate-100">
        {logs.map((log) => `[${log.created_at}] ${log.level}: ${log.message}`).join("\n") || "No logs."}
      </pre>
    </Panel>
  );
}

function CreditsView({ credits, transactions, reward, setReward, addReward }) {
  return (
    <Panel title="Credits">
      <div className="mb-4 rounded-md border border-line bg-panel p-4">
        <div className="text-sm text-slate-500">Balance</div>
        <div className="text-2xl font-semibold">{credits?.balance?.toFixed?.(4) ?? "0"}</div>
        <div className="mt-1 text-xs text-slate-500">
          {credits?.plan_name || "Plan"} runtime multiplier: {credits?.credit_multiplier || 1}x. Redeem credits from My Bots.
        </div>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Input value={reward} onChange={(event) => setReward(event.target.value)} placeholder="Reward id" />
        <Button onClick={addReward}><Coins size={17} /> Fake ad reward</Button>
      </div>
      <div className="space-y-2">
        {transactions.map((tx) => (
          <div key={tx.id} className="flex justify-between rounded-md border border-line px-3 py-2 text-sm">
            <span>{tx.visible_reason || tx.reason} - {tx.reference || "manual"}</span>
            <span>{tx.amount}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function BuyCreditsView({ credits, reward, setReward, addReward, setView }) {
  const [config, setConfig] = useState(null);

  useEffect(() => {
    apiFetch("/payment-requests/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  return (
    <Panel title="Buy Credits">
      <div className="mb-4 rounded-md border border-line bg-panel p-4">
        <div className="text-sm text-slate-500">Current balance</div>
        <div className="text-2xl font-semibold">{credits?.balance?.toFixed?.(4) ?? "0"}</div>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-md border border-line p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Coins size={17} /> Rewarded ads</div>
          <div className="mb-3 flex gap-2">
            <Input value={reward} onChange={(event) => setReward(event.target.value)} placeholder="Reward id" />
            <Button onClick={addReward}>Claim</Button>
          </div>
        </div>
        <div className="rounded-md border border-line p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold"><CreditCard size={17} /> {config?.provider_name || "Manual payment"}</div>
          <p className="mb-2 text-sm text-slate-600">{config?.instructions || "Submit a payment proof for admin review."}</p>
          <p className="mb-3 text-xs text-slate-500">Receiver: {config?.receiver_id || "Ask admin"} - Currency: {config?.currency || "USDT"}</p>
          <Button onClick={() => setView("paymentRequests")}>Submit payment</Button>
        </div>
        <div className="rounded-md border border-line p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Ticket size={17} /> Coupon</div>
          <p className="mb-3 text-sm text-slate-600">Redeem a one-time or campaign coupon code.</p>
          <Button onClick={() => setView("redeemCoupon")}>Redeem coupon</Button>
        </div>
      </div>
    </Panel>
  );
}

function PaymentRequestsView({ refresh }) {
  const empty = {
    payment_method: "binance_manual",
    payer_binance_id: "",
    transaction_id: "",
    amount_paid: "",
    currency: "USDT",
    requested_credits: 1,
    proof_note: "",
    proof_image_url: "",
  };
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState(empty);

  async function load() {
    setRequests(await apiFetch("/payment-requests/my"));
  }

  useEffect(() => { load().catch(() => setRequests([])); }, []);

  async function submit(event) {
    event.preventDefault();
    await apiFetch("/payment-requests", { method: "POST", body: JSON.stringify(form) });
    setForm(empty);
    await load();
    await refresh();
  }

  return (
    <Panel title="Submit Manual Payment">
      <form onSubmit={submit} className="mb-5 grid gap-3 md:grid-cols-2">
        <Input value={form.payer_binance_id} onChange={(e) => setForm({ ...form, payer_binance_id: e.target.value })} placeholder="Payer Binance ID" required />
        <Input value={form.transaction_id} onChange={(e) => setForm({ ...form, transaction_id: e.target.value })} placeholder="Transaction ID" required />
        <Input value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} placeholder="Amount paid" required />
        <Input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} placeholder="Currency" required />
        <Input type="number" min="1" value={form.requested_credits} onChange={(e) => setForm({ ...form, requested_credits: Number(e.target.value) })} placeholder="Requested credits" required />
        <Input value={form.proof_image_url} onChange={(e) => setForm({ ...form, proof_image_url: e.target.value })} placeholder="Proof image URL/path" />
        <Textarea value={form.proof_note} onChange={(e) => setForm({ ...form, proof_note: e.target.value })} placeholder="Proof note" />
        <Button tone="primary" type="submit"><Save size={17} /> Submit</Button>
      </form>
      <PaymentRequestList rows={requests} />
    </Panel>
  );
}

function PaymentRequestList({ rows, admin = false, onAction }) {
  return (
    <div className="overflow-x-auto rounded-md border border-line">
      <table className="w-full min-w-[760px] text-left text-xs">
        <thead className="bg-panel text-slate-500">
          <tr>
            {["id", "user", "txid", "amount", "credits", "status", "created"].map((col) => <th key={col} className="px-3 py-2">{col}</th>)}
            {admin ? <th className="px-3 py-2">actions</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="border-t border-line px-3 py-2">{row.id}</td>
              <td className="border-t border-line px-3 py-2">{row.user_id}</td>
              <td className="border-t border-line px-3 py-2">{row.transaction_id}</td>
              <td className="border-t border-line px-3 py-2">{row.amount_paid} {row.currency}</td>
              <td className="border-t border-line px-3 py-2">{row.requested_credits}</td>
              <td className="border-t border-line px-3 py-2"><Badge tone={statusTone(row.status)}>{row.status}</Badge></td>
              <td className="border-t border-line px-3 py-2">{new Date(row.created_at).toLocaleString()}</td>
              {admin ? (
                <td className="border-t border-line px-3 py-2">
                  <div className="flex gap-2">
                    <Button onClick={() => onAction(row.id, "approve")}>Approve</Button>
                    <Button onClick={() => onAction(row.id, "needs-more-info")}>Info</Button>
                    <Button tone="danger" onClick={() => onAction(row.id, "reject")}>Reject</Button>
                  </div>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RedeemCouponView({ refresh }) {
  const [code, setCode] = useState("");
  const [redemptions, setRedemptions] = useState([]);
  const [message, setMessage] = useState("");

  async function load() {
    setRedemptions(await apiFetch("/coupons/my-redemptions"));
  }

  useEffect(() => { load().catch(() => setRedemptions([])); }, []);

  async function submit(event) {
    event.preventDefault();
    const result = await apiFetch("/coupons/redeem", { method: "POST", body: JSON.stringify({ code }) });
    setMessage(`Redeemed ${result.code}: +${result.credits_added} credits`);
    setCode("");
    await load();
    await refresh();
  }

  return (
    <Panel title="Redeem Coupon">
      <form onSubmit={submit} className="mb-4 flex flex-wrap gap-2">
        <Input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Coupon code" required />
        <Button tone="primary" type="submit"><Ticket size={17} /> Redeem</Button>
      </form>
      {message ? <p className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p> : null}
      <div className="space-y-2">
        {redemptions.map((item) => (
          <div key={item.id} className="flex justify-between rounded-md border border-line px-3 py-2 text-sm">
            <span>Coupon #{item.coupon_id}</span>
            <span>+{item.credits_added}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function CreditHistoryView({ transactions }) {
  return (
    <Panel title="Credit History">
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[680px] text-left text-xs">
          <thead className="bg-panel text-slate-500">
            <tr>{["date", "amount", "reason", "reference", "balance"].map((col) => <th key={col} className="px-3 py-2">{col}</th>)}</tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr key={tx.id}>
                <td className="border-t border-line px-3 py-2">{new Date(tx.created_at).toLocaleString()}</td>
                <td className="border-t border-line px-3 py-2">{tx.amount}</td>
                <td className="border-t border-line px-3 py-2">{tx.visible_reason || tx.reason}</td>
                <td className="border-t border-line px-3 py-2">{tx.reference || ""}</td>
                <td className="border-t border-line px-3 py-2">{tx.balance_after}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function AdminView({ user }) {
  const [data, setData] = useState({ users: [], bots: [], deployments: [], flags: [], nodes: [], credits: [] });
  async function load() {
    if (!user?.is_admin) return;
    const [users, bots, deployments, flags, nodes, credits] = await Promise.all([
      apiFetch("/admin/users"),
      apiFetch("/admin/bots"),
      apiFetch("/admin/deployments"),
      apiFetch("/admin/abuse-flags"),
      apiFetch("/admin/node-health"),
      apiFetch("/admin/credit-transactions"),
    ]);
    setData({ users, bots, deployments, flags, nodes, credits });
  }
  useEffect(() => { load().catch(() => {}); }, [user?.is_admin]);
  if (!user?.is_admin) return <Panel title="Admin Panel"><p className="text-sm text-slate-500">Admin access required.</p></Panel>;
  return (
    <Panel title="Admin Panel" actions={<Button onClick={load}><RefreshCw size={16} /> Refresh</Button>}>
      <AdminList title="Nodes" rows={data.nodes} cols={["name", "status", "cpu_percent", "running_containers"]} />
      <AdminList title="Abuse Flags" rows={data.flags} cols={["id", "severity", "status", "reason"]} />
      <AdminList title="Users" rows={data.users} cols={["id", "email", "telegram_id", "is_suspended"]} />
      <AdminList title="Deployments" rows={data.deployments} cols={["id", "bot_id", "status", "worker_node_id"]} />
      <AdminList title="Credit Transactions" rows={data.credits} cols={["id", "user_id", "amount", "reason"]} />
    </Panel>
  );
}

function AdminList({ title, rows, cols }) {
  return (
    <div className="mb-5">
      <h2 className="mb-2 text-sm font-semibold">{title}</h2>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[560px] text-left text-xs">
          <thead className="bg-panel text-slate-500">
            <tr>{cols.map((col) => <th key={col} className="px-3 py-2">{col}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0, 8).map((row, index) => (
              <tr key={row.id || index}>{cols.map((col) => <td key={col} className="border-t border-line px-3 py-2">{String(row[col] ?? "")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AdminPaymentRequestsView({ user, refresh }) {
  const [rows, setRows] = useState([]);
  const [adminNote, setAdminNote] = useState("");

  async function load() {
    if (user?.is_admin) setRows(await apiFetch("/admin/payment-requests"));
  }

  useEffect(() => { load().catch(() => setRows([])); }, [user?.is_admin]);

  async function action(id, statusAction) {
    await apiFetch(`/admin/payment-requests/${id}/${statusAction}`, {
      method: "POST",
      body: JSON.stringify({ admin_note: adminNote }),
    });
    setAdminNote("");
    await load();
    await refresh();
  }

  if (!user?.is_admin) return <Panel title="Admin Payment Requests"><p className="text-sm text-slate-500">Admin access required.</p></Panel>;
  return (
    <Panel title="Admin Payment Requests" actions={<Button onClick={load}><RefreshCw size={16} /> Refresh</Button>}>
      <div className="mb-3">
        <Textarea value={adminNote} onChange={(event) => setAdminNote(event.target.value)} placeholder="Admin note" />
      </div>
      <PaymentRequestList rows={rows} admin onAction={action} />
    </Panel>
  );
}

function AdminCreditAdjustmentView({ user, refresh }) {
  const [form, setForm] = useState({
    user_id: "",
    amount: "",
    reference_type: "manual_adjustment",
    visible_reason: "",
    internal_reason: "",
  });

  async function submit(event) {
    event.preventDefault();
    await apiFetch(`/admin/users/${form.user_id}/credit-adjustment`, {
      method: "POST",
      body: JSON.stringify({
        amount: Number(form.amount),
        reference_type: form.reference_type,
        visible_reason: form.visible_reason,
        internal_reason: form.internal_reason,
      }),
    });
    setForm({ ...form, amount: "", visible_reason: "", internal_reason: "" });
    await refresh();
  }

  if (!user?.is_admin) return <Panel title="Admin Credit Adjustment"><p className="text-sm text-slate-500">Admin access required.</p></Panel>;
  return (
    <Panel title="Admin Credit Adjustment">
      <form onSubmit={submit} className="grid max-w-2xl gap-3">
        <Input value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })} placeholder="User ID" required />
        <Input type="number" step="0.000001" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="Amount, negative to deduct" required />
        <select className="focus-ring h-10 rounded-md border border-line px-3 text-sm" value={form.reference_type} onChange={(e) => setForm({ ...form, reference_type: e.target.value })}>
          {["manual_adjustment", "abuse_penalty", "refund", "bonus", "correction"].map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
        <Input value={form.visible_reason} onChange={(e) => setForm({ ...form, visible_reason: e.target.value })} placeholder="Visible reason" />
        <Textarea value={form.internal_reason} onChange={(e) => setForm({ ...form, internal_reason: e.target.value })} placeholder="Internal reason" required />
        <Button tone="primary" type="submit"><Save size={17} /> Apply adjustment</Button>
      </form>
    </Panel>
  );
}

function AdminCouponsView({ user }) {
  const empty = {
    code: "",
    description: "",
    credit_amount: 1,
    percent_bonus: "",
    max_uses_total: "",
    max_uses_per_user: 1,
    expires_at: "",
    active: true,
  };
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(empty);

  async function load() {
    if (user?.is_admin) setRows(await apiFetch("/admin/coupons"));
  }

  useEffect(() => { load().catch(() => setRows([])); }, [user?.is_admin]);

  async function submit(event) {
    event.preventDefault();
    await apiFetch("/admin/coupons", {
      method: "POST",
      body: JSON.stringify({
        code: form.code,
        description: form.description,
        credit_amount: Number(form.credit_amount),
        percent_bonus: form.percent_bonus === "" ? null : Number(form.percent_bonus),
        max_uses_total: form.max_uses_total === "" ? null : Number(form.max_uses_total),
        max_uses_per_user: Number(form.max_uses_per_user),
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
        active: form.active,
      }),
    });
    setForm(empty);
    await load();
  }

  async function disable(id) {
    await apiFetch(`/admin/coupons/${id}/disable`, { method: "POST", body: JSON.stringify({}) });
    await load();
  }

  if (!user?.is_admin) return <Panel title="Admin Coupons"><p className="text-sm text-slate-500">Admin access required.</p></Panel>;
  return (
    <Panel title="Admin Coupons" actions={<Button onClick={load}><RefreshCw size={16} /> Refresh</Button>}>
      <form onSubmit={submit} className="mb-5 grid gap-3 md:grid-cols-2">
        <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} placeholder="Code" required />
        <Input type="number" min="0.000001" step="0.000001" value={form.credit_amount} onChange={(e) => setForm({ ...form, credit_amount: e.target.value })} placeholder="Credit amount" required />
        <Input type="number" min="0" step="0.01" value={form.percent_bonus} onChange={(e) => setForm({ ...form, percent_bonus: e.target.value })} placeholder="Percent bonus optional" />
        <Input type="number" min="1" value={form.max_uses_total} onChange={(e) => setForm({ ...form, max_uses_total: e.target.value })} placeholder="Max uses total" />
        <Input type="number" min="1" value={form.max_uses_per_user} onChange={(e) => setForm({ ...form, max_uses_per_user: e.target.value })} placeholder="Max uses per user" />
        <Input type="datetime-local" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} />
        <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" />
        <Button tone="primary" type="submit"><Save size={17} /> Create coupon</Button>
      </form>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[760px] text-left text-xs">
          <thead className="bg-panel text-slate-500">
            <tr>{["code", "credits", "bonus", "total", "per user", "active", "actions"].map((col) => <th key={col} className="px-3 py-2">{col}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((coupon) => (
              <tr key={coupon.id}>
                <td className="border-t border-line px-3 py-2 font-mono">{coupon.code}</td>
                <td className="border-t border-line px-3 py-2">{coupon.credit_amount}</td>
                <td className="border-t border-line px-3 py-2">{coupon.percent_bonus || 0}%</td>
                <td className="border-t border-line px-3 py-2">{coupon.max_uses_total || "unlimited"}</td>
                <td className="border-t border-line px-3 py-2">{coupon.max_uses_per_user}</td>
                <td className="border-t border-line px-3 py-2"><Badge tone={coupon.active ? "good" : "bad"}>{String(coupon.active)}</Badge></td>
                <td className="border-t border-line px-3 py-2"><Button onClick={() => disable(coupon.id)}>Disable</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("home");
  const [bots, setBots] = useState([]);
  const [credits, setCredits] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [reward, setReward] = useState(`reward-${Date.now()}`);
  const [notice, setNotice] = useState("");

  const selectedBot = useMemo(() => bots.find((bot) => bot.id === selectedBotId) || bots[0], [bots, selectedBotId]);

  async function refresh() {
    const [me, nextBots, nextCredits, nextTransactions] = await Promise.all([
      apiFetch("/users/me"),
      apiFetch("/bots"),
      apiFetch("/credits/me"),
      apiFetch("/credits/transactions"),
    ]);
    setUser(me);
    setBots(nextBots);
    setCredits(nextCredits);
    setTransactions(nextTransactions);
    if (!selectedBotId && nextBots[0]) setSelectedBotId(nextBots[0].id);
  }

  useEffect(() => {
    if (getToken()) refresh().catch(() => setToken(null));
  }, []);

  async function addReward() {
    const target = user?.email ? { email: user.email } : { user_id: user.id };
    await apiFetch("/ad-rewards/callback", {
      method: "POST",
      body: JSON.stringify({ reward_id: reward, credits: 1, ...target }),
    });
    setReward(`reward-${Date.now()}`);
    await refresh();
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  if (!user) return <Login onLogin={(nextUser) => { setUser(nextUser); refresh().catch(() => {}); }} />;

  let content = <Home bots={bots} credits={credits} />;
  if (view === "bots") content = <BotsView bots={bots} selectedBotId={selectedBotId} setSelectedBotId={setSelectedBotId} refresh={refresh} />;
  if (view === "create") content = <CreateBot onCreated={(bot) => { setSelectedBotId(bot.id); refresh(); setView("settings"); }} />;
  if (view === "upload") content = <UploadView bot={selectedBot} refresh={refresh} />;
  if (view === "settings") content = <SettingsView bot={selectedBot} refresh={refresh} />;
  if (view === "env") content = <EnvView bot={selectedBot} />;
  if (view === "logs") content = <LogsView bot={selectedBot} />;
  if (view === "credits") content = <CreditsView credits={credits} transactions={transactions} reward={reward} setReward={setReward} addReward={addReward} />;
  if (view === "buyCredits") content = <BuyCreditsView credits={credits} reward={reward} setReward={setReward} addReward={addReward} setView={setView} />;
  if (view === "paymentRequests") content = <PaymentRequestsView refresh={refresh} />;
  if (view === "redeemCoupon") content = <RedeemCouponView refresh={refresh} />;
  if (view === "creditHistory") content = <CreditHistoryView transactions={transactions} />;
  if (view === "admin") content = <AdminView user={user} />;
  if (view === "adminPayments") content = <AdminPaymentRequestsView user={user} refresh={refresh} />;
  if (view === "adminAdjustment") content = <AdminCreditAdjustmentView user={user} refresh={refresh} />;
  if (view === "adminCoupons") content = <AdminCouponsView user={user} />;

  return (
    <Shell view={view} setView={setView} user={user} onLogout={logout}>
      {notice ? <div className="mb-3 rounded-md border border-line bg-white px-4 py-2 text-sm">{notice}</div> : null}
      <div className="mb-3 text-xs text-slate-500">API: {API_BASE}</div>
      {content}
    </Shell>
  );
}

createRoot(document.getElementById("root")).render(<App />);
