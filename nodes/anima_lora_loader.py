import logging
import math
from pathlib import PurePosixPath

import comfy.sd
import comfy.utils
import folder_paths

from .anima_remap import (
    ANIMA_GENERATIONS,
    NEW_BLOCKS_MODES,
    AnimaBlockMismatchError,
    get_lora_block_count,
    get_model_block_count,
    remap_lora,
)

logger = logging.getLogger(__name__)


def resolve_lora_path(name):
    """Resolve only registered files; ambiguous basenames require a folder."""
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
        raise ValueError(f"Invalid LoRA name: {name}")
    names = folder_paths.get_filename_list("loras")
    exact = [n for n in names if n.replace("\\", "/") == normalized]
    matches = exact or [n for n in names if str(PurePosixPath(n.replace("\\", "/")).with_suffix("")) == normalized]
    if not matches and "/" not in normalized:
        matches = [
            n
            for n in names
            if normalized
            in (
                PurePosixPath(n.replace("\\", "/")).name,
                PurePosixPath(n.replace("\\", "/")).stem,
            )
        ]
    if not matches:
        logger.warning("[ANIMA LoRA] LoRA file missing: %s", name)
        raise FileNotFoundError(f'LoRA "{name}" was not found in ComfyUI loras folders.')
    if len(matches) != 1:
        raise ValueError(f'Ambiguous LoRA "{name}"; use the folder-qualified filename: {matches}')
    path = folder_paths.get_full_path("loras", matches[0])
    if path is None:
        logger.warning("[ANIMA LoRA] LoRA file missing: %s", name)
        raise FileNotFoundError(name)
    return path


class AnimaLoraLoader:
    # V1 is intentional: the requested interface and LoRA Manager custom widgets.
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "text": (
                    "AUTOCOMPLETE_TEXT_LORAS",
                    {
                        "placeholder": "Search LoRAs to add...",
                        "tooltip": "Search and add LoRAs",
                    },
                ),
                "loras": ("LORAS", {}),
                "new_blocks_mode": (list(NEW_BLOCKS_MODES), {"default": NEW_BLOCKS_MODES[0]}),
            },
            "optional": {"clip": ("CLIP",)},
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("MODEL", "CLIP", "trigger_words", "loaded_loras", "remap_info")
    FUNCTION = "load_loras"
    CATEGORY = "loaders/anima"

    def load_loras(self, model, text, loras, new_blocks_mode=NEW_BLOCKS_MODES[0], clip=None):
        if new_blocks_mode not in NEW_BLOCKS_MODES:
            raise ValueError(f"Unknown new_blocks_mode: {new_blocks_mode}")
        target = get_model_block_count(model)
        if target not in ANIMA_GENERATIONS:
            logger.warning("[ANIMA LoRA] Unsupported MODEL block count: %s", target)
            raise RuntimeError(f"Detected model block count: {target}. Unsupported ANIMA generation.")
        logger.info("[ANIMA LoRA] Model generation: %s blocks", target)
        if not isinstance(loras, list):
            raise ValueError("loras must be a LoRA Manager array")
        loaded, info = [], []
        for entry in loras:
            if not isinstance(entry, dict):
                raise ValueError("Each LoRA entry must be an object")
            if not entry.get("active", False):
                continue
            name = entry["name"]
            strength = float(entry.get("strength", 1.0))
            clip_strength = float(entry.get("clipStrength", strength))
            if not math.isfinite(strength) or not math.isfinite(clip_strength):
                raise ValueError(f"Non-finite LoRA strength: {name}")
            sd = comfy.utils.load_torch_file(resolve_lora_path(name), safe_load=True)
            source = get_lora_block_count(sd)
            if source is not None and source > target:
                raise AnimaBlockMismatchError(
                    f'LoRA "{name}" uses {source} blocks, but connected model has only '
                    f"{target} blocks. Down-remapping is not supported."
                )
            target_label = f"{ANIMA_GENERATIONS[target]} {target}"
            if source not in ANIMA_GENERATIONS:
                logger.warning(
                    '[ANIMA LoRA] Could not determine ANIMA generation for "%s" (block count: %s). '
                    "LoRA will be applied without remapping.",
                    name,
                    source,
                )
                action = f"unknown source ({source}) -> {target_label} [as-is, generation undetermined]"
            elif source == target:
                action = f"{target_label} [native]"
            else:
                sd = remap_lora(sd, source, target, new_blocks_mode)
                mode_label = {
                    NEW_BLOCKS_MODES[0]: "",
                    NEW_BLOCKS_MODES[1]: ", copy new blocks",
                    NEW_BLOCKS_MODES[2]: ", neighbor blend",
                }[new_blocks_mode]
                action = f"{ANIMA_GENERATIONS[source]} {source} -> {target_label} [remapped{mode_label}]"
            logger.info("[ANIMA LoRA] %s: %s; strength model=%s clip=%s", name, action, strength, clip_strength)
            model, clip = comfy.sd.load_lora_for_models(model, clip, sd, strength, clip_strength)
            tag_path = PurePosixPath(name.replace("\\", "/"))
            tag_name = (
                str(tag_path.with_suffix(""))
                if tag_path.suffix.lower()
                in {
                    ".safetensors",
                    ".pt",
                    ".pt2",
                    ".pth",
                    ".ckpt",
                    ".bin",
                    ".pkl",
                    ".sft",
                }
                else str(tag_path)
            )
            weights = f"{strength:g}" if strength == clip_strength else f"{strength:g}:{clip_strength:g}"
            loaded.append(f"<lora:{tag_name}:{weights}>")
            info.append(f"{name}: {action}")
        return model, clip, "", " ".join(loaded), "\n".join(info)
