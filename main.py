# main.py

import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import cv2
import os
import re
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

app = FastAPI()

def extract_number(filename):
    match = re.search(r'(\d+)', filename)
    return int(match.group()) if match else float('inf')

def image_to_text(image_folder):
    aggregated_text = ""
    image_files = [f for f in os.listdir(image_folder) if f.startswith('rectangle_') and f.endswith('.png')]

    # Sort the files by the numeric part
    image_files.sort(key=extract_number)

    # Loop through each sorted image file
    for filename in image_files:
        image_path = os.path.join(image_folder, filename)

        # Read the image
        image = cv2.imread(image_path)

        # Convert the image to black and white for better OCR
        ret, thresh1 = cv2.threshold(image, 120, 255, cv2.THRESH_BINARY)

        # Perform OCR on the image
        text = pytesseract.image_to_string(thresh1, config='--psm 6')

        # Append the result to aggregated text
        aggregated_text += text + "\n"

    return aggregated_text

def extract_text_with_positions(pdf_path):
    doc = fitz.open(pdf_path)
    text_positions = []
    for page in doc:
        for block in page.get_text("blocks"):
            if block[6] == 0:  # Text blocks
                text_positions.append({
                    'text': block[4].strip(),
                    'bbox': block[:4]  # (x0, y0, x1, y1)
                })
    doc.close()
    return text_positions

def draw_and_save_rectangle(pdf_path, output_folder, text_positions, zoom=2.0):
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    
    # Create a high-resolution image from the page
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    for i, item in enumerate(text_positions):
        bbox = item['bbox']
        
        # Calculate the rectangle coordinates in the zoomed image
        x0, y0, x1, y1 = [int(coord * zoom) for coord in bbox]
        
        # Crop the image around the rectangle
        cropped_img = img.crop((x0, y0, x1, y1))
        
        # Save the cropped image
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        cropped_img.save(f"{output_folder}/rectangle_{i+1}.png")

    doc.close()

@app.post("/upload_pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        pdf_path = f"./{file.filename}"
        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        output_folder = 'output_images'
        text_positions = extract_text_with_positions(pdf_path)
        draw_and_save_rectangle(pdf_path, output_folder, text_positions)
        aggregated_text = image_to_text(output_folder)
        
        return JSONResponse(content={"text": aggregated_text})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
