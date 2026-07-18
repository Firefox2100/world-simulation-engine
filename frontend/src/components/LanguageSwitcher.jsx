import { useTranslation } from "react-i18next";

export function LanguageSwitcher() {
    const { i18n } = useTranslation();

    return (
        <select
            className="language-switcher"
            value={i18n.language}
            onChange={(event) => i18n.changeLanguage(event.target.value)}
        >
            <option value="en">English</option>
            <option value="zh">中文</option>
        </select>
    );
}
