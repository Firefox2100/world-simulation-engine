export function labelFor(entity, fallback) {
    return entity?.name || entity?.model || entity?.id || fallback;
}
