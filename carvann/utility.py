from PySide6.QtCore import QBuffer


def convert_image_to_byte(image):
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    image.save(buffer, 'PNG')  # Save QImage to buffer as PNG format
    image_data = bytes(buffer.data())  # Get the binary data from the buffer
    buffer.close()
    return image_data


# --------------------------------------------------------------------------------------------------------------------
fa_to_en_digits = {
    '۰': '0',
    '۱': '1',
    '۲': '2',
    '۳': '3',
    '۴': '4',
    '۵': '5',
    '۶': '6',
    '۷': '7',
    '۸': '8',
    '۹': '9'
}


def convert_fa_digits_to_en(plate_number: str) -> str:
    result = []
    for char in plate_number:
        if char in fa_to_en_digits:
            result.append(fa_to_en_digits[char])
        else:
            result.append(char)
    return ''.join(result)
