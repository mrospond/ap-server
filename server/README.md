# Experiments

1. Install dependencies
```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

2. Start the server
```
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
3. Fix missing pip module
```
pip install <missing module>
```

4. API guide: http://localhost:8000/docs