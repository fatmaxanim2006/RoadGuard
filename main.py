from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg2.extras import Json
from ultralytics import YOLO
from PIL import Image
import numpy as np
import psycopg2
import io
import os
import base64

app = FastAPI()

model = YOLO("best.pt")

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


@app.on_event("startup")
def create_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            damage_type VARCHAR(50),
            confidence FLOAT,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            image VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS detection_count INT DEFAULT 1")
    cur.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS detections JSONB")
    conn.commit()
    cur.close()
    conn.close()




class DetectionIn(BaseModel):
    damage_type: str
    confidence: float
    bbox: Optional[dict] = None


class ReportIn(BaseModel):
    image: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    detections: List[DetectionIn]




def summarize(detections):
    """Return (dominant_type, best_confidence, count) for a list of detection dicts."""
    stats = {}
    for d in detections:
        s = stats.setdefault(d["damage_type"], {"count": 0, "max_conf": 0.0})
        s["count"] += 1
        s["max_conf"] = max(s["max_conf"], d["confidence"])
    dominant = max(stats, key=lambda k: (stats[k]["count"], stats[k]["max_conf"]))
    return dominant, stats[dominant]["max_conf"], len(detections)


def insert_report(cur, image, latitude, longitude, detections):
    dominant, conf, count = summarize(detections)
    cur.execute(
        """
        INSERT INTO reports
            (damage_type, confidence, latitude, longitude, image, detection_count, detections)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (dominant, conf, latitude, longitude, image, count, Json(detections)),
    )
    return cur.fetchone()[0], dominant, count




@app.api_route("/", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "service": "RoadGuard API"}


@app.get("/reports")
def get_reports():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, damage_type, confidence, latitude, longitude, image, created_at,
               detection_count, detections
        FROM reports
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for r in rows:
        detections = r[8] or [{"damage_type": r[1], "confidence": r[2]}]
        result.append({
            "id": r[0],
            "damage_type": r[1],
            "confidence": r[2],
            "latitude": r[3],
            "longitude": r[4],
            "image": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
            "detection_count": r[7] or 1,
            "detections": detections,
        })
    return result


@app.post("/reports")
def create_report(report: ReportIn):
    """One image = one report. Called by the 'Save to map' button."""
    if not report.detections:
        raise HTTPException(status_code=400, detail="No detections to save.")

    detections = [
        {
            "damage_type": d.damage_type,
            "confidence": round(d.confidence, 4),
            "bbox": d.bbox,
        }
        for d in report.detections
    ]

    conn = get_conn()
    cur = conn.cursor()
    report_id, dominant, count = insert_report(
        cur, report.image, report.latitude, report.longitude, detections
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"id": report_id, "damage_type": dominant, "detection_count": count}


@app.post("/detect")
async def detect(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    conf: float = Form(0.25),
    save: bool = Form(False),
):
    contents = await file.read()
    try:
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file.")

    results = model.predict(np.array(img), conf=conf, iou=0.5, agnostic_nms=True)[0]

    detections = []
    for box in results.boxes:
        name = model.names[int(box.cls)]
        score = float(box.conf)
        x1, y1, x2, y2 = [round(v, 1) for v in box.xyxy[0].tolist()]
        detections.append({
            "damage_type": name,
            "confidence": round(score, 4),
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        })

    saved_id = None
    if save and detections:
        conn = get_conn()
        cur = conn.cursor()
        saved_id, _, _ = insert_report(cur, file.filename, latitude, longitude, detections)
        conn.commit()
        cur.close()
        conn.close()


    annotated = results.plot()[:, :, ::-1]  
    annotated_img = Image.fromarray(annotated)
    buffer = io.BytesIO()
    annotated_img.save(buffer, format="JPEG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "filename": file.filename,
        "detections_count": len(detections),
        "detections": detections,
        "saved_report_id": saved_id,
        "annotated_image": img_base64,
    }
