import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { connectWidgets, preserveZeroClip } from "./bridge.js";

const TYPE = "AnimaLoraLoader";
const WIDGET = "ANIMA_MANAGER_LORAS";
let synchronization

app.registerExtension({
    name: "AnimaLoraLoader.ManagerBridge",
    async getCustomWidgets() {
        let factory;
        try {
            const response = await api.fetchApi("/extensions");
            if (!response.ok) throw new Error(`Extensions request failed: ${response.status}`);
            const extensions = await response.json();
            const path = extensions.find((url) => /\/[^/]*lora.manager[^/]*\/.*loras_widget\.js$/i.test(url));
            if (!path) throw new Error("ComfyUI-Lora-Manager's loras_widget.js was not found.");
            ({ addLorasWidget: factory } = await import(path));
            const [{ mergeLoras }, { applyLoraValuesToText }] = await Promise.all([
              import(path.replace(/loras_widget\.js$/i, 'utils.js')),
              import(path.replace(/loras_widget\.js$/i, 'lora_syntax_utils.js')),
            ])
            synchronization = { mergeLoras, applyLoraValuesToText }
        } catch (error) {
            console.error("[ANIMA LoRA] Install/enable ComfyUI-Lora-Manager and reload.", error);
        }
        return {
            [WIDGET](node, name) {
                if (!factory) throw new Error("ANIMA LoRA Loader requires ComfyUI-Lora-Manager. Enable it and reload.");
                const result = factory(node, name, {}, null);
                preserveZeroClip(result.widget);
                return result;
            },
        };
    },
    beforeRegisterNodeDef(_nodeType, nodeData) {
        if (nodeData.name !== TYPE) return;
        // A local frontend alias makes Manager's exported factory synchronous.
        // Its registered LORAS factory is async in the tested version, which can
        // append the list after configure() and break positional restoration.
        // The backend API still declares LORAS; no other node is modified.
        nodeData.input.required.loras[0] = WIDGET;
    },
    nodeCreated(node) {
        if (node.comfyClass === TYPE) connectWidgets(node, synchronization)
    },
    loadedGraphNode(node) {
        if (node.comfyClass === TYPE) connectWidgets(node, synchronization)
    },
});
