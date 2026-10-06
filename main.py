from fastapi import FastAPI, File, UploadFile, Form
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
    conn.commit()
    cur.close()
    conn.close()


@app.get("/")
def health():
    return {"status": "ok", "service": "RoadGuard API"}


@app.get("/reports")
def get_reports():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, damage_type, confidence, latitude, longitude, image, created_at
        FROM reports
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0],
            "damage_type": r[1],
            "confidence": r[2],
            "latitude": r[3],
            "longitude": r[4],
            "image": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


@app.post("/detect")
async def detect(
    file: UploadFile = File(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    conf: float = Form(0.25)
):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")

    results = model.predict(np.array(img), conf=conf)[0]

    detections = []

    conn = get_conn()
    cur = conn.cursor()

    for box in results.boxes:
        name = model.names[int(box.cls)]
        score = float(box.conf)

        x1, y1, x2, y2 = [round(v, 1) for v in box.xyxy[0].tolist()]

        detections.append({
            "damage_type": name,
            "confidence": round(score, 4),
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        })

        cur.execute(
            """
            INSERT INTO reports (damage_type, confidence, latitude, longitude, image)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, score, latitude, longitude, file.filename)
        )

    conn.commit()
    cur.close()
    conn.close()

    # Bounding box çəkilmiş şəkli hazırla
    annotated = results.plot()[:, :, ::-1]  # BGR -> RGB
    annotated_img = Image.fromarray(annotated)
    buffer = io.BytesIO()
    annotated_img.save(buffer, format="JPEG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "filename": file.filename,
        "detections_count": len(detections),
        "detections": detections,
        "annotated_image": img_base64
    }
