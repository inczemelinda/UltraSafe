import { type FormEvent, type ReactNode, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  FileText,
  Gauge,
  ShieldCheck
} from "lucide-react";
import {
  Button,
  Logo,
  Modal,
  Panel,
  PrimaryLink
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { USE_MOCK_DATA } from "../config/dataSource";
import { registerClient, signIn } from "../services/authService";

export function HomePage() {
  const trustStats = [
    ["2 min", "average quote time"],
    ["98.4%", "claims approval rate"],
    ["24/7", "client portal access"]
  ];
  const productCards = [
    {
      icon: ShieldCheck,
      title: "Clear coverage",
      text: "Property, contents, liability, and claim status are shown in one readable workspace."
    },
    {
      icon: Gauge,
      title: "Live pricing",
      text: "Quotes explain the premium drivers before a contract is generated."
    },
    {
      icon: FileText,
      title: "Contract flow",
      text: "Clients and underwriters work from the same clear policy information."
    }
  ];

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col px-4 py-8 sm:px-6 lg:px-8">
      <section className="grid min-h-[calc(100dvh-170px)] items-center gap-10 py-8 lg:grid-cols-[1.02fr_0.98fr]">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs font-extrabold uppercase tracking-[0.16em] text-orange-700">
            <span className="h-2 w-2 rounded-full bg-orange-500" />
            Property insurance, made clear
          </span>
          <h1 className="mt-6 text-5xl font-extrabold leading-[0.95] tracking-normal text-zinc-950 sm:text-6xl lg:text-7xl">
            Insurance you actually{" "}
            <em className="font-serif font-normal italic text-orange-600">understand.</em>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-600">
            UltraSafe turns property details, underwriting decisions, contracts, and claims into a calm digital workspace for clients and employees.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-zinc-950 px-5 py-3 text-sm font-extrabold text-white shadow-sm transition hover:bg-zinc-800 focus:outline-none focus:ring-4 focus:ring-zinc-200"
              to="/signin"
            >
              Get my quote <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              className="inline-flex min-h-12 items-center justify-center rounded-lg border border-zinc-300 bg-white px-5 py-3 text-sm font-extrabold text-zinc-800 shadow-sm transition hover:border-zinc-400 hover:bg-zinc-50 focus:outline-none focus:ring-4 focus:ring-zinc-100"
              to="/about"
            >
              See how it works
            </Link>
          </div>
          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            {trustStats.map(([value, label]) => (
              <div className="border-l border-zinc-200 pl-4" key={label}>
                <div className="text-2xl font-extrabold text-zinc-950">{value}</div>
                <div className="mt-1 text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">{label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative">
          <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-lg">
            <div className="flex items-start justify-between gap-4 border-b border-zinc-200 pb-5">
              <div>
                <div className="text-xs font-extrabold uppercase tracking-[0.16em] text-zinc-400">Live quote</div>
                <div className="mt-2 text-xl font-extrabold text-zinc-950">Apartment · Str. Aviatorilor 12</div>
                <div className="mt-1 text-sm font-semibold text-zinc-500">Ana Popescu · București</div>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-extrabold text-emerald-700 ring-1 ring-emerald-200">
                <BadgeCheck className="h-3.5 w-3.5" /> Ready
              </span>
            </div>
            <div className="grid gap-4 py-5 sm:grid-cols-2">
              <div className="rounded-xl bg-zinc-950 p-4 text-white">
                <div className="text-xs font-bold uppercase tracking-[0.12em] text-white/60">Monthly premium</div>
                <div className="mt-3 text-4xl font-extrabold">250<span className="ml-1 text-base text-white/60">RON</span></div>
                <div className="mt-3 text-sm text-white/60">Coverage 135,000 RON</div>
              </div>
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
                <div className="text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">Risk score</div>
                <div className="mt-3 flex items-end gap-2">
                  <span className="text-4xl font-extrabold text-zinc-950">92</span>
                  <span className="pb-1 text-sm font-bold text-zinc-500">/100</span>
                </div>
                <div className="mt-3 text-sm font-bold text-emerald-700">Low risk property</div>
              </div>
            </div>
            <div className="space-y-3">
              {[
                ["Base premium", "270 RON", "w-[68%]"],
                ["Construction discount", "-5%", "w-[42%]"],
                ["Security discount", "-8%", "w-[34%]"]
              ].map(([label, value, width]) => (
                <div className="grid grid-cols-[1fr_2fr_auto] items-center gap-3 text-sm" key={label}>
                  <span className="font-bold text-zinc-600">{label}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-zinc-100">
                    <span className={`block h-full rounded-full bg-orange-500 ${width}`} />
                  </span>
                  <span className="font-extrabold text-zinc-950">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {productCards.map((card) => {
              const Icon = card.icon;
              return (
                <div className="rounded-xl border border-zinc-200 bg-white/90 p-4 shadow-sm" key={card.title}>
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-orange-50 text-orange-600">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h2 className="mt-3 text-sm font-extrabold text-zinc-950">{card.title}</h2>
                  <p className="mt-1 text-xs leading-5 text-zinc-600">{card.text}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}

export function AboutPage() {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-150px)] w-full max-w-3xl items-center px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <Panel className="w-full">
        <h1 className="text-2xl font-bold text-slate-950">About UltraSafe</h1>
        <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
          <p>
            UltraSafe helps clients get property insurance quotes and contracts in one place.
          </p>
          <p>
            Employees can review quotes, contracts, claims, and underwriting rules from a focused workspace.
          </p>
        </div>
        <div className="mt-6 flex justify-end">
          <PrimaryLink to="/">Back Home</PrimaryLink>
        </div>
      </Panel>
    </main>
  );
}

export function ContactPage() {
  const contacts = [
    ["Phone", "+40 700 123 456"],
    ["Email", "contact@ultrasafe.ro"],
    ["Support", "support@ultrasafe.ro"],
    ["Claims", "claims@ultrasafe.ro"],
    ["Address", "26 Libertatea Street, Cluj-Napoca, România"],
    ["Support hours", "Monday - Friday, 09:00 - 18:00"]
  ];
  return (
    <main className="mx-auto flex min-h-[calc(100vh-150px)] w-full max-w-3xl items-center px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <Panel className="w-full">
        <h1 className="text-2xl font-bold text-slate-950">Contact Us</h1>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          {contacts.map(([label, value]) => (
            <div className="rounded-lg border border-slate-200/80 bg-slate-50 p-3" key={label}>
              <dt className="text-xs font-bold uppercase tracking-normal text-slate-500">{label}</dt>
              <dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-6 flex justify-end">
          <PrimaryLink to="/">Back Home</PrimaryLink>
        </div>
      </Panel>
    </main>
  );
}

export function SignInPage() {
  const [email, setEmail] = useState(USE_MOCK_DATA ? "ana.popescu@client.com" : "");
  const [password, setPassword] = useState(USE_MOCK_DATA ? "client123" : "");
  const [showNotFound, setShowNotFound] = useState(false);
  const { setUser } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!email || !password) {
      showToast("Email and password are required.", "error");
      return;
    }
    try {
      const user = await signIn(email, password);
      if (!user) {
        setShowNotFound(true);
        return;
      }
      setUser(user);
      navigate(user.role === "client" ? "/client" : "/employee", { replace: true });
    } catch (error) {
      showToast(getErrorMessage(error, "Could not connect to the service."), "error");
    }
  }

  return (
    <AuthShell>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <RequiredInput label="Email" onChange={setEmail} type="email" value={email} />
        <RequiredInput label="Password" onChange={setPassword} type="password" value={password} />
        <Button className="w-full" type="submit" variant="primary">
          Sign in
        </Button>
        <p className="text-center text-sm text-slate-600">
          New to UltraSafe?{" "}
          <Link className="font-bold text-slate-950 underline-offset-4 hover:underline" to="/register">
            Create account
          </Link>
        </p>
      </form>
      <Modal
        actions={
          <>
            <Button onClick={() => navigate("/")} variant="secondary">
              Back Home
            </Button>
            <Button onClick={() => navigate("/register")} variant="primary">
              Create account
            </Button>
          </>
        }
        onClose={() => setShowNotFound(false)}
        open={showNotFound}
        title="Account not found"
      >
        No account matches these details.
      </Modal>
    </AuthShell>
  );
}

export function RegisterPage() {
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: ""
  });
  const { showToast } = useToast();
  const navigate = useNavigate();

  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (Object.values(form).some((value) => !value)) {
      showToast("All fields are required.", "error");
      return;
    }
    if (form.password !== form.confirmPassword) {
      showToast("Password confirmation must match.", "error");
      return;
    }
    try {
      await registerClient(form);
      showToast("Your account has been created. Please sign in to continue.");
      navigate("/signin");
    } catch (error) {
      showToast(getErrorMessage(error, "Could not create the account."), "error");
    }
  }

  return (
    <AuthShell>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <RequiredInput label="Full name" onChange={(value) => update("fullName", value)} value={form.fullName} />
        <RequiredInput label="Email" onChange={(value) => update("email", value)} type="email" value={form.email} />
        <RequiredInput label="Phone" onChange={(value) => update("phone", value)} value={form.phone} />
        <RequiredInput label="Password" onChange={(value) => update("password", value)} type="password" value={form.password} />
        <RequiredInput label="Confirm password" onChange={(value) => update("confirmPassword", value)} type="password" value={form.confirmPassword} />
        <Button className="w-full" type="submit" variant="primary">
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-150px)] w-full max-w-5xl items-center px-4 py-8 sm:px-6 sm:py-10">
      <div className="grid w-full overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-lg lg:grid-cols-[0.95fr_1.05fr]">
        <div className="hidden bg-zinc-950 p-8 text-white lg:flex lg:flex-col lg:justify-between">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-orange-400">UltraSafe portal</p>
            <h1 className="mt-5 text-4xl font-extrabold leading-tight">
              One workspace for quotes, contracts, and claims.
            </h1>
            <p className="mt-4 text-sm leading-6 text-white/65">
              Sign in to continue with your quotes, contracts, claims, and underwriting workflows.
            </p>
          </div>
          <div className="grid gap-3 text-sm font-semibold text-white/75">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">Live quote status</div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">Generated contracts</div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">Claim decisions</div>
          </div>
        </div>
        <div className="p-5 sm:p-8">
          <div className="mb-6 flex justify-center">
            <Logo centered size="auth" to="/" />
          </div>
          {children}
        </div>
      </div>
    </main>
  );
}

function RequiredInput({
  label,
  onChange,
  type = "text",
  value
}: {
  label: string;
  onChange: (value: string) => void;
  type?: string;
  value: string;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div>
      <label className="mb-1.5 block text-sm font-bold text-zinc-700" htmlFor={id}>
        {label} <span className="text-orange-600" aria-label="required">*</span>
      </label>
      <input
        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-400 focus:border-orange-500 focus:ring-4 focus:ring-orange-100"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </div>
  );
}
