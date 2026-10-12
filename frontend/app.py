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
    has_coords = latitude != 0.0 or longitude != 0.0
    st.caption("Enter coordinates so the report appears on the map. Example (Baku): 40.4093, 49.8671")

    file = st.file_uploader("Upload a road image", type=["jpg", "jpeg", "png"])
    if not file:
        return

    file_bytes = file.getvalue()
    key = f"{file.name}|{len(file_bytes)}|{conf}"

    # Call the backend only when the image or threshold changes.
    # Nothing is written to the database here (preview only).
    if st.session_state.get("det_key") != key:
        with st.spinner("Analyzing... (the first request may take up to a minute)"):
            files = {"file": (file.name, file_bytes, file.type)}
            try:
                response = requests.post(
                    API_URL, files=files, data={"conf": conf, "save": "false"}, timeout=120
                )
            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to the backend: {e}")
                return

        if response.status_code != 200:
            st.error(f"Error: {response.status_code}")
            st.text(response.text)
            return

        st.session_state["det_key"] = key
        st.session_state["det_data"] = response.json()
        st.session_state["saved_key"] = None

    data = st.session_state["det_data"]
    st.image(base64.b64decode(data["annotated_image"]), caption="Detection result")

    if data["detections_count"] == 0:
        st.warning("No damage detected.")
        return

    st.success(f"{data['detections_count']} damage(s) detected in this image.")

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

    st.divider()

    if st.session_state.get("saved_key") == key:
        st.success("✅ Saved as 1 report. Open the Map tab to see it.")
        return

    if not has_coords:
        st.info("No coordinates entered: the report will be saved but will not appear on the map.")

    if st.button("💾 Save to map"):
        payload = {
            "image": file.name,
            "detections": data["detections"],
        }
        if has_coords:
            payload["latitude"] = latitude
            payload["longitude"] = longitude
        try:
            resp = requests.post(REPORTS_URL, json=payload, timeout=60)
        except requests.exceptions.RequestException as e:
            st.error(f"Could not save the report: {e}")
            return
        if resp.status_code != 200:
            st.error(f"Error: {resp.status_code}")
            st.text(resp.text)
            return
        st.session_state["saved_key"] = key
        st.rerun()


def has_valid_location(r):
    lat, lon = r.get("latitude"), r.get("longitude")
    if lat is None or lon is None:
        return False
    # (0, 0) and values near it are leftovers from empty/test input
    return not (abs(lat) < 1 and abs(lon) < 1)


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

    located = [r for r in reports if has_valid_location(r)]

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
        st.info("No reports with coordinates yet. Upload an image in the Detect tab, enter latitude/longitude and press 'Save to map'.")

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    for r in located:
        color = COLORS.get(r["damage_type"], "blue")
        created = (r.get("created_at") or "")[:16].replace("T", " ")
        count = r.get("detection_count") or 1
        detections = r.get("detections") or [
            {"damage_type": r["damage_type"], "confidence": r["confidence"]}
        ]

        lines = "".join(
            f"{i}. {d['damage_type'].capitalize()} — {d['confidence'] * 100:.1f}%<br>"
            for i, d in enumerate(detections, start=1)
        )
        popup_html = (
            f"<b>{count} damage(s) found</b><br>"
            f"{lines}"
            f"<hr style='margin:4px 0'>"
            f"Image: {r.get('image') or '-'}<br>"
            f"Date: {created}"
        )

        folium.CircleMarker(
            location=[r["latitude"], r["longitude"]],
            radius=11 if count > 1 else 9,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{r['damage_type']} · {count} damage(s)",
        ).add_to(m)

        if count > 1:
            folium.Marker(
                location=[r["latitude"], r["longitude"]],
                icon=folium.DivIcon(
                    icon_size=(22, 22),
                    icon_anchor=(11, 11),
                    html=(
                        "<div style='width:22px;height:22px;line-height:22px;"
                        "text-align:center;color:white;font-weight:bold;"
                        f"font-size:12px;pointer-events:none;'>{count}</div>"
                    ),
                ),
            ).add_to(m)

    points = {(r["latitude"], r["longitude"]) for r in located}
    if len(points) > 1:
        m.fit_bounds([list(p) for p in points], max_zoom=15)

    st.caption("🔴 Pothole   🟠 Crack   (number on marker = damages in that image)")
    st_folium(m, height=500, use_container_width=True, returned_objects=[])


with tab_detect:
    run_detection()

with tab_map:
    show_map()
