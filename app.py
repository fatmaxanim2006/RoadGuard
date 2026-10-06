import streamlit as st
import requests
import base64

st.set_page_config(page_title="RoadGuard", page_icon="🚧")
st.title("🚧 RoadGuard")
st.caption("Detect. Report. Map.")

API_URL = "http://127.0.0.1:8000/detect"

conf = st.slider("Confidence threshold", 0.1, 0.9, 0.25)
file = st.file_uploader("Yol şəklini yüklə", type=["jpg", "jpeg", "png"])

if file:
    with st.spinner("Analiz edilir..."):
        files = {"file": (file.name, file.getvalue(), file.type)}
        response = requests.post(API_URL, files=files, data={"conf": conf})

    if response.status_code == 200:
        data = response.json()

        img_bytes = base64.b64decode(data["annotated_image"])
        st.image(img_bytes, caption="Detection result")

        if data["detections_count"] == 0:
            st.warning("Heç bir zədə aşkarlanmadı.")
        else:
            st.subheader("Nəticələr")
            for d in data["detections"]:
                st.write(f"**{d['damage_type']}** — confidence: {d['confidence']:.0%}")
    else:
        st.error(f"Xəta baş verdi: {response.status_code}")
