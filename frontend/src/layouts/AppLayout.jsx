import { Outlet } from "react-router-dom";
import { HeaderBar } from "@/components/HeaderBar";

export function AppLayout() {
    return (
        <div className="app-shell">
            <HeaderBar />

            <main className="app-main">
                <Outlet />
            </main>
        </div>
    );
}
