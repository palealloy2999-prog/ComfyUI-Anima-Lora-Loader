from .nodes.anima_lora_loader import AnimaLoraLoader

NODE_CLASS_MAPPINGS = {"AnimaLoraLoader": AnimaLoraLoader}
NODE_DISPLAY_NAME_MAPPINGS = {"AnimaLoraLoader": "ANIMA LoRA Loader"}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
