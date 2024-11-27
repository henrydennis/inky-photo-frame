from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from inky import Inky7Colour as Inky
from PIL import Image
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import random
import shutil
import logging
from logging.handlers import RotatingFileHandler
import traceback
import RPi.GPIO as GPIO
import json

# Set up logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'inky_frame.log'
log_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)  # 1MB per file, keep 5 files
log_handler.setFormatter(log_formatter)

logger = logging.getLogger('inky_frame')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Also log to console for systemd journal
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('photos')
logger.info("Starting Inky Photo Frame application")

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
logger.info(f"Upload folder configured: {app.config['UPLOAD_FOLDER']}")

# Handle static photos directory
static_photos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'photos')

try:
    # Remove existing symlink or directory if it exists
    if os.path.islink(static_photos_dir):
        os.unlink(static_photos_dir)
        logger.info("Removed existing symlink")
    elif os.path.exists(static_photos_dir):
        shutil.rmtree(static_photos_dir)
        logger.info("Removed existing static photos directory")

    # Create new symlink
    os.symlink(app.config['UPLOAD_FOLDER'], static_photos_dir)
    logger.info("Created symlink for static photos")
except Exception as e:
    logger.warning(f"Could not create symlink: {e}")
    # If symlink fails, try to create directory and copy files
    try:
        os.makedirs(static_photos_dir, exist_ok=True)
        for file in os.listdir(app.config['UPLOAD_FOLDER']):
            src = os.path.join(app.config['UPLOAD_FOLDER'], file)
            dst = os.path.join(static_photos_dir, file)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
        logger.info("Created static photos directory and copied files")
    except Exception as e:
        logger.error(f"Error setting up static photos directory: {e}")

# Initialize the Inky display
try:
    display = Inky(resolution=(600, 448))
    logger.info(f"Successfully initialized Inky display: {display.width}x{display.height}")
except Exception as e:
    logger.error(f"Could not initialize Inky display: {e}\n{traceback.format_exc()}")
    display = None

def get_random_image():
    """Get a random image from the photos directory"""
    try:
        photos = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        logger.info(f"Found {len(photos)} photos in directory")
        if photos:
            chosen_photo = random.choice(photos)
            logger.info(f"Selected random photo: {chosen_photo}")
            return os.path.join(app.config['UPLOAD_FOLDER'], chosen_photo)
        logger.warning("No photos available to display")
        return None
    except Exception as e:
        logger.error(f"Error in get_random_image: {e}\n{traceback.format_exc()}")
        return None

def update_display():
    """Update the Inky display with a random image"""
    logger.info("Starting display update process")
    
    if not display:
        logger.error("Display not initialized, skipping update")
        return

    image_path = get_random_image()
    if not image_path:
        logger.error("No images available for display update")
        return

    try:
        # Open the image
        logger.info(f"Opening image: {image_path}")
        image = Image.open(image_path)
        
        # Prepare image for display with current orientation
        display_image = prepare_for_display(image, current_orientation)
        
        # Show the image on the display
        logger.info("Setting image on display")
        display.set_image(display_image)
        logger.info("Showing image on display")
        display.show()
        
        logger.info(f"Successfully updated display with image: {os.path.basename(image_path)}")
    except Exception as e:
        logger.error(f"Error updating display: {e}\n{traceback.format_exc()}")

def schedule_update():
    """Wrapper for scheduler to catch and log any errors"""
    try:
        logger.info("Scheduled update triggered")
        update_display()
    except Exception as e:
        logger.error(f"Error in scheduled update: {e}\n{traceback.format_exc()}")

# Constants for settings
SETTINGS_FILE = 'settings.json'
DEFAULT_SETTINGS = {
    'orientation': ORIENTATION_0
}

def load_settings():
    """Load settings from file, creating default if doesn't exist"""
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            logger.info(f"Settings loaded: {settings}")
            return settings
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load settings ({e}), using defaults")
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS

def save_settings(settings):
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
        logger.info(f"Settings saved: {settings}")
    except Exception as e:
        logger.error(f"Could not save settings: {e}")

# Initialize the scheduler
scheduler = BackgroundScheduler()

# Load saved settings
settings = load_settings()
current_orientation = settings.get('orientation', ORIENTATION_0)
logger.info(f"Loaded orientation setting: {current_orientation}")

scheduler.add_job(schedule_update, 'interval', hours=1, next_run_time=datetime.now())  # Run immediately and then every hour
scheduler.start()
logger.info("Scheduler started - images will update every hour")

