from pydantic import BaseModel

# Models
class Experiment(BaseModel):
    name: str
    ref: str
    code: str
    entrypoint: str = ""
    artifacts_path: str = ""

class NameRequest(BaseModel):
    experiment_name: str
