import streamlit as st
from ultralytics import YOLO
from PIL import Image
import numpy as np

st.set_page_config(page_title="RoadGuard", page_icon="🚧")
st.title("🚧 RoadGuard")
st.caption("Detect. Report. Map.")

@st.cache_resource
def load_model():
    return YOLO("best.pt")

model = load_model()

conf = st.slider("Confidence threshold", 0.1, 0.9, 0.25)
file = st.file_uploader("Yol şəklini yüklə", type=["jpg", "jpeg", "png"])

if file:
    img = Image.open(file).convert("RGB")
    results = model.predict(np.array(img), conf=conf)[0]

    st.image(results.plot()[:, :, ::-1], caption="Detection result")

    if len(results.boxes) == 0:
        st.warning("Heç bir zədə aşkarlanmadı.")
    else:
        st.subheader("Nəticələr")
        for box in results.boxes:
            name = model.names[int(box.cls)]
            score = float(box.conf)
            x, y, w, h = box.xywh[0].tolist()
            st.write(f"**{name}** — confidence: {score:.0%}")
            st.caption(f"Bounding box: [{x:.0f}, {y:.0f}, {w:.0f}, {h:.0f}]")