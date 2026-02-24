export function getOrCreateSessionId(): string {
    if (typeof window === "undefined") return "";
    let id = sessionStorage.getItem("nep_chat_session");
    if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem("nep_chat_session", id);
    }
    return id;
}

export function resetSessionId(): string {
    const id = crypto.randomUUID();
    sessionStorage.setItem("nep_chat_session", id);
    return id;
}
