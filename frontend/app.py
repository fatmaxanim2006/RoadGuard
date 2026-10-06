import streamlit as st
import requests
import base64

st.set_page_config(page_title="RoadGuard", page_icon="🚧")
st.title("🚧 RoadGuard")
st.caption("Detect. Report. Map.")

API_URL = "https://roadguard-api-fcfs.onrender.com/detect"

conf = st.slider("Confidence threshold", 0.1, 0.9, 0.25)

col1, col2 = st.columns(2)
latitude = col1.number_input("Latitude (optional)", value=0.0, format="%.6f")
longitude = col2.number_input("Longitude (optional)", value=0.0, format="%.6f")

file = st.file_uploader("Upload a road image", type=["jpg", "jpeg", "png"])

if file:
    with st.spinner("Analyzing... (the first request may take up to a minute)"):
        files = {"file": (file.name, file.getvalue(), file.type)}
        form = {"conf": conf}
        if latitude != 0.0 or longitude != 0.0:
            form["latitude"] = latitude
            form["longitude"] = longitude

        try:
            response = requests.post(API_URL, files=files, data=form, timeout=120)
        except requests.exceptions.RequestException as e:
            st.error(f"Could not connect to the backend: {e}")
            st.stop()

    if response.status_code == 200:
        data = response.json()

        img_bytes = base64.b64decode(data["annotated_image"])
        st.image(img_bytes, caption="Detection result")

        if data["detections_count"] == 0:
            st.warning("No damage detected.")
        else:
            st.success(f"{data['detections_count']} damage(s) detected and saved to the database.")
            for i, d in enumerate(data["detections"], start=1):
                st.markdown(
                    f"**{i}. {d['damage_type'].capitalize()}** — "
                    f"confidence: **{d['confidence'] * 100:.1f}%**"
                )
                b = d.get("bbox")
                if b:
                    st.caption(
                        f"Bounding box (pixels): x1={b['x1']}, y1={b['y1']}, "
                        f"x2={b['x2']}, y2={b['y2']}"
                    )
    else:
        st.error(f"Error: {response.status_code}")
        st.text(response.text)
