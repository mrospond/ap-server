from dataclasses import dataclass


@dataclass
class LocalConfigs:
    cache_dir: str = "./.cache"
    imagenet_root: str = ""