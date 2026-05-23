import {
  CheckCircle2,
  Info,
  X,
  XCircle
} from "lucide-react";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState
} from "react";

type ToastTone = "success" | "info" | "error";

interface Toast {
  id: string;
  message: string;
  tone: ToastTone;
}

interface ToastContextValue {
  showToast: (message: string, tone?: ToastTone) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((items) => items.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, tone: ToastTone = "success") => {
      const toast = {
        id: `${Date.now()}-${Math.random()}`,
        message,
        tone
      };
      setToasts((items) => [toast, ...items].slice(0, 4));
      window.setTimeout(() => dismiss(toast.id), 3400);
    },
    [dismiss]
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed left-1/2 top-[max(1rem,env(safe-area-inset-top))] z-[100] flex w-[min(24rem,calc(100vw-2rem))] -translate-x-1/2 flex-col gap-3 sm:left-auto sm:right-[max(1rem,env(safe-area-inset-right))] sm:translate-x-0">
        {toasts.map((toast) => {
          const Icon = toast.tone === "error" ? XCircle : toast.tone === "info" ? Info : CheckCircle2;
          const toneClass =
            toast.tone === "error"
              ? "border-red-200 bg-red-50 text-red-800"
              : toast.tone === "info"
                ? "border-orange-200 bg-orange-50 text-orange-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-800";
          return (
            <div
              className={`pointer-events-auto flex max-w-full items-start gap-3 rounded-lg border p-3 shadow-soft ${toneClass}`}
              key={toast.id}
              role="status"
            >
              <Icon className="mt-0.5 h-5 w-5 shrink-0" />
              <p className="min-w-0 flex-1 text-sm font-medium">{toast.message}</p>
              <button
                aria-label="Dismiss notification"
                className="rounded p-1 hover:bg-white/70"
                onClick={() => dismiss(toast.id)}
                type="button"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}

