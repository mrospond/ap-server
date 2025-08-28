# API Usage

NOTE:
* The app comes with SwaggerUI API documentation at `/docs` endpoint.
* To test the functioanlity you can use the `Makefile` in the project root. (change directory and run `make`)

## Simple example using curl
### 1. List Experiments
```
curl http://<IP>:8000/experiments
```

### 2. Build Experiment Image
```
curl -X POST "http://<IP>:8000/build"
-H "Content-Type: application/json"
-d '{"experiment_name":"analysing_pii_leakage"}'
```
- Streams Docker build logs in response.

### 3. Run Experiment
```
curl -X POST "http://<IP>:8000/run"
-H "Content-Type: application/json"
-d '{"experiment_name":"analysing_pii_leakage"}'
```
- Response: `{"container_id": "<docker_container_id>"}`

### 4. Remove Experiment Container
```
curl -X POST "http://<IP>:8000/remove"
-H "Content-Type: application/json"
-d '{"experiment_name":"analysing_pii_leakage"}'
```
- Response: `{"removed": "<container-name>"}`

### 5. Download Artifacts
```
curl -O http://<IP>:8000/artifacts/analysing_pii_leakage
```
- Downloads `analysing_pii_leakage-artifacts.zip`.
- The ZIP archive is created on request (not pre-existing).

## Logs and Monitoring

### Live Logs via Web UI
- From the webUI: select the experiment and click on `View Logs`

### Real-time Logs via WebSocket
- Connect to WebSocket URL `ws://<IP>:8000/ws/logs/container/<container_id>`
- Example in `../server/static/logs.html`