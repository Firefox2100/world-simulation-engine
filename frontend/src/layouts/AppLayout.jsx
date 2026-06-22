import { Outlet, useLocation } from "react-router-dom";
import { HeaderBar } from "@/components/HeaderBar";

export function AppLayout() {
    const location = useLocation();
    const isChatPage = location.pathname.startsWith("/simulations/");

    return (
        <div className="app-shell">
            <HeaderBar />

            <main className={`app-main${isChatPage ? " full-bleed-main" : ""}`}>
                <Outlet />
            </main>
        </div>
    );
}
