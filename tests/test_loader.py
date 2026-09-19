import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Model:
    def __init__(self, count=52):
        self.count = count

    def model_state_dict(self):
        return {f"diffusion_model.net.blocks.{self.count - 1}.weight": None}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.comfy = types.ModuleType("comfy")
        self.comfy.sd = types.ModuleType("comfy.sd")
        self.comfy.utils = types.ModuleType("comfy.utils")
        self.comfy.sd.load_lora_for_models = Mock(side_effect=lambda m, c, *_: (m, c))
        self.comfy.utils.load_torch_file = Mock(
            side_effect=lambda path, **_: {
                f"net.blocks.{int(path.split('/')[-1].split('.')[0]) - 1}.x": torch.ones(1),
            }
        )
        self.folders = types.ModuleType("folder_paths")
        self.folders.get_filename_list = Mock(return_value=["28.safetensors", "40.safetensors", "52.safetensors"])
        self.folders.get_full_path = Mock(side_effect=lambda _, name: "/loras/" + name)
        self.modules = patch.dict(
            sys.modules,
            {
                "comfy": self.comfy,
                "comfy.sd": self.comfy.sd,
                "comfy.utils": self.comfy.utils,
                "folder_paths": self.folders,
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        sys.modules.pop("nodes.anima_lora_loader", None)
        self.module = importlib.import_module("nodes.anima_lora_loader")
        self.node = self.module.AnimaLoraLoader()

    def entry(self, count, **kwargs):
        return {"name": str(count), "active": True, "strength": 0.8, "clipStrength": 0.0, **kwargs}

    def register_manager(self, get_info, format_name=lambda name: name):
        manager = types.ModuleType("test_lora_manager")
        manager.get_lora_info_absolute = get_info
        manager.apply_lora_syntax_format = format_name
        loader_class = type("LoraLoaderLM", (), {"__module__": manager.__name__})
        sys.modules[manager.__name__] = manager
        self.addCleanup(sys.modules.pop, manager.__name__, None)
        sys.modules["nodes"].NODE_CLASS_MAPPINGS = {"Lora Loader (LoraManager)": loader_class}

    def test_trigger_words_match_manager_format_and_order(self):
        calls = []
        self.folders.get_filename_list.return_value = ["folder/28.safetensors", "40.safetensors"]

        def get_info(name):
            calls.append(name)
            return "/absolute/" + name, {"28": ["foo", "bar"], "40": ["baz"]}[name]

        self.register_manager(get_info, lambda name: name.rsplit("/", 1)[-1].removesuffix(".safetensors"))
        result = self.node.load_loras(Model(), "", [
            self.entry("folder/28.safetensors"),
            self.entry("40.safetensors"),
        ])
        self.assertEqual(result[2], "foo,, bar,, baz")
        self.assertEqual(calls, ["28", "40"])

    def test_trigger_words_ignore_inactive_and_missing_metadata(self):
        self.register_manager(lambda name: ("/absolute/" + name, []))
        result = self.node.load_loras(Model(), "", [self.entry(28, active=False), self.entry(40)])
        self.assertEqual(result[2], "")

    def test_trigger_words_failure_does_not_stop_loading(self):
        def get_info(_name):
            raise RuntimeError("metadata unavailable")

        self.register_manager(get_info)
        result = self.node.load_loras(Model(), "", [self.entry(28)])
        self.assertEqual(result[2], "")
        self.assertEqual(self.comfy.sd.load_lora_for_models.call_count, 1)

    def test_mixed_order_optional_clip_zero_strength(self):
        result = self.node.load_loras(Model(), "<lora:ignored:1>", [self.entry(i) for i in (28, 40, 52)])
        self.assertEqual(len(result), 5)
        self.assertIsNone(result[1])
        self.assertEqual(result[2], "")
        self.assertEqual(result[3], "<lora:28:0.8:0> <lora:40:0.8:0> <lora:52:0.8:0>")
        self.assertIn("[native]", result[4])
        self.assertEqual(self.comfy.sd.load_lora_for_models.call_count, 3)
        for call in self.comfy.sd.load_lora_for_models.call_args_list:
            self.assertEqual(call.args[4], 0)
            self.assertIn("net.blocks.51.x", call.args[2])

    def test_native_and_all_remap_pairs(self):
        for source, target in ((28, 28), (40, 40), (52, 52), (28, 40), (28, 52), (40, 52)):
            clip = object()
            result = self.node.load_loras(Model(target), "", [self.entry(source)], clip=clip)
            self.assertIs(result[1], clip)
            self.assertIn("native" if source == target else "remapped", result[4])

    def test_inactive_and_empty(self):
        model = Model()
        for entries in ([], [self.entry("missing", active=False)]):
            self.assertEqual(self.node.load_loras(model, "", entries), (model, None, "", "", ""))
        self.comfy.utils.load_torch_file.assert_not_called()

    def test_down_remap_never_applied(self):
        for source, target in ((52, 40), (40, 28)):
            with self.assertRaisesRegex(self.module.AnimaBlockMismatchError, "Down-remapping"):
                self.node.load_loras(Model(target), "", [self.entry(source)])
        self.comfy.sd.load_lora_for_models.assert_not_called()

    def test_unknown_model_stops(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            self.node.load_loras(Model(64), "", [self.entry(28)])
        self.comfy.utils.load_torch_file.assert_not_called()

    def test_unknown_lora_warns_and_applies_as_is(self):
        sd = {"final.weight": torch.ones(1)}
        self.comfy.utils.load_torch_file.side_effect = None
        self.comfy.utils.load_torch_file.return_value = sd
        with self.assertLogs(self.module.logger, level="WARNING"):
            result = self.node.load_loras(Model(), "", [self.entry(28)])
        self.assertIn("as-is", result[4])
        self.assertIs(self.comfy.sd.load_lora_for_models.call_args.args[2], sd)

    def test_paths(self):
        self.folders.get_filename_list.return_value = ["folder/foo.safetensors"]
        for name in ("foo", "foo.safetensors", "folder/foo", "folder/foo.safetensors", "folder\\foo.safetensors"):
            self.assertEqual(self.module.resolve_lora_path(name), "/loras/folder/foo.safetensors")
        self.folders.get_filename_list.return_value.append("other/foo.safetensors")
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.module.resolve_lora_path("foo")
        for name in ("../foo", "C:\\foo", "/foo"):
            with self.assertRaises(ValueError):
                self.module.resolve_lora_path(name)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            self.module.resolve_lora_path("missing")

    def test_schema(self):
        schema = self.node.INPUT_TYPES()
        self.assertEqual(list(schema["required"]), ["model", "text", "loras", "new_blocks_mode"])
        self.assertEqual(self.node.RETURN_TYPES, ("MODEL", "CLIP", "STRING", "STRING", "STRING"))


if __name__ == "__main__":
    unittest.main()
