import { CircleUserRound, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";
import {
  ClipboardList,
  FileSearch,
  Home,
  ScrollText,
  UserRound
} from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import {
  employeeNavigationSections,
  isNavigationItemActive
} from "../../config/navigation";
import { useAuth } from "../../context/AuthContext";
import { Logo } from "../ui";

const expandedWidthClass = "w-64";
const collapsedWidthClass = "w-16";

const clientNavigationItems = [
  { id: "client-overview", label: "Dashboard", href: "/client", icon: Home, exact: true },
  { id: "client-quotes", label: "Quotes", href: "/client/quotes", icon: FileSearch },
  { id: "client-contracts", label: "Contracts", href: "/client/contracts", icon: ScrollText },
  { id: "client-claims", label: "Claims", href: "/client/claims", icon: ClipboardList },
  { id: "client-account", label: "Account", href: "/client/account", icon: UserRound }
];

function getInitials(name?: string) {
  if (!name) return "US";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "US";
}

function isClientItemActive(item: (typeof clientNavigationItems)[number], pathname: string) {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function ClientAppSidebar() {
  const { user } = useAuth();
  const location = useLocation();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-zinc-200 bg-white px-4 py-5 text-zinc-900 shadow-[18px_0_45px_-40px_rgba(24,24,27,0.35)]">
      <div className="flex items-center border-b border-zinc-200 pb-5">
        <Logo to="/client" />
      </div>

      <div className="px-2 pt-5 text-[11px] font-extrabold uppercase tracking-[0.16em] text-zinc-400">
        Workspace
      </div>
      <nav aria-label="Client navigation" className="mt-2 flex-1 space-y-1">
        {clientNavigationItems.map((item) => {
          const Icon = item.icon;
          const isActive = isClientItemActive(item, location.pathname);
          return (
            <NavLink
              className={[
                "group flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-zinc-100",
                isActive
                  ? "bg-zinc-950 text-white shadow-sm"
                  : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
              ].join(" ")}
              key={item.id}
              to={item.href}
            >
              <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-orange-400" : "text-zinc-400 group-hover:text-zinc-700"}`} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <Link
        aria-label="Client account"
        className="mt-5 flex items-center gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-left transition hover:border-zinc-300 hover:bg-white focus:outline-none focus:ring-4 focus:ring-zinc-100"
        to="/client/account"
      >
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-zinc-950 text-sm font-extrabold text-white">
          {getInitials(user?.fullName)}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-extrabold text-zinc-950">
            {user?.fullName ?? "Client account"}
          </span>
          <span className="block truncate text-xs font-semibold text-zinc-500">
            {user?.email ?? "UltraSafe client"}
          </span>
        </span>
      </Link>
    </aside>
  );
}

export function AppSidebar() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { user } = useAuth();
  const location = useLocation();
  const secondaryAccountText = user?.title ?? user?.role ?? user?.email ?? "Employee";
  const collapseLabel = isCollapsed ? "Expand navigation" : "Collapse navigation";

  return (
    <aside
      className={`flex h-screen shrink-0 flex-col border-r border-zinc-200 bg-white px-3 py-5 text-zinc-900 shadow-[18px_0_45px_-40px_rgba(24,24,27,0.35)] transition-[width] duration-200 ease-out ${
        isCollapsed ? collapsedWidthClass : expandedWidthClass
      }`}
    >
      <div className={`flex items-center border-b border-zinc-200 pb-5 ${isCollapsed ? "justify-center" : "gap-2"}`}>
        {!isCollapsed ? (
          <div className="min-w-0 flex-1">
            <Logo to="/employee" />
          </div>
        ) : null}
        <button
          aria-label={collapseLabel}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-950 focus:outline-none focus:ring-4 focus:ring-zinc-100"
          onClick={() => setIsCollapsed((current) => !current)}
          title={collapseLabel}
          type="button"
        >
          {isCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <nav aria-label="Employee navigation" className="mt-5 flex-1 space-y-5 overflow-y-auto overflow-x-hidden pr-0.5">
        {employeeNavigationSections.map((section) => (
          <section aria-label={section.label} className="space-y-1.5" key={section.id}>
            {section.label && !isCollapsed ? (
              <h2 className="px-3 text-[11px] font-extrabold uppercase tracking-[0.16em] text-zinc-400">
                {section.label}
              </h2>
            ) : null}
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = isNavigationItemActive(item, location.pathname);

                return (
                  <NavLink
                    aria-label={isCollapsed ? item.label : undefined}
                    className={[
                      "group relative flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-zinc-100",
                      isCollapsed ? "justify-center" : "",
                      isActive
                        ? "bg-zinc-950 text-white shadow-sm before:absolute before:left-1 before:top-2 before:h-6 before:w-1 before:rounded-full before:bg-orange-400"
                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
                    ].join(" ")}
                    key={item.id}
                    title={isCollapsed ? item.label : undefined}
                    to={item.href}
                  >
                    <Icon
                      aria-hidden="true"
                      className={`h-4 w-4 shrink-0 ${
                        isActive ? "text-orange-400" : "text-zinc-400 group-hover:text-zinc-700"
                      }`}
                    />
                    {!isCollapsed ? <span className="truncate">{item.label}</span> : null}
                  </NavLink>
                );
              })}
            </div>
          </section>
        ))}
      </nav>

      <Link
        aria-label="Employee account"
        className={[
          "mt-4 flex items-center gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-left transition hover:border-zinc-300 hover:bg-white focus:outline-none focus:ring-4 focus:ring-zinc-100",
          isCollapsed ? "justify-center" : ""
        ].join(" ")}
        title={isCollapsed ? user?.fullName ?? "Employee account" : undefined}
        to="/employee/account"
      >
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-zinc-950 text-white">
          <CircleUserRound className="h-4 w-4" />
        </span>
        {!isCollapsed ? (
          <span className="min-w-0">
            <span className="block truncate text-sm font-extrabold text-zinc-950">
              {user?.fullName ?? "Employee account"}
            </span>
            <span className="block truncate text-xs font-semibold capitalize text-zinc-500">
              {secondaryAccountText}
            </span>
          </span>
        ) : null}
      </Link>
    </aside>
  );
}


