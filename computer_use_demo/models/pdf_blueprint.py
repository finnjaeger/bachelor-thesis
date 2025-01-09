from fpdf import FPDF
from PIL import Image
import base64
from io import BytesIO


class PDF(FPDF):
    def header(self):
        self.set_font("ArialU", "B", 12)
        self.cell(0, 10, "User Actions Report", align="C", ln=True)

    def chapter_title(self, title):
        self.set_font("ArialU", "B", 12)
        self.multi_cell(0, 10, title, align="L")
        self.ln(5)

    def chapter_body(self, text):
        self.set_font("ArialU", "", 12)
        self.multi_cell(0, 10, text)

    def add_image(self, base64_string, width=100):
        # Decode base64 string into a temporary image
        img_data = base64.b64decode(base64_string)
        img = Image.open(BytesIO(img_data))
        temp_file = BytesIO()
        img.save(temp_file, format="PNG")
        temp_file.seek(0)
        self.image(temp_file, x=None, y=None, w=width)
