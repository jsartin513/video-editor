import argparse
import os

from utils.utils import log

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

LOGO_PATH = "/Users/jessica.sartin/github_development/video-editor/src/static/bdl_rectangle_logo.png"

def watermark_images(directory, logo_path, output_directory):
    """
    Watermarks all images in a directory with the given logo.

    Args:
        directory (str): Path to the directory containing images.
        logo_path (str): Path to the logo file.
        output_directory (str): Path to the directory to save watermarked images.
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory, filename)
            process_image(image_path, logo_path, output_directory)

def process_image(image_path, logo_path, output_directory):
    """
    Processes a single image and applies a watermark.

    Args:
        image_path (str): Path to the image file.
        logo_path (str): Path to the logo file.
        output_directory (str): Path to the directory to save watermarked images.
    """
    log(f"Processing image: {image_path}")
    try:
        image = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")

        # Resize logo to 1/4 of its original size
        logo_width, logo_height = logo.size
        new_logo_size = (logo_width // 2, logo_height // 2)
        logo = logo.resize(new_logo_size)

        # Make the logo 50% transparent
        alpha = logo.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(0.75)
        logo.putalpha(alpha)

        image_width, image_height = image.size
        logo_width, logo_height = logo.size

        # Position the logo at the lower right corner
        x = image_width - logo_width - 10
        y = image_height - logo_height - 10

        image.paste(logo, (x, y), logo)

        output_path = os.path.join(output_directory, f"watermarked_{os.path.basename(image_path)}")
        
        # Replace jpg and jpeg with png to keep transparency
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            output_path = output_path[:-4] + ".png"
        
        image.save(output_path)
        print(f"Watermarked image saved: {output_path}")
    except Exception as e:
        print(f"Error processing {os.path.basename(image_path)}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Handle tournament videos.')
    parser.add_argument('image_directory', type=str, help='The name of the directory containing the videos')

    image_directory = parser.parse_args().image_directory
    output_directory = f"{image_directory}/watermarked_images"
    logo_path = LOGO_PATH

    watermark_images(image_directory, logo_path, output_directory)