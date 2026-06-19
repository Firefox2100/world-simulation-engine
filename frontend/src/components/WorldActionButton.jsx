function ActionIcon({ type }) {
    if (type === "edit") {
        return (
            <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                <path d="M4 20h4.8L19.4 9.4a2 2 0 0 0 0-2.8l-2-2a2 2 0 0 0-2.8 0L4 15.2V20Zm2-2v-2l8.6-8.6 2 2L8 18H6Zm10-12 2 2 .6-.6-2-2-.6.6Z" />
            </svg>
        );
    }

    if (type === "createSimulation") {
        return (
            <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                <path d="M8 5.6v12.8L18.2 12 8 5.6Zm2 3.6 4.4 2.8-4.4 2.8V9.2Z" />
            </svg>
        );
    }

    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
            <path d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-2 6h10l-.7 11H7.7L7 9Zm2.1 2 .4 7h5l.4-7H9.1Z" />
        </svg>
    );
}

export function WorldActionButton({ type, label, danger = false, onClick }) {
    return (
        <button
            type="button"
            className={`card-icon-button${danger ? " danger" : ""}`}
            onClick={onClick}
            aria-label={label}
            title={label}
        >
            <ActionIcon type={type} />
        </button>
    );
}
