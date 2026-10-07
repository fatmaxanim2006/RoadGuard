# 🚧 RoadGuard
**AI-Powered Road Damage Detection Platform**

*Detect. Report. Map.*

RoadGuard detects road damage (potholes and cracks) from road images using a YOLO object detection model. For each detection it returns the damage class, a bounding box and a confidence score. Results are stored in a PostgreSQL database via a FastAPI backend, and the whole system is deployed online.

## 🌐 Live Demo
- **Web app (Streamlit):** https://roadguard-cc5k5u5urn2ozumwrk53qy.streamlit.app/
- **API docs (Swagger UI):** https://roadguard-api-fcfs.onrender.com/docs

> The backend runs on a free Render plan and goes to sleep after 15 minutes of inactivity. The first request after a pause can take up to a minute.

## Project Status
- **Sprint 1 (25%)** — ✅ Complete: working prototype (Streamlit + YOLO)
- **Sprint 2 (50%)** — ✅ Complete: backend API + database integration
- **Sprint 3 (65%)** — ✅ Complete: full system deployed online (Render + Streamlit Community Cloud)

## Architecture
```
[Streamlit frontend]  --HTTP POST-->  [FastAPI backend] --> YOLO model
 (Streamlit Cloud)                      (Render)
                                            |
                                            v
                                  [PostgreSQL database]
                                       (Render)
```
- **Frontend (`frontend/app.py`)**: Streamlit app. The user uploads an image, sets a confidence threshold and optional coordinates, then sees the annotated image with each detection's class, confidence and bounding box.
- **Backend (`main.py`)**: FastAPI app. Runs YOLO inference, draws bounding boxes, saves each detection to PostgreSQL and returns the results (including the annotated image) as JSON.
- **Database**: PostgreSQL, `reports` table (created automatically on backend startup).

## Deployment
| Component | Platform |
|-----------|----------|
| FastAPI backend + YOLO model | Render (Web Service, free plan) |
| PostgreSQL database | Render (PostgreSQL, free plan) |
| Streamlit frontend | Streamlit Community Cloud |

- The backend reads the database connection from the `DATABASE_URL` environment variable (no credentials in the code).
- Render settings: Python 3.11.9, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- The backend `requirements.txt` uses CPU-only PyTorch to fit the free plan's 512 MB RAM. The frontend has its own lightweight `frontend/requirements.txt`.

## Model
- Architecture: YOLO11n (Ultralytics)
- Dataset: "crack and pothole" (Roboflow Universe, CC BY 4.0), classes: `crack`, `pothole`
- 3,653 original images; the exported version (with augmentation) has 11,340 images (10,244 train / 731 validation)
- Training: 25 epochs, image size 640, Google Colab (Tesla T4), about 1.2 hours

### Results (validation set)
| Class | Precision | Recall | mAP50 |
|-------|-----------|--------|-------|
| all | 0.851 | 0.748 | 0.815 |
| crack | 0.874 | 0.859 | 0.902 |
| pothole | 0.828 | 0.636 | 0.728 |

Inference speed: about 11 ms per image on a T4 GPU.

## Database Schema
Table `reports`:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PRIMARY KEY | Auto-incrementing ID |
| damage_type | VARCHAR(50) | "crack" or "pothole" |
| confidence | FLOAT | Model confidence score |
| latitude | DOUBLE PRECISION | Location (optional) |
| longitude | DOUBLE PRECISION | Location (optional) |
| image | VARCHAR(255) | Original filename |
| created_at | TIMESTAMP | Auto-set on insert |

## API
### `GET /`
Health check. Returns `{"status": "ok", "service": "RoadGuard API"}`.

### `POST /detect`
Accepts a road image, runs detection, saves results to the database and returns the annotated image plus detection details.

**Request (multipart/form-data):**
- `file`: image file (jpg/jpeg/png)
- `conf`: confidence threshold (float, default 0.25)
- `latitude`, `longitude`: optional location (float)

**Response (JSON):**
```json
{
  "filename": "pothole.jpg",
  "detections_count": 1,
  "detections": [
    {
      "damage_type": "pothole",
      "confidence": 0.8676,
      "bbox": {"x1": 105.2, "y1": 262.8, "x2": 563.4, "y2": 498.1}
    }
  ],
  "annotated_image": "<base64-encoded JPEG>"
}
```
`bbox` values are pixel coordinates: (x1, y1) is the top-left and (x2, y2) the bottom-right corner of the box.

### `GET /reports`
Returns all saved reports (newest first) as a JSON list. This endpoint will feed the interactive map.

Interactive API docs are available at `/docs` (Swagger UI).

## Demo
![Single pothole](screenshots/pothole_single.png)
![Multiple potholes](screenshots/pothole_multiple.png)
![Crack](screenshots/crack_example.png)

Pothole examples are images taken from the web. Crack examples come from the dataset.

## Limitations
- The model works best on close-up photos of asphalt roads.
- Accuracy drops on gravel or unpaved roads, wide street views with thin cracks, and low-quality images.
- Pothole recall (0.636) is lower than crack recall; more pothole data is planned.
- The same damage can sometimes be detected twice with overlapping boxes.
- Location (latitude/longitude) is optional and entered manually; the map view is not implemented yet.
- Free hosting limits: the backend sleeps after inactivity (slow first request), and the free Render database is time-limited.

## How to run locally
1. Install Python 3.11+
2. Install backend dependencies: `pip install -r requirements.txt`
3. Install PostgreSQL (or use any PostgreSQL instance) and create a database.
4. Set the connection string as an environment variable (Windows CMD):
```
   set DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/roadguard
```
   The `reports` table is created automatically on startup.
5. Make sure `best.pt` and `main.py` are in the same folder, then start the backend:
```
   uvicorn main:app --reload
```
6. Install frontend dependencies and start the frontend (set `API_URL` in `frontend/app.py` to `http://127.0.0.1:8000/detect` for local use):
```
   pip install -r frontend/requirements.txt
   streamlit run frontend/app.py
```
7. Open http://localhost:8501 in your browser.

## Next Sprint
- Interactive map (Folium/Leaflet) showing all reported damage, using `GET /reports`
- Improve pothole recall (more data / epochs / augmentation)
- Deduplication of overlapping detections
- Error handling and UI polish
