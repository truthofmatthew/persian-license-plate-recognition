import requests

from carvann.utility import convert_image_to_byte, convert_fa_digits_to_en

CARVANN_URL = 'http://127.0.0.1:8000/api/v1/camera/'


def send_data_to_carvann(data: dict) -> None:
    files = {'image': convert_image_to_byte(image=data['image'])}
    json_data = {'plate_number': convert_fa_digits_to_en(data['plate_number'])}

    response = requests.post(CARVANN_URL, data=json_data, files=files)

    # Check response status
    if response.status_code == 200:
        print('Data sent successfully!')
    else:
        print(f'Error sending data - Status Code: {response.status_code}')
