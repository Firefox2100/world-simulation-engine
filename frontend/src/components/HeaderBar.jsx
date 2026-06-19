import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export function HeaderBar() {
    const { t } = useTranslation();

    return (
        <header className="app-header">
            <div className="app-title">{t("app.title")}</div>

            <nav className="app-nav" aria-label={t("app.navigationLabel")}>
                <NavLink to="/" end className="app-nav-link">
                    {t("app.nav.simulations")}
                </NavLink>
                <NavLink to="/worlds" className="app-nav-link">
                    {t("app.nav.worlds")}
                </NavLink>
                <NavLink to="/connections" className="app-nav-link">
                    {t("app.nav.connections")}
                </NavLink>
            </nav>

            <LanguageSwitcher />
        </header>
    );
}
