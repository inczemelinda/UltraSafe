import { Outlet } from "react-router-dom";
import { AppSidebar, ClientAppSidebar } from "../components/navigation/AppSidebar";
import {
  ClientNavbar,
  EmployeeDashboardBackground,
  PublicBackground,
  PublicNavbar
} from "../components/ui";
import { SHOW_MOCK_DATA_INDICATOR } from "../config/dataSource";

export function PublicLayout() {
  return (
    <PublicBackground>
      <PublicNavbar />
      <MockDataIndicator />
      <main className="flex min-h-0 flex-1 flex-col">
        <Outlet />
      </main>
    </PublicBackground>
  );
}

export function ClientLayout() {
  return (
    <div className="paper-background flex min-h-screen text-zinc-950 lg:h-screen lg:overflow-hidden">
      <div className="hidden lg:flex">
        <ClientAppSidebar />
      </div>
      <MockDataIndicator />
      <div className="flex min-w-0 flex-1 flex-col lg:overflow-y-auto">
        <div className="lg:hidden">
          <ClientNavbar />
        </div>
        <main className="flex min-h-0 w-full flex-1 flex-col px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function EmployeeLayout() {
  return (
    <div className="paper-background flex h-screen overflow-hidden text-zinc-950">
      <AppSidebar />
      <MockDataIndicator />
      <div className="min-w-0 flex-1 overflow-y-auto">
        <EmployeeDashboardBackground>
          <main className="flex min-h-0 w-full flex-1 flex-col px-4 py-4 sm:px-6 sm:py-5 lg:px-8">
            <Outlet />
          </main>
        </EmployeeDashboardBackground>
      </div>
    </div>
  );
}

function MockDataIndicator() {
  if (!SHOW_MOCK_DATA_INDICATOR) return null;
  return (
    <div className="pointer-events-none fixed right-3 top-3 z-[60] rounded-md border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-bold uppercase tracking-normal text-amber-900 shadow-sm">
      Mock data mode
    </div>
  );
}

