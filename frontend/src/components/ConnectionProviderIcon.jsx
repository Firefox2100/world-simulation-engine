import { ComfyUI, Ollama, OpenAI } from "@lobehub/icons";

const iconSize = 28;

export function ConnectionProviderIcon({ provider }) {
    if (provider === "openai") {
        return <OpenAI size={iconSize} />;
    }

    if (provider === "ollama") {
        return <Ollama size={iconSize} />;
    }

    if (provider === "comfy_ui") {
        return <ComfyUI size={iconSize} />;
    }

    return <span className="connection-provider-fallback">{provider.slice(0, 1).toUpperCase()}</span>;
}
