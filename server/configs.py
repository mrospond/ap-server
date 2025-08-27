# --- Implemented experiments ---
EXPERIMENTS = [
    {
        "experimentName": "analysing_pii_leakage",
        "ref": "https://arxiv.org/abs/2302.00539",
        "code": "https://github.com/microsoft/analysing_pii_leakage"
    },
    {
        "experimentName": "LM_PersonalInfoLeak",
        "ref": "https://arxiv.org/abs/2205.12628",
        "code": "https://github.com/jeffhj/LM_PersonalInfoLeak"
    }   
]

import os
EXPERIMENTS_PATH = os.path.abspath("..")