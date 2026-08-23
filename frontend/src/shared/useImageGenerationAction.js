import { useEffect, useRef, useState } from "react";

export function useImageGenerationAction(onGenerate) {
    const [state, setState] = useState("idle");
    const [error, setError] = useState(null);
    const resetTimerRef = useRef(null);

    useEffect(() => () => {
        if (resetTimerRef.current) {
            clearTimeout(resetTimerRef.current);
        }
    }, []);

    async function trigger() {
        if (state === "generating") {
            return;
        }

        setState("generating");
        setError(null);

        try {
            await onGenerate();
            setState("success");
        } catch (err) {
            setError(err.message);
            setState("error");
        } finally {
            resetTimerRef.current = setTimeout(() => setState("idle"), 3000);
        }
    }

    return { state, error, trigger };
}
