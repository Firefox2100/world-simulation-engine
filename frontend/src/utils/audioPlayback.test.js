import { afterEach, describe, expect, it, vi } from "vitest";

class FakeAudioElement {
    constructor() {
        this.paused = true;
        this.src = "";
        this.preload = "";
        this._listeners = {};
        this.playImpl = () => Promise.resolve();
    }

    play() {
        this.paused = false;
        return this.playImpl();
    }

    pause() {
        this.paused = true;
    }

    addEventListener(event, handler) {
        (this._listeners[event] ??= []).push(handler);
    }

    removeEventListener(event, handler) {
        this._listeners[event] = (this._listeners[event] ?? []).filter((h) => h !== handler);
    }

    emit(event) {
        (this._listeners[event] ?? []).slice().forEach((handler) => handler());
    }
}

class FakeAudioContext {
    constructor() {
        this.state = "suspended";
        this.resume = vi.fn(() => {
            this.state = "running";
            return Promise.resolve();
        });
    }
}

let createdAudioElements;

function stubGlobals() {
    createdAudioElements = [];
    vi.stubGlobal(
        "Audio",
        vi.fn(function AudioMock() {
            const element = new FakeAudioElement();
            createdAudioElements.push(element);
            return element;
        }),
    );
    vi.stubGlobal("AudioContext", FakeAudioContext);
}

async function loadModule() {
    vi.resetModules();
    stubGlobals();
    return import("./audioPlayback.js");
}

async function flush(times = 5) {
    let chain = Promise.resolve();
    for (let i = 0; i < times; i += 1) {
        chain = chain.then(() => Promise.resolve());
    }
    await chain;
}

describe("audioPlayback", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("unlocks audio on the first gesture and stops listening afterward", async () => {
        const { ensureAudioUnlockListeners, isAudioUnlocked } = await loadModule();

        expect(isAudioUnlocked()).toBe(false);

        ensureAudioUnlockListeners();
        document.dispatchEvent(new Event("pointerdown"));
        await flush();

        expect(isAudioUnlocked()).toBe(true);
        expect(createdAudioElements).toHaveLength(1);

        document.dispatchEvent(new Event("keydown"));
        await flush();

        // The listeners were removed after the first gesture, so no second unlock cycle ran.
        expect(createdAudioElements).toHaveLength(1);
    });

    it("does nothing on repeated calls once already unlocked", async () => {
        const { ensureAudioUnlockListeners, isAudioUnlocked } = await loadModule();

        ensureAudioUnlockListeners();
        document.dispatchEvent(new Event("pointerdown"));
        await flush();
        expect(isAudioUnlocked()).toBe(true);

        ensureAudioUnlockListeners();
        document.dispatchEvent(new Event("keydown"));
        await flush();

        expect(createdAudioElements).toHaveLength(1);
    });

    it("plays a sequence of URLs one at a time, advancing only after each ends", async () => {
        const { playAudioUrlSequence } = await loadModule();

        const started = [];
        const { done } = playAudioUrlSequence(["a.mp3", "b.mp3"], {
            onTrackStart: (url) => started.push(url),
        });

        await flush();
        expect(started).toEqual(["a.mp3"]);
        const audio = createdAudioElements.at(-1);
        expect(audio.src).toBe("a.mp3");

        audio.emit("ended");
        await flush();

        expect(started).toEqual(["a.mp3", "b.mp3"]);
        expect(audio.src).toBe("b.mp3");

        audio.emit("ended");
        await done;

        expect(started).toEqual(["a.mp3", "b.mp3"]);
    });

    it("stops without throwing when play() is rejected", async () => {
        const { playAudioUrlSequence } = await loadModule();
        vi.stubGlobal(
            "Audio",
            vi.fn(function AudioMock() {
                const element = new FakeAudioElement();
                element.playImpl = () => Promise.reject(new Error("NotAllowedError"));
                createdAudioElements.push(element);
                return element;
            }),
        );

        const started = [];
        const { done } = playAudioUrlSequence(["a.mp3", "b.mp3"], {
            onTrackStart: (url) => started.push(url),
        });

        await expect(done).resolves.toBeUndefined();
        expect(started).toEqual(["a.mp3"]);
    });

    it("cancel() halts mid-sequence without starting further tracks", async () => {
        const { playAudioUrlSequence } = await loadModule();

        const started = [];
        const { cancel, done } = playAudioUrlSequence(["a.mp3", "b.mp3", "c.mp3"], {
            onTrackStart: (url) => started.push(url),
        });

        await flush();
        expect(started).toEqual(["a.mp3"]);

        cancel();
        const audio = createdAudioElements.at(-1);
        audio.emit("ended");
        await done;

        expect(started).toEqual(["a.mp3"]);
    });
});
