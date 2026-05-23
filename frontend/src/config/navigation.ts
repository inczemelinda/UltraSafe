import type { LucideIcon } from "lucide-react";
import {
  ClipboardList,
  FileSearch,
  Home,
  Scale,
  ScrollText,
  SlidersHorizontal,
  Users
} from "lucide-react";

export type NavigationActiveMatch =
  | {
      type: "exact";
      path?: string;
    }
  | {
      type: "prefix";
      path?: string;
    };

export interface AppNavigationItem {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  activeMatch: NavigationActiveMatch;
}

export interface AppNavigationSection {
  id: string;
  label?: string;
  items: AppNavigationItem[];
}

export const employeeNavigationSections: AppNavigationSection[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: [
      {
        id: "employee-overview",
        label: "Overview",
        href: "/employee",
        icon: Home,
        activeMatch: { type: "exact" }
      },
      {
        id: "employee-legal-review",
        label: "Legal Review",
        href: "/legal-review",
        icon: Scale,
        activeMatch: { type: "prefix" }
      }
    ]
  },
  {
    id: "work-queues",
    label: "Work queues",
    items: [
      {
        id: "employee-quotes",
        label: "Quotes",
        href: "/employee/quotes",
        icon: FileSearch,
        activeMatch: { type: "prefix" }
      },
      {
        id: "employee-contracts",
        label: "Contracts",
        href: "/employee/contracts",
        icon: ScrollText,
        activeMatch: { type: "prefix" }
      },
      {
        id: "employee-claims",
        label: "Claims",
        href: "/employee/claims",
        icon: ClipboardList,
        activeMatch: { type: "prefix" }
      }
    ]
  },
  {
    id: "administration",
    label: "Administration",
    items: [
      {
        id: "employee-customers",
        label: "Customers",
        href: "/employee/customers",
        icon: Users,
        activeMatch: { type: "prefix" }
      },
      {
        id: "employee-rules",
        label: "Rules",
        href: "/employee/rules",
        icon: SlidersHorizontal,
        activeMatch: { type: "exact" }
      }
    ]
  }
];

export const employeeNavigationItems = employeeNavigationSections.flatMap(
  (section) => section.items
);

export function isNavigationItemActive(item: AppNavigationItem, currentPathname: string) {
  const activePath = normalizePath(item.activeMatch.path ?? item.href);
  const currentPath = normalizePath(currentPathname);

  if (item.activeMatch.type === "exact") {
    return currentPath === activePath;
  }

  return currentPath === activePath || currentPath.startsWith(`${activePath}/`);
}

function normalizePath(path: string) {
  if (path.length > 1 && path.endsWith("/")) {
    return path.slice(0, -1);
  }

  return path;
}

