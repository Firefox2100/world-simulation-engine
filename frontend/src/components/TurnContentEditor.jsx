import { useTranslation } from "react-i18next";

// A system turn's content is always NarrationProposal JSON ({"blocks":[...]}), matching what
// Narrator.serialize_content stores for a live turn (see narration.py / world_assembler.py's
// _narration_content) - never plain prose. This editor works directly in that structured shape
// instead of exposing the raw JSON string, so a world author edits narration/speech blocks the
// same way whether the turn came from a live simulation or a SillyTavern import.
function parseBlocks(content) {
    if (!content) {
        return [{ type: "narration", text: "" }];
    }
    try {
        const parsed = JSON.parse(content);
        if (parsed && Array.isArray(parsed.blocks) && parsed.blocks.length > 0) {
            return parsed.blocks.map((block) => ({
                type: block.type === "speech" ? "speech" : "narration",
                text: block.text ?? "",
                character_id: block.character_id ?? null,
                character_name: block.character_name ?? null,
            }));
        }
    } catch {
        // Legacy plain-text content (authored before this editor existed, or a hand-typed value)
        // is treated as a single narration block - the next edit re-serializes it as proper
        // blocks JSON, so nothing needs an explicit "convert" step.
    }
    return [{ type: "narration", text: content }];
}

function serializeBlocks(blocks) {
    return JSON.stringify({
        blocks: blocks.map((block) =>
            block.type === "speech"
                ? {
                      type: "speech",
                      character_id: block.character_id,
                      character_name: block.character_name,
                      text: block.text,
                  }
                : { type: "narration", text: block.text },
        ),
    });
}

/**
 * Structured editor for `Turn.content`. `user_input` turns are always plain text (a live
 * simulation stores the user's raw input verbatim - see world_simulator.py's
 * commit_user_actions); every other turn type is edited as ordered narration/speech blocks.
 */
export function TurnContentEditor({ content, characters, type, onChange }) {
    const { t } = useTranslation();

    if (type === "user_input") {
        return (
            <textarea
                className="multi-line-input"
                value={content ?? ""}
                onChange={(event) => onChange(event.target.value)}
            />
        );
    }

    const blocks = parseBlocks(content);

    function commit(nextBlocks) {
        onChange(serializeBlocks(nextBlocks.length > 0 ? nextBlocks : [{ type: "narration", text: "" }]));
    }

    function updateBlock(index, patch) {
        const next = blocks.slice();
        next[index] = { ...next[index], ...patch };
        commit(next);
    }

    function removeBlock(index) {
        commit(blocks.filter((_, blockIndex) => blockIndex !== index));
    }

    function moveBlock(index, direction) {
        const targetIndex = index + direction;
        if (targetIndex < 0 || targetIndex >= blocks.length) return;
        const next = blocks.slice();
        [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
        commit(next);
    }

    function addBlock(blockType) {
        const block =
            blockType === "speech"
                ? {
                      type: "speech",
                      text: "",
                      character_id: characters[0]?.id ?? null,
                      character_name: characters[0]?.name ?? null,
                  }
                : { type: "narration", text: "" };
        commit([...blocks, block]);
    }

    return (
        <div className="turn-block-editor">
            {blocks.map((block, index) => (
                <div className="turn-block-editor-row" key={index}>
                    <div className="turn-block-editor-row-header">
                        <span className="turn-block-editor-row-type">
                            {t(`worldCreate.newEditor.turnBlocks.types.${block.type}`)}
                        </span>
                        <div className="turn-block-editor-row-actions">
                            <button
                                type="button"
                                className="icon-button"
                                disabled={index === 0}
                                onClick={() => moveBlock(index, -1)}
                                aria-label={t("worldCreate.newEditor.turnBlocks.moveUp")}
                            >
                                &uarr;
                            </button>
                            <button
                                type="button"
                                className="icon-button"
                                disabled={index === blocks.length - 1}
                                onClick={() => moveBlock(index, 1)}
                                aria-label={t("worldCreate.newEditor.turnBlocks.moveDown")}
                            >
                                &darr;
                            </button>
                            <button
                                type="button"
                                className="icon-button st-import-remove-button"
                                onClick={() => removeBlock(index)}
                                aria-label={t("worldCreate.newEditor.turnBlocks.remove")}
                            >
                                &times;
                            </button>
                        </div>
                    </div>
                    {block.type === "speech" ? (
                        <select
                            className="single-line-input"
                            value={block.character_id ?? ""}
                            onChange={(event) => {
                                const character = characters.find(
                                    (candidate) => candidate.id === event.target.value,
                                );
                                updateBlock(index, {
                                    character_id: character?.id ?? null,
                                    character_name: character?.name ?? null,
                                });
                            }}
                        >
                            <option value="">{t("worldCreate.newEditor.emptySelect")}</option>
                            {characters.map((character) => (
                                <option key={character.id} value={character.id}>
                                    {character.name}
                                </option>
                            ))}
                        </select>
                    ) : null}
                    <textarea
                        className="multi-line-input"
                        value={block.text}
                        onChange={(event) => updateBlock(index, { text: event.target.value })}
                    />
                </div>
            ))}
            <div className="modal-actions inline-actions">
                <button type="button" className="secondary-button" onClick={() => addBlock("narration")}>
                    {t("worldCreate.newEditor.turnBlocks.addNarration")}
                </button>
                <button
                    type="button"
                    className="secondary-button"
                    disabled={characters.length === 0}
                    onClick={() => addBlock("speech")}
                >
                    {t("worldCreate.newEditor.turnBlocks.addSpeech")}
                </button>
            </div>
        </div>
    );
}
