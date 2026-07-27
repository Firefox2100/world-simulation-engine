import { apiRequest } from "@/api/client";

export async function transcribeSpeech(audioBlob, { filename = "recording.webm", language = null } = {}) {
    const formData = new FormData();
    formData.set("file", audioBlob, filename);

    if (language) {
        formData.set("language", language);
    }

    return apiRequest("/speech-recognition/transcribe", {
        method: "POST",
        body: formData,
    });
}
