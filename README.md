# ANIMA LoRA Loader

[日本語版 README](README.ja.md)

Requires ComfyUI and [ComfyUI-Lora-Manager](https://github.com/willmiao/ComfyUI-Lora-Manager).
Place this folder in `ComfyUI/custom_nodes`, restart ComfyUI, and reload the browser.
Add **ANIMA LoRA Loader** from `loaders/anima`, connect MODEL and optionally CLIP,
then search/add LoRAs. The list controls activation, strengths, order and preview.

The loader detects 28/40/52 blocks for each LoRA independently. It remaps 28→40,
28→52 and 40→52 in memory; a larger LoRA on a smaller model raises an error.
No converted LoRA files or disk caches are created. Python uses the `loras` list
only; `text` is for search synchronization. Removing tags does not remove entries:
use the list's delete control. Inactive rows stay in the list when other LoRAs are added.

`Original Blocks Only` is the default. `Copy To New Blocks` copies the original
source block's tensors to inserted blocks. `Blend Neighbor Blocks` averages
neighboring original blocks' corresponding tensors (one available tensor: 100%).
Blend averages the LoRA factors themselves, **not** the composed LoRA delta;
copy/blend are experimental, and incompatible neighbor shapes stop with an error.

Outputs: MODEL, CLIP (None when disconnected), trigger_words, loaded_loras, and
remap_info. `trigger_words` reads the trigger-word metadata from LoRA Manager for
each active LoRA, preserving list order, and joins the words with `,, `. Missing
metadata or a metadata lookup failure is ignored so loading continues. Unknown
LoRA counts warn and apply as-is; unknown MODEL counts stop. Detection uses the
largest stored block index plus one. Sparse LoRAs can therefore be misidentified,
including a known but incorrect generation; v1 has no manual override. Duplicate
basenames require folder-qualified names.

## Compatibility and mapping provenance

The UI reuses Manager's autocomplete and exported list widget without copying its
implementation or importing its Python modules. A frontend-only widget alias
creates the list synchronously to preserve `text, loras, new_blocks_mode` order.
The bridge preserves numeric zero CLIP strength despite the tested Manager's
truthy-default setter. The backend uses the specified V1 node contract.

Reference mapping files come from [ComfyUI-Anima-Remap](https://github.com/shin131002/ComfyUI-Anima-Remap)
at `3f9bb6ea56c52ae4ff559bc2490113c3b281751a`; its notice is in
`mapping/UPSTREAM-LICENSE.txt`. 40→52 is reconstructed by the upstream project,
not an official expansion manifest. 28→52 is composed from 28→40 and 40→52.
Their provenance fields are retained. Manager inspected at
`ee71d5c4993f29086b27fde1629a945ae48425bf`. Widget export changes may require updating
the small bridge. Manager's hard-coded external "send to loader" integration
does not recognize this node; use its search widget to add LoRAs.

## install

```
cd custum_nodes
git clone https://github.com/palealloy2999-prog/ComfyUI-Anima-Lora-Loader
```

