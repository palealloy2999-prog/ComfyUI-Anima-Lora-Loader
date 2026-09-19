"""In-memory block remapping. No ComfyUI or frontend imports."""

import json
import logging
import re
from pathlib import Path

ANIMA_GENERATIONS = {28: "ANIMA", 40: "ANIMA 2.9B", 52: "ANIMA 3.8B"}
NEW_BLOCKS_MODES = (
    "Original Blocks Only",
    "Copy To New Blocks",
    "Blend Neighbor Blocks",
)
_EXCLUDED = ("llm_adapter", "semantic_attentions", "connector")
_DETECTION = re.compile(
    r"^(?:blocks|diffusion_model\.blocks|model\.diffusion_model\.blocks|net\.blocks|diffusion_model\.net\.blocks)\."
    r"(\d+)(?=\.|$)|^lora_unet_(?:net_)?blocks_(\d+)(?=_|$)"
)
_MAIN = _DETECTION
_MAPPING_DIR = Path(__file__).resolve().parent.parent / "mapping"
logger = logging.getLogger(__name__)


class AnimaBlockMismatchError(RuntimeError):
    """A larger-generation LoRA cannot be applied to a smaller model."""


def _match(key, pattern):
    return None if any(part in key for part in _EXCLUDED) else pattern.search(key)


def find_block_indices(keys):
    return {int(m[1] or m[2]) for key in keys if (m := _match(key, _DETECTION))}


def get_model_block_count(model):
    diffusion_model = getattr(getattr(model, "model", None), "diffusion_model", None)
    blocks = getattr(diffusion_model, "blocks", None)
    if blocks is not None:
        try:
            count = len(blocks)
        except TypeError:
            count = None
        if count is not None:
            logger.debug("[ANIMA LoRA] diffusion model class: %s", type(diffusion_model).__name__)
            logger.debug("[ANIMA LoRA] detected blocks: %s", count)
            return count

    state_dict_method = getattr(diffusion_model, "state_dict", None)
    if callable(state_dict_method):
        state_dict = state_dict_method()
    else:
        state_dict = getattr(model, "model_state_dict", lambda: {})()
    indices = {int(m[1] or m[2]) for key in state_dict if (m := _match(key, _MAIN))}
    count = max(indices) + 1 if indices else None
    logger.debug("[ANIMA LoRA] diffusion model class: %s", type(diffusion_model).__name__)
    logger.debug("[ANIMA LoRA] detected blocks: %s", count)
    return count


def get_lora_block_count(lora_sd):
    indices = find_block_indices(lora_sd)
    return max(indices) + 1 if indices else None


def build_block_mapping(manifest):
    old, new = manifest["old_block_count"], manifest["new_block_count"]
    positions = manifest["insertion_positions"]
    if (
        not isinstance(old, int)
        or not isinstance(new, int)
        or not 0 < old < new
        or any(type(i) is not int or not 0 <= i < new for i in positions)
        or len(set(positions)) != len(positions)
        or len(positions) != new - old
    ):
        raise ValueError("Invalid ANIMA expansion manifest")
    inserted = set(positions)
    mapping = dict(enumerate(i for i in range(new) if i not in inserted))
    sources = {int(k): v for k, v in manifest["inserted_to_source"].items()}
    if set(sources) != inserted or any(type(v) is not int or not 0 <= v < old for v in sources.values()):
        raise ValueError("Invalid inserted_to_source in ANIMA manifest")
    return mapping


def load_manifest(source_blocks, target_blocks):
    if source_blocks not in ANIMA_GENERATIONS or target_blocks not in ANIMA_GENERATIONS:
        raise ValueError("Unsupported ANIMA manifest pair")
    path = _MAPPING_DIR / f"expand_manifest_{source_blocks}_{target_blocks}.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("[ANIMA LoRA] manifest missing: %s", path.name)
        raise
    if (manifest["old_block_count"], manifest["new_block_count"]) != (source_blocks, target_blocks):
        raise ValueError(f"Wrong block counts in {path.name}")
    build_block_mapping(manifest)
    return manifest


def remap_key(key, block_mapping):
    match = _match(key, _MAIN)
    if not match:
        return key
    source = int(match[1] or match[2])
    index_start, index_end = (match.span(1) if match[1] else match.span(2))
    if source not in block_mapping:
        raise ValueError(f"Block {source} has no mapping: {key}")
    return key[:index_start] + str(block_mapping[source]) + key[index_end:]


def remap_lora(lora_sd, source_blocks, target_blocks, new_blocks_mode=NEW_BLOCKS_MODES[0]):
    if new_blocks_mode not in NEW_BLOCKS_MODES:
        raise ValueError(f"Unknown new_blocks_mode: {new_blocks_mode}")
    if source_blocks > target_blocks:
        raise AnimaBlockMismatchError("Down-remapping is not supported.")
    if source_blocks == target_blocks:
        return lora_sd
    manifest = load_manifest(source_blocks, target_blocks)
    mapping = build_block_mapping(manifest)
    result = {}
    blocks = {}
    for key, tensor in lora_sd.items():
        result[remap_key(key, mapping)] = tensor
        match = _match(key, _MAIN)
        if match:
            # Templates keep the prefix/parameter suffix, pairing like tensors only.
            index_start, index_end = (match.span(1) if match[1] else match.span(2))
            template = (key[:index_start], key[index_end:])
            blocks.setdefault(int(match[1] or match[2]), {})[template] = tensor
    if new_blocks_mode == NEW_BLOCKS_MODES[0]:
        return result
    for inserted in manifest["insertion_positions"]:
        if new_blocks_mode == NEW_BLOCKS_MODES[1]:
            values = blocks.get(manifest["inserted_to_source"][str(inserted)], {})
        else:
            before = [old for old, new in mapping.items() if new < inserted]
            after = [old for old, new in mapping.items() if new > inserted]
            left = blocks.get(before[-1], {}) if before else {}
            right = blocks.get(after[0], {}) if after else {}
            values = {}
            for template in left.keys() | right.keys():
                a, b = left.get(template), right.get(template)
                if a is None or b is None:
                    values[template] = b if a is None else a
                else:
                    if a.shape != b.shape or a.dtype != b.dtype or a.device != b.device:
                        raise ValueError("Neighbor LoRA tensors cannot be blended: incompatible shape/dtype/device")
                    values[template] = a * 0.5 + b * 0.5
        for (prefix, suffix), tensor in values.items():
            result[f"{prefix}{inserted}{suffix}"] = tensor
    return result
