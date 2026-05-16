export function Panel({ title, actions, children }) {
  return (
    <section className="rounded-md border border-line bg-white">
      <div className="flex min-h-14 items-center justify-between border-b border-line px-4 py-3">
        <h1 className="text-base font-semibold">{title}</h1>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({ children, tone = "default", className = "", ...props }) {
  const tones = {
    default: "border-line bg-white text-slate-800 hover:bg-panel",
    primary: "border-brand bg-brand text-white hover:bg-teal-800",
    danger: "border-red-700 bg-red-700 text-white hover:bg-red-800",
  };
  return (
    <button
      className={`focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${tones[tone]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Input(props) {
  return <input className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm" {...props} />;
}

export function Textarea(props) {
  return <textarea className="focus-ring min-h-24 w-full rounded-md border border-line px-3 py-2 text-sm" {...props} />;
}

export function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-slate-100 text-slate-700",
    good: "bg-emerald-100 text-emerald-800",
    warn: "bg-amber-100 text-amber-800",
    bad: "bg-red-100 text-red-800",
  };
  return <span className={`rounded px-2 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
