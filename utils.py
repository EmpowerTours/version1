from io import BytesIO
import qrcode

def get_message(update):
    if update.message:
        return update.message, "message"
    elif update.edited_message:
        return update.edited_message, "edited_message"
    return None, None

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    return qr_buffer
