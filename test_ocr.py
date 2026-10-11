from app.services.ocr_service import extract_image_text


file_path = "uploads/aa.jpeg"

text = extract_image_text(file_path)

print("========== OCR RESULT ==========")
print(text)
print("================================")