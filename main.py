from fastapi import FastAPI, File, UploadFile, Form
from ultralytics import YOLO
from PIL import Image
import numpy as np
import psycopg2
import io
import base64

app = FastAPI()

model = YOLO("best.pt")

DB_CONFIG = {
    "dbname": "roadguard",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": 5432
}


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

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for box in results.boxes:
        name = model.names[int(box.cls)]
        score = float(box.conf)

        detections.append({
            "damage_type": name,
            "confidence": round(score, 4)
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