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
- python3-venv (install with `sudo apt install python3-venv python3-full`)

## Installation

1. Install system dependencies:
```bash
sudo apt update
sudo apt install python3-venv python3-full git
```

2. Clone this repository:
```bash
git clone https://github.com/henrydennis/inky-photo-frame.git
cd inky-photo-frame
```

3. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

4. Install the required packages:
```bash
pip install -r requirements.txt
```

5. Run the application:
```bash
python app.py
```

The web interface will be available at `http://[your-pi-ip]:5000`

To have the application start automatically on boot, you can create a systemd service.

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
- Always activate the virtual environment (`source venv/bin/activate`) before running the application

## Troubleshooting

If you encounter any issues:

1. Check that the Inky display is properly connected
2. Ensure you have the correct permissions to access the display
3. Check the application logs for any error messages
4. Make sure the photos directory is writable
5. If you get "externally-managed-environment" errors, make sure you've created and activated the virtual environment as described in the installation steps