"""Quick web demo: upload a photo, see the plates. Run with `streamlit run streamlit_app.py` (pip install streamlit)."""
import cv2
import numpy as np
import streamlit as st

from plpr import Engine


@st.cache_resource
def engine():
    return Engine()


st.title("Persian License Plate Recognition")
uploaded = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])
if uploaded is not None:
    img = cv2.imdecode(np.frombuffer(uploaded.read(), np.uint8), cv2.IMREAD_COLOR)
    reads = engine().read(img)
    for r in reads:
        cv2.rectangle(img, r.box[:2], r.box[2:], (0, 0, 255), 3)
    st.image(img, channels="BGR", use_container_width=True)
    if reads:
        st.table([{"Plate": r.plate.persian if r.plate else r.text, "Plate confidence": round(r.plate_conf, 2),
                   "Char confidence": round(r.char_conf, 2)} for r in reads])
    else:
        st.write("No license plates detected.")
