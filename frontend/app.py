import streamlit as st
import requests
import base64
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="RoadGuard", page_icon="🚧", layout="wide")
st.title("🚧 RoadGuard")
st.caption("Detect. Report. Map.")

API_BASE = "https://roadguard-api-fcfs.onrender.com"
API_URL = f"{API_BASE}/detect"
REPORTS_URL = f"{API_BASE}/reports"

COLORS = {"pothole": "red", "crack": "orange"}

tab_detect, tab_map = st.tabs(["🔍 Detect", "🗺️ Map"])


def run_detection():
    conf = st.slider("Confidence threshold", 0.1, 0.9, 0.25)

    col1, col2 = st.columns(2)
    latitude = col1.number_input("Latitude (optional)", value=0.0, format="%.6f")
    longitude = col2.number_input("Longitude (optional)", value=0.0, format="%.6f")
    st.caption("Enter coordinates so the report appears on the map. Example (Baku): 40.4093, 49.8671")

    file = st.file_uploader("Upload a road image", type=["jpg", "jpeg", "png"])
    if not file:
        return

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
            return

    if response.status_code != 200:
        st.error(f"Error: {response.status_code}")
        st.text(response.text)
        return

    data = response.json()
    st.image(base64.b64decode(data["annotated_image"]), caption="Detection result")

    if data["detections_count"] == 0:
        st.warning("No damage detected.")
        return

    st.success(f"{data['detections_count']} damage(s) detected and saved to the database.")
    if "latitude" in form:
        st.info("Location saved. Open the Map tab to see it.")

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


def show_map():
    st.subheader("Reported road damage")

    if st.button("🔄 Refresh map"):
        st.rerun()

    try:
        with st.spinner("Loading reports... (the first request may take up to a minute)"):
            resp = requests.get(REPORTS_URL, timeout=120)
        resp.raise_for_status()
        reports = resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not load reports: {e}")
        return

    located = [
        r for r in reports
        if r.get("latitude") is not None and r.get("longitude") is not None
    ]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total reports", len(reports))
    c2.metric("Reports with location", len(located))
    c3.metric("Without location", len(reports) - len(located))

    if located:
        center = [located[0]["latitude"], located[0]["longitude"]]
        zoom = 13
    else:
        center = [40.4093, 49.8671]  # Baku
        zoom = 11
        st.info("No reports with coordinates yet. Upload an image in the Detect tab and enter latitude/longitude.")

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    for r in located:
        color = COLORS.get(r["damage_type"], "blue")
        created = (r.get("created_at") or "")[:16].replace("T", " ")
        popup_html = (
            f"<b>{r['damage_type'].capitalize()}</b><br>"
            f"Confidence: {r['confidence'] * 100:.1f}%<br>"
            f"Image: {r.get('image') or '-'}<br>"
            f"Date: {created}"
        )
        folium.CircleMarker(
            location=[r["latitude"], r["longitude"]],
            radius=9,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{r['damage_type']} ({r['confidence'] * 100:.0f}%)",
        ).add_to(m)

    if len(located) > 1:
        m.fit_bounds([[r["latitude"], r["longitude"]] for r in located])

    st.caption("🔴 Pothole   🟠 Crack")
    st_folium(m, height=500, use_container_width=True, returned_objects=[])


with tab_detect:
    run_detection()

with tab_map:
    show_map()
