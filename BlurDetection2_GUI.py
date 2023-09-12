import sys
import argparse
import logging
import pathlib
import json
import cv2
import shutil
import tkinter as tk
from tkinter import filedialog, StringVar, OptionMenu
import tempfile
import subprocess

from blur_detection import estimate_blur
from blur_detection import pretty_blur_map

def parse_args():
    parser = argparse.ArgumentParser(description='run blur detection on a single image')
    parser.add_argument('-v', '--verbose', action='store_true', help='set logging level to debug')
    parser.add_argument('-d', '--display', action='store_true', help='display images')
    return parser.parse_args()

def find_images_in_folder(folder_path, img_extensions=['.jpg', '.png', '.jpeg', '.heic']):
    img_extensions += [i.upper() for i in img_extensions]
    image_paths = []

    for img_ext in img_extensions:
        image_paths.extend(list(pathlib.Path(folder_path).rglob(f'*{img_ext}')))
    
    return image_paths

def convert_heic_to_jpeg(heic_path):
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_jpeg:
        temp_jpeg_path = temp_jpeg.name
        subprocess.run(['sips', '-s', 'format', 'jpeg', heic_path, '--out', temp_jpeg_path], check=True)
        return temp_jpeg_path

def main():
    args = parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level)

    # Create the main tkinter window
    root = tk.Tk()
    root.title("Blur Detection")

    # Create a tkinter variable to store the selected threshold
    selected_threshold = StringVar()
    selected_threshold.set("100")  # Default threshold value

    # Define the list of threshold options
    threshold_options = ["5", "10", "20", "40", "50", "75", "100", "200", "400", "1000"]

    # Create a dropdown menu for selecting the threshold
    threshold_label = tk.Label(root, text="Select Threshold:")
    threshold_label.pack()
    threshold_menu = OptionMenu(root, selected_threshold, *threshold_options)
    threshold_menu.pack()

    # Function to handle the "Start" button click
    def start_processing():
        folder_path = filedialog.askdirectory(title='Select a folder of images')
        if not folder_path:
            logging.info('No folder selected. Exiting.')
            return

        logging.info(f'Selected folder: {folder_path}')

        # Get the threshold value from the dropdown menu
        threshold_value = float(selected_threshold.get())

        results = []

        # Customize the folder name based on the selected folder and chosen threshold
        folder_name = f'{pathlib.Path(folder_path).name}_blur_{int(threshold_value)}'
        blur_folder = pathlib.Path(folder_path) / folder_name
        blur_folder.mkdir(exist_ok=True)

        for image_path in find_images_in_folder(folder_path):
            image_name = image_path.name
            logging.info(f'processing {image_name}')
            temp_jpeg_path = None  # Initialize temp_jpeg_path

            try:
                if image_path.suffix.lower() == '.heic':
                    # Convert HEIC image to JPEG using sips (macOS command-line tool)
                    temp_jpeg_path = convert_heic_to_jpeg(image_path)

                    # Read the converted JPEG image with OpenCV
                    image = cv2.imread(temp_jpeg_path)
                else:
                    image = cv2.imread(str(image_path))
                    if image is None:
                        logging.warning(f'warning! failed to read image from {image_name}; skipping!')
                        continue

                if image.shape[2] == 3:  # Check the number of color channels
                    blur_map, score, _ = estimate_blur(image, threshold=threshold_value)

                    logging.info(f'image_path: {image_name} score: {score}')
                    results.append({'input_path': image_name, 'score': score})

                    if score < threshold_value:  # Only move images below the threshold
                        if image_path.suffix.lower() == '.heic':
                            # If the image is HEIC, move the original HEIC file
                            shutil.move(image_path, blur_folder / image_name)
                        else:
                            # If the image is not HEIC, move the original file
                            shutil.move(image_path, blur_folder / image_name)

                    if args.display:
                        cv2.imshow('input', image)
                        cv2.imshow('result', pretty_blur_map(blur_map))

                        if cv2.waitKey(0) == ord('q'):
                            logging.info('exiting...')
                            exit()

                    # Log image processing information to a log.txt file in the subfolder
                    with open(blur_folder / 'log.txt', 'a') as log_file:
                        log_file.write(f'Processed: {image_name}, Score: {score}\n')
            except Exception as e:
                logging.warning(f'Failed to process image {image_name}: {str(e)}')
            finally:
                # Remove the temporary JPEG file if it was created
                if temp_jpeg_path is not None:
                    pathlib.Path(temp_jpeg_path).unlink()

        logging.info('Processing complete.')
        if results:
            save_path = pathlib.Path(folder_path) / 'blurry_results.json'
            logging.info(f'saving json to {save_path}')

            with open(save_path, 'w') as result_file:
                data = {'folder_path': folder_path, 'threshold': threshold_value, 'results': results}
                json.dump(data, result_file, indent=4)

    # Create a "Start" button
    start_button = tk.Button(root, text="Start Processing", command=start_processing)
    start_button.pack()

    # Start the tkinter main loop
    root.mainloop()

if __name__ == '__main__':
    assert sys.version_info >= (3, 6), sys.version_info
    main()

