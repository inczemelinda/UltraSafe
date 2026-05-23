import type { ReactNode } from "react";

export function EmployeePageHeader({
  title,
  subtitle,
  actions,
  children,
  className = ""
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={`mb-5 rounded-xl border border-zinc-200 bg-white/95 p-4 shadow-sm backdrop-blur sm:p-5 ${className}`}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <p className="mb-1 text-[11px] font-extrabold uppercase tracking-[0.16em] text-orange-600">Underwriting workspace</p>
          <h1 className="text-2xl font-extrabold tracking-normal text-zinc-950">{title}</h1>
          {subtitle ? (
            <div className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
              {subtitle}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children ? <div className="mt-4">{children}</div> : null}
    </header>
  );
}

