import requests

from services.utility import convert_image_to_byte, convert_fa_digits_to_en
from configParams import Parameters

params = Parameters()

EXTERNAL_SERVICE_URL = params.external_service_url


def send_data_to_external_service(data: dict) -> None:
    """
    Sends data to an external service via a POST request.

    This function converts an image to bytes and plate numbers from Persian
    digits to English digits before sending them as part of a POST request
    to an external service.

    Args:
        data (dict): A dictionary containing 'image' (image data) and
                     'plate_number' (Persian digit string).

    Raises:
        requests.exceptions.ConnectionError: If there is a connection error.
        requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        requests.exceptions.RequestException: If there is an ambiguous exception during the request.
    """
    files = {'image': convert_image_to_byte(image=data['image'])}
    json_data = {'plate_number': convert_fa_digits_to_en(data['plate_number'])}
    try:
        response = requests.post(EXTERNAL_SERVICE_URL, data=json_data, files=files)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to external service: {EXTERNAL_SERVICE_URL}.")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
