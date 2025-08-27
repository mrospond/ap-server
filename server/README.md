# Experiments

1. Install dependencies
```
python3 -m venv server
source server/bin/activate
pip3 install -r requirements.txt
```

1. Start the server
```
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

1. API guide: http://localhost:8000/docs