import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import enCommon from "@/locales/en/common.json";
import zhCommon from "@/locales/zh/common.json";

i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
        fallbackLng: "en",
        supportedLngs: ["en", "zh"],
        defaultNS: "common",
        resources: {
            en: { common: enCommon },
            zh: { common: zhCommon },
        },
        interpolation: {
            escapeValue: false,
        },
    });

export default i18n;
