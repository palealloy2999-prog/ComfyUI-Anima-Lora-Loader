import sys
import unittest
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nodes.anima_remap import (  # noqa: E402
    NEW_BLOCKS_MODES,
    AnimaBlockMismatchError,
    build_block_mapping,
    find_block_indices,
    get_lora_block_count,
    get_model_block_count,
    load_manifest,
    remap_key,
    remap_lora,
)


def state(count, underscore=False):
    return {
        (
            f"lora_unet_net_blocks_{i}_q.lora_down.weight"
            if underscore
            else f"diffusion_model.net.blocks.{i}.q.lora_down.weight"
        ): torch.tensor([float(i)])
        for i in range(count)
    }


class RemapTests(unittest.TestCase):
    def test_native(self):
        for count in (28, 40, 52):
            sd = state(count)
            self.assertEqual(get_lora_block_count(sd), count)
            self.assertIs(remap_lora(sd, count, count), sd)

    def test_all_expansions_and_formats(self):
        for source, target in ((28, 40), (28, 52), (40, 52)):
            mapping = build_block_mapping(load_manifest(source, target))
            for underscore in (False, True):
                sd = state(source, underscore)
                result = remap_lora(sd, source, target)
                self.assertEqual(len(result), source)
                self.assertEqual(find_block_indices(result), set(mapping.values()))
                for key, tensor in sd.items():
                    self.assertIs(result[remap_key(key, mapping)], tensor)

    def test_composition(self):
        a = build_block_mapping(load_manifest(28, 40))
        b = build_block_mapping(load_manifest(40, 52))
        c = build_block_mapping(load_manifest(28, 52))
        self.assertEqual(c, {i: b[a[i]] for i in a})

    def test_copy(self):
        for source, target in ((28, 40), (28, 52), (40, 52)):
            sd = state(source)
            result = remap_lora(sd, source, target, NEW_BLOCKS_MODES[1])
            self.assertEqual(len(result), target)
            for inserted, old in load_manifest(source, target)["inserted_to_source"].items():
                self.assertIs(
                    result[f"diffusion_model.net.blocks.{inserted}.q.lora_down.weight"],
                    sd[f"diffusion_model.net.blocks.{old}.q.lora_down.weight"],
                )

    def test_blend_values_and_input_unchanged(self):
        sd = state(28)
        result = remap_lora(sd, 28, 40, NEW_BLOCKS_MODES[2])
        self.assertEqual(result["diffusion_model.net.blocks.2.q.lora_down.weight"].item(), 1.5)
        self.assertEqual(sd["diffusion_model.net.blocks.1.q.lora_down.weight"].item(), 1)
        self.assertEqual(len(sd), 28)

    def test_blend_one_missing_neighbor(self):
        sd = state(28)
        del sd["diffusion_model.net.blocks.2.q.lora_down.weight"]
        result = remap_lora(sd, 28, 40, NEW_BLOCKS_MODES[2])
        self.assertEqual(result["diffusion_model.net.blocks.2.q.lora_down.weight"].item(), 1)

    def test_blend_shape_failure(self):
        sd = state(28)
        sd["diffusion_model.net.blocks.2.q.lora_down.weight"] = torch.ones(2)
        with self.assertRaisesRegex(ValueError, "incompatible"):
            remap_lora(sd, 28, 40, NEW_BLOCKS_MODES[2])

    def test_exclusions_and_non_block_keys(self):
        keys = [
            "llm_adapter.blocks.99.x",
            "semantic_attentions.net.blocks.99.x",
            "connector_net_blocks_99_x",
            "other.blocks.27.x",
            "net.blocks.27.x",
        ]
        self.assertEqual(find_block_indices(keys), {27})
        mapping = {27: 51}
        for key in keys[:-1]:
            self.assertEqual(remap_key(key, mapping), key)
        sd = state(28) | {key: torch.ones(1) for key in keys[:3]} | {"final.weight": torch.ones(1)}
        result = remap_lora(sd, 28, 52)
        for key in keys[:3] + ["final.weight"]:
            self.assertIs(sd[key], result[key])

    def test_model_detection_is_stricter(self):
        class Model:
            def model_state_dict(self):
                return {
                    "diffusion_model.net.blocks.51.x": None,
                    "other.blocks.99.x": None,
                    "llm_adapter.net.blocks.999.x": None,
                }

        self.assertEqual(get_model_block_count(Model()), 52)

    def test_model_detection_prefers_diffusion_blocks(self):
        class DiffusionModel:
            blocks = [object()] * 40

            def state_dict(self):
                return {"blocks.0.weight": None}

        class ModelPatcher:
            model = type("Model", (), {"diffusion_model": DiffusionModel()})()

            def model_state_dict(self):
                return {"blocks.0.weight": None}

        self.assertEqual(get_model_block_count(ModelPatcher()), 40)

    def test_model_detection_falls_back_to_diffusion_state_dict(self):
        class DiffusionModel:
            def state_dict(self):
                return {f"blocks.{i}.weight": None for i in range(28)}

        model = type("ModelPatcher", (), {"model": type("Model", (), {"diffusion_model": DiffusionModel()})()})()
        self.assertEqual(get_model_block_count(model), 28)

    def test_block_detection_formats_and_exclusions(self):
        for count, prefix in ((28, "blocks"), (40, "diffusion_model.blocks"), (52, "model.diffusion_model.blocks")):
            keys = {f"{prefix}.{i}.weight": None for i in range(count)}
            self.assertEqual(get_model_block_count(type("Model", (), {"model_state_dict": lambda _: keys})()), count)
        for count, prefix in ((28, "lora_unet_blocks"), (40, "lora_unet_net_blocks")):
            keys = {f"{prefix}_{i}_weight": None for i in range(count)}
            self.assertEqual(get_lora_block_count(keys), count)
        self.assertEqual(get_lora_block_count({"llm_adapter.blocks.99.x": None, "blocks.27.x": None}), 28)

    def test_unknown_and_sparse(self):
        self.assertIsNone(get_lora_block_count({"final.weight": None}))
        self.assertEqual(get_lora_block_count({"net.blocks.4.x": None}), 5)

    def test_down_remap(self):
        for source, target in ((52, 40), (40, 28), (52, 28)):
            with self.assertRaises(AnimaBlockMismatchError):
                remap_lora(state(source), source, target)

    def test_invalid_manifest(self):
        manifest = load_manifest(28, 40)
        manifest["insertion_positions"].append(2)
        with self.assertRaises(ValueError):
            build_block_mapping(manifest)


if __name__ == "__main__":
    unittest.main()
