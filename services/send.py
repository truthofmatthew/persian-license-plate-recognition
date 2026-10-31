import threading
import requests

from configParams import Parameters
from services.utility import convert_fa_digits_to_en, convert_image_to_byte

params = Parameters()

EXTERNAL_SERVICE_URL = params.external_service_url


def _send_worker(data: dict) -> None:
    if not EXTERNAL_SERVICE_URL or not EXTERNAL_SERVICE_URL.strip():
        return
    try:
        files = {'image': convert_image_to_byte(image=data['image'])}
        json_data = {'plate_number': convert_fa_digits_to_en(data['plate_number'])}
        response = requests.post(EXTERNAL_SERVICE_URL, data=json_data, files=files, timeout=4)
        response.raise_for_status()
    except Exception as e:
        print(f"[Webhook POST skipped/failed]: {e}")


def send_data_to_external_service(data: dict) -> None:
    """Sends data asynchronously without blocking the GUI."""
    if not EXTERNAL_SERVICE_URL or not EXTERNAL_SERVICE_URL.strip():
        return
    threading.Thread(target=_send_worker, args=(data,), daemon=True).start()