def fix_image_orientation(image):
    """Fix image orientation based on EXIF data"""
    try:
        # Check if image has EXIF data
        if hasattr(image, '_getexif') and image._getexif():
            exif = dict(image._getexif().items())
            
            # EXIF orientation tag
            orientation = exif.get(274)  # 274 is the orientation tag ID
            
            # Rotate or flip based on orientation
            if orientation == 2:
                return image.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                return image.transpose(Image.ROTATE_180)
            elif orientation == 4:
                return image.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                return image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
            elif orientation == 6:
                return image.transpose(Image.ROTATE_270)
            elif orientation == 7:
                return image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
            elif orientation == 8:
                return image.transpose(Image.ROTATE_90)
    except Exception as e:
        logger.warning(f"Error processing EXIF orientation: {e}")
    
    return image

# Initialize GPIO for buttons
BUTTON_A = 5
BUTTON_B = 6
BUTTON_C = 16
BUTTON_D = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup([BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_D], GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Global orientation state
ORIENTATION_0 = "0"    # Normal
ORIENTATION_90 = "90"  # Rotated right
ORIENTATION_180 = "180"  # Upside down
ORIENTATION_270 = "270"  # Rotated left
current_orientation = ORIENTATION_0

def handle_button(channel):
    """Handle button presses for orientation changes"""
    global current_orientation
    try:
        if channel in [BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_D]:
            # Cycle through orientations based on button press
            if channel == BUTTON_A:
                current_orientation = ORIENTATION_0
            elif channel == BUTTON_B:
                current_orientation = ORIENTATION_90
            elif channel == BUTTON_C:
                current_orientation = ORIENTATION_180
            elif channel == BUTTON_D:
                current_orientation = ORIENTATION_270
            
            # Save the new orientation
            save_settings({'orientation': current_orientation})
            
            logger.info(f"Orientation changed to: {current_orientation}°")
            update_display()  # Update the display with new orientation
    except Exception as e:
        logger.error(f"Error handling button press: {e}")

# Update button event detection for all buttons
GPIO.remove_event_detect(BUTTON_A)  # Remove existing detection first
GPIO.remove_event_detect(BUTTON_B)
GPIO.setup([BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_D], GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(BUTTON_A, GPIO.FALLING, callback=handle_button, bouncetime=250)
GPIO.add_event_detect(BUTTON_B, GPIO.FALLING, callback=handle_button, bouncetime=250)
GPIO.add_event_detect(BUTTON_C, GPIO.FALLING, callback=handle_button, bouncetime=250)
GPIO.add_event_detect(BUTTON_D, GPIO.FALLING, callback=handle_button, bouncetime=250)

def compress_image(image, max_width, max_height):
    """Compress and resize image to target dimensions while maintaining aspect ratio"""
    # Calculate scaling ratios
    width_ratio = max_width / image.width
    height_ratio = max_height / image.height
    scale_ratio = min(width_ratio, height_ratio)
    
    # Calculate new dimensions
    new_width = int(image.width * scale_ratio)
    new_height = int(image.height * scale_ratio)
    
    # Resize the image using high-quality Lanczos resampling
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Create a new white background image
    final_image = Image.new("RGB", (max_width, max_height), (255, 255, 255))
    
    # Calculate position to center the image
    x = (max_width - new_width) // 2
    y = (max_height - new_height) // 2
    
    # Paste the resized image onto the white background
    final_image.paste(resized_image, (x, y))
    
    return final_image

def prepare_for_display(image, orientation):
    """Prepare image for display by rotating if needed"""
    # Create a mapping of orientations to rotation angles
    rotations = {
        ORIENTATION_0: 0,
        ORIENTATION_90: 90,
        ORIENTATION_180: 180,
        ORIENTATION_270: 270
    }
    
    # First ensure the image is the correct size for the display
    target_width = display.width
    target_height = display.height
    
    # Calculate scaling ratios
    width_ratio = target_width / image.width
    height_ratio = target_height / image.height
    scale_ratio = min(width_ratio, height_ratio)
    
    # Calculate new dimensions
    new_width = int(image.width * scale_ratio)
    new_height = int(image.height * scale_ratio)
    
    # Create a white background image of the correct size
    final_image = Image.new("RGB", (target_width, target_height), (255, 255, 255))
    
    # Resize the original image
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Center the resized image
    x = (target_width - new_width) // 2
    y = (target_height - new_height) // 2
    final_image.paste(resized_image, (x, y))
    
    # Get the rotation angle and rotate if needed
    angle = rotations.get(orientation, 0)
    if angle != 0:
        return final_image.rotate(angle, expand=False)
    
    return final_image

@app.route('/')
def index():
    """Display the upload form and list of images"""
    photos = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    logger.info(f"Index page requested, found {len(photos)} photos")
    return render_template('index.html', photos=photos)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle photo uploads"""
    if 'photos' not in request.files:
        logger.warning("Upload attempted with no files")
        return redirect(url_for('index'))
    
    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        logger.warning("Upload attempted with empty filenames")
        return redirect(url_for('index'))
    
    uploaded_files = []
    for file in files:
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            try:
                # Open and process the image
                image = Image.open(file)
                
                # Fix EXIF orientation during upload
                image = fix_image_orientation(image)
                
                # Convert to RGB if necessary (handles PNG with transparency)
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1])
                    image = background
                elif image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Compress and resize the image
                if current_orientation == ORIENTATION_90 or current_orientation == ORIENTATION_270:
                    image = compress_image(image, display.height, display.width)
                elif current_orientation == ORIENTATION_180:
                    image = compress_image(image, display.width, display.height)
                
                # Generate filename and save path
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save the compressed image
                image.save(file_path, 'JPEG', quality=85, optimize=True)
                logger.info(f"New photo uploaded and compressed: {filename}")
                uploaded_files.append(filename)
                
                # Also copy to static directory if symlink failed
                static_file_path = os.path.join(static_photos_dir, filename)
                try:
                    if not os.path.islink(static_photos_dir):
                        shutil.copy2(file_path, static_file_path)
                        logger.info(f"Copied photo to static directory: {filename}")
                except Exception as e:
                    logger.error(f"Error copying to static directory: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing image {file.filename}: {e}")
                continue
        else:
            logger.warning(f"Upload rejected - invalid file type: {file.filename}")
    
    if uploaded_files:
        update_display()  # Update display with the last uploaded image
    
    return redirect(url_for('index'))

@app.route('/update_display', methods=['POST'])
def trigger_update_display():
    """Manually trigger a display update"""
    logger.info("Manual display update triggered")
    update_display()
    return redirect(url_for('index'))

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    """Handle bulk photo deletion"""
    selected_files = request.form.getlist('selected_files')
    logger.info(f"Bulk delete requested for {len(selected_files)} files")
    
    for filename in selected_files:
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {filename}")
            else:
                logger.warning(f"File not found for deletion: {filename}")
        except Exception as e:
            logger.error(f"Error deleting file {filename}: {e}")
    
    return redirect(url_for('index'))

@app.route('/bulk_display', methods=['POST'])
def bulk_display():
    """Handle bulk display update with selected photos"""
    selected_files = request.form.getlist('selected_files')
    logger.info(f"Bulk display requested for {len(selected_files)} files")
    
    if not selected_files:
        return redirect(url_for('index'))
    
    if not display:
        logger.error("Display not initialized")
        return redirect(url_for('index'))
    
    try:
        # Use the first selected image for now (future enhancement could be to create a collage)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], selected_files[0])
        if os.path.exists(image_path):
            logger.info(f"Updating display with selected image: {selected_files[0]}")
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Fix orientation and compress
            compressed_image = compress_image(image, display.width, display.height)
            
            # Update the display
            display.set_image(compressed_image)
            display.show()
            
            logger.info("Display updated successfully")
        else:
            logger.error(f"Selected image not found: {image_path}")
    except Exception as e:
        logger.error(f"Error updating display with selected image: {e}")
    
    return redirect(url_for('index'))

@app.route('/delete_all_photos', methods=['POST'])
def delete_all_photos():
    """Delete all photos from the system"""
    try:
        # Get list of all photos
        photos = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
                if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        logger.info(f"Attempting to delete all photos ({len(photos)} files)")
        
        # Delete each photo
        for filename in photos:
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted file: {filename}")
                
                # Also remove from static directory if it exists
                static_file_path = os.path.join(static_photos_dir, filename)
                if os.path.exists(static_file_path) and not os.path.islink(static_photos_dir):
                    os.remove(static_file_path)
                    logger.info(f"Deleted file from static directory: {filename}")
            except Exception as e:
                logger.error(f"Error deleting file {filename}: {e}")
        
        logger.info("All photos deleted successfully")
    except Exception as e:
        logger.error(f"Error during bulk deletion: {e}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    try:
        logger.info("Starting Flask web server")
        app.run(host='0.0.0.0', port=5000)
    finally:
        GPIO.cleanup()  # Clean up GPIO on exit 