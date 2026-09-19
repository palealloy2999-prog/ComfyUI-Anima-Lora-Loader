// Pure synchronization functions; LoRA Manager owns all list rendering.
const number = "[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?";
const tags = new RegExp(`<lora:([^<>:]+):(${number})(?::(${number}))?>`, "gi");
const identity = (name) => name.replaceAll("\\", "/").replace(/\.(safetensors|pt|pth|ckpt|bin)$/i, "");

export function mergeText(text, entries) {
    const result = entries.map((entry) => ({ ...entry }));
    for (const match of String(text).matchAll(tags)) {
        const name = match[1].trim();
        const strength = Number(match[2]);
        const clipStrength = Number(match[3] ?? match[2]);
        if (!name || !Number.isFinite(strength) || !Number.isFinite(clipStrength)) continue;
        const entry = result.find((item) => identity(item.name) === identity(name));
        if (entry) {
            Object.assign(entry, { strength, clipStrength, expanded: strength !== clipStrength || entry.expanded });
        } else {
            result.push({ name, active: true, strength, clipStrength, expanded: strength !== clipStrength });
        }
    }
    return result;
}

export function listText(entries) {
    return entries.filter((entry) => entry.active).map((entry) => {
        const strength = Number(entry.strength);
        const clip = Number(entry.clipStrength ?? entry.strength);
        return `<lora:${entry.name}:${strength}${strength === clip ? "" : `:${clip}`}>`;
    }).join(" ");
}

export function connectWidgets(node) {
    const text = node.widgets?.find((widget) => widget.name === "text");
    const loras = node.widgets?.find((widget) => widget.name === "loras");
    if (!text || !loras || node.__animaConnected) return;
    node.__animaConnected = true;
    node.serialize_widgets = true;
    let isUpdating = false;
    const textCallback = text.callback;
    const listCallback = loras.callback;
    text.callback = function (value, ...args) {
        if (isUpdating) return;
        isUpdating = true;
        try {
            textCallback?.call(this, value, ...args);
            loras.value = mergeText(value, loras.value ?? []);
        } finally {
            isUpdating = false;
        }
    };
    loras.callback = function (value, ...args) {
        if (isUpdating) return;
        isUpdating = true;
        try {
            listCallback?.call(this, value, ...args);
            text.value = listText(value ?? loras.value ?? []);
        } finally {
            isUpdating = false;
        }
    };
}

export function preserveZeroClip(widget) {
    // The installed Manager's setter uses `clipStrength || strength`.
    // Its numeric controls accept "0"; serialize back to an actual number.
    if (Object.prototype.hasOwnProperty.call(widget, "__animaZeroClipPreserved")) return;
    let owner = widget;
    let descriptor;
    while (owner && !(descriptor = Object.getOwnPropertyDescriptor(owner, "value"))) {
        owner = Object.getPrototypeOf(owner);
    }
    if (!descriptor?.get || !descriptor?.set || (owner === widget && !descriptor.configurable)) return;
    Object.defineProperty(widget, "value", {
        configurable: true,
        get() {
            const value = descriptor.get.call(this);
            return Array.isArray(value) ? value.map((entry) => ({
                ...entry, clipStrength: Number(entry.clipStrength ?? entry.strength),
            })) : value;
        },
        set(value) {
            descriptor.set.call(this, Array.isArray(value) ? value.map((entry) => ({
                ...entry, clipStrength: Number(entry.clipStrength) === 0 ? "0" : entry.clipStrength,
            })) : value);
        },
    });
    Object.defineProperty(widget, "__animaZeroClipPreserved", { value: true });
}
