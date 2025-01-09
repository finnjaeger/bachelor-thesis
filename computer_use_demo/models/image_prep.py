from PIL import Image, ImageDraw
import base64
from io import BytesIO

TOP_PIXELS = 0  # Would be 81 if you want to remove the option to close the browser or switch tabs
BOTTOM_PIXELS = 60
FILL_COLOR = "#f7f7f5"

"""
This function crops the image that Open AI receives from the user's computer. It removes 
the the bottom part of the image that conains the OS Task bar. Also it draws a white rectangle over
the browser URL bar to prevent the AI from switching the website. 
This is to reduce distracitons on the screen.
"""


def prep_image(b64_image: str) -> str:
    # Convert base64 to Image
    bytesio_image = BytesIO(base64.b64decode(b64_image))
    image = Image.open(bytesio_image)

    # Get the dimensions of the image
    width, height = image.size

    # Validate crop dimensions
    if TOP_PIXELS + BOTTOM_PIXELS >= height:
        raise ValueError("Crop size exceeds image height.")

    # Calculate the crop box (left, top, right, bottom)
    left = 0
    top = TOP_PIXELS
    right = width
    bottom = height - BOTTOM_PIXELS

    # Perform the crop
    cropped_image = image.crop((left, top, right, bottom))

    # Create a draw object
    draw = ImageDraw.Draw(cropped_image)

    draw.rectangle([width - 880, 81, width, 81 + 40], fill=FILL_COLOR)

    # Convert the image back to the desired output format
    output_buffer = BytesIO()
    cropped_image.save(output_buffer, format="PNG")
    output_buffer.seek(0)

    base64_output = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
    return base64_output
