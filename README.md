# Inky Photo Frame

A web-based photo frame manager for the Pimoroni Inky Impression e-ink display.

## Features

- Web interface for photo uploads
- Automatic photo rotation (every hour)
- Manual display updates
- Support for JPG and PNG images
- Automatic image resizing and centering

## Requirements

- Raspberry Pi (tested on Pi Zero W)
- Pimoroni Inky Impression display
- Python 3.6+
- pip

## Installation

1. Clone this repository:
```bash
git clone https://github.com/henrydennis/inky-photo-frame.git
cd inky-photo-frame
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

The web interface will be available at `http://[your-pi-ip]:5000`

## Usage

1. Open the web interface in your browser
2. Use the upload form to add new photos
3. Photos will automatically rotate every hour
4. Use the "Update Display Now" button to manually change the displayed image

## Notes

- The display updates may take a few seconds due to the e-ink refresh rate
- Images are automatically resized to fit the display while maintaining aspect ratio
- Uploaded photos are stored in the `photos` directory
- The application creates a white background for images that don't fill the entire display

## Troubleshooting

If you encounter any issues:

1. Check that the Inky display is properly connected
2. Ensure you have the correct permissions to access the display
3. Check the application logs for any error messages
4. Make sure the photos directory is writable 