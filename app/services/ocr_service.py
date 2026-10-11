from paddleocr import PaddleOCR


ocr = PaddleOCR(
    lang="en",
    enable_mkldnn=False
)


def extract_image_text(file_path: str) -> str:

    result = ocr.predict(file_path)

    text_parts = []

    for page_result in result:

        if "rec_texts" in page_result:
            text_parts.extend(page_result["rec_texts"])

    return "\n".join(text_parts)