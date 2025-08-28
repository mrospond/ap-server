import os
from pathlib import Path
from models import Experiment
from typing import List

# Currently implemented params:
# name="test"                 # Name of the experiment; also the directory containing source code and Dockerfile
# ref="https://arxiv.org/abs/2205.12628"  # Reference publication for the experiment
# code="https://github.com/jeffhj/LM_PersonalInfoLeak"  # Reference to the original source code
# artifacts_path="results"    # Directory where result artifacts will be stored
# entrypoint=""               # Optional docker "--entrypoint" flag; depends on the implemented Dockerfile behavior

# Configs
EXPERIMENTS: List[Experiment] = [
    Experiment(
        name="analysing_pii_leakage",
        ref="https://arxiv.org/abs/2302.00539",
        code="https://github.com/microsoft/analysing_pii_leakage",
        entrypoint="hello.py hello world 123",
    ),
    Experiment(
        name="LM_PersonalInfoLeak",
        ref="https://arxiv.org/abs/2205.12628",
        code="https://github.com/jeffhj/LM_PersonalInfoLeak",
        entrypoint="main.py",
    ),
    Experiment(
        name="test",
        ref="https://arxiv.org/abs/2205.12628",
        code="https://github.com/jeffhj/LM_PersonalInfoLeak",
        artifacts_path="results",
        entrypoint="hello.py hello world 123",
    ),
]

EXPERIMENTS_PATH = Path(os.path.abspath("../experiments"))
