import test from "node:test";
import assert from "node:assert/strict";
import { mergeText, listText, connectWidgets, preserveZeroClip } from "../web/bridge.js";

test("search adds tags and updates duplicates while preserving inactive rows and order", () => {
    const rows = [{ name: "a.safetensors", active: false, strength: 1, clipStrength: 0.5, locked: true }];
    const result = mergeText("<lora:a:0.8:0> <lora:b:-1.2> <lora:b:0.7>", rows);
    assert.equal(result.length, 2);
    assert.deepEqual(result.map(x => x.name), ["a.safetensors", "b"]);
    assert.equal(result[0].active, false);
    assert.equal(result[0].clipStrength, 0);
    assert.equal(result[0].locked, true);
    assert.equal(result[1].strength, 0.7);
    assert.equal(rows[0].strength, 1);
});

test("list edits, reorder, deletion, toggle and differing CLIP strengths update text", () => {
    const rows = [
        { name: "a", active: true, strength: 1.2, clipStrength: 0 },
        { name: "b", active: true, strength: 0.7, clipStrength: 0.7 },
    ];
    assert.equal(listText(rows), "<lora:a:1.2:0> <lora:b:0.7>");
    assert.equal(listText(rows.toReversed()), "<lora:b:0.7> <lora:a:1.2:0>");
    rows[0].active = false;
    assert.equal(listText(rows), "<lora:b:0.7>");
    assert.equal(listText(rows.slice(0, 1)), "");
});

test("callbacks are guarded and passive restoration keeps saved values", () => {
    let value = [];
    const text = { name: "text", value: "" };
    const loras = { name: "loras", get value() { return value; }, set value(v) { value = v; this.callback?.(v); } };
    const node = { widgets: [text, loras, { name: "new_blocks_mode", value: "Original Blocks Only" }] };
    connectWidgets(node);
    text.callback("<lora:a:1:0>");
    assert.equal(loras.value.length, 1);
    const saved = ["", [{ name: "a", active: false, strength: 0.6, clipStrength: 0 }], "Copy To New Blocks"];
    node.widgets.forEach((widget, index) => { widget.value = structuredClone(saved[index]); });
    const before = structuredClone(loras.value);
    connectWidgets(node);
    assert.deepEqual(loras.value, before);
    assert.equal(loras.value[0].active, false);
    assert.equal(loras.value[0].clipStrength, 0);
});

test("Manager truthy-default workaround preserves numeric zero on roundtrip", () => {
    let rows = [];
    const widget = {
        get value() { return rows; },
        set value(v) { rows = v.map(x => ({ ...x, clipStrength: x.clipStrength || x.strength })); },
    };
    preserveZeroClip(widget);
    widget.value = [{ name: "a", active: false, strength: 0.8, clipStrength: 0 }];
    assert.equal(widget.value[0].clipStrength, 0);
    const saved = JSON.parse(JSON.stringify(widget.value));
    widget.value = saved;
    assert.equal(widget.value[0].clipStrength, 0);
    assert.equal(widget.value[0].active, false);
});

test("Manager DOM widgets with non-configurable value accessors do not throw", () => {
    let rows = [];
    const widget = {};
    Object.defineProperty(widget, "value", {
        configurable: false,
        get() { return rows; },
        set(value) { rows = value; },
    });
    assert.doesNotThrow(() => preserveZeroClip(widget));
    widget.value = [{ name: "a", clipStrength: 0 }];
    assert.equal(widget.value[0].clipStrength, 0);
});
