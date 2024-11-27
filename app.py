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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
        
        # Log original image size
        logger.info(f"Original image size: {image.size}")
        
        # Calculate scaling ratios
        width_ratio = display.width / image.width
        height_ratio = display.height / image.height
        
        # Use the larger ratio to ensure the image fills the frame
        scale_ratio = max(width_ratio, height_ratio)
        
        # Calculate new dimensions
        new_width = int(image.width * scale_ratio)
        new_height = int(image.height * scale_ratio)
        
        # Resize the image
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized image size: {image.size}")
        
        # Create a new white image with the display's dimensions
        new_image = Image.new("RGB", (display.width, display.height), (255, 255, 255))
        
        # Calculate position to center the image
        x = (display.width - new_width) // 2
        y = (display.height - new_height) // 2
        logger.info(f"Centering image at position: ({x}, {y})")
        
        # Paste the resized image onto the white background
        new_image.paste(image, (x, y))
        
        # Show the image on the display
        logger.info("Setting image on display")
        display.set_image(new_image)
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

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(schedule_update, 'interval', hours=1, next_run_time=datetime.now())  # Run immediately and then every hour
scheduler.start()
logger.info("Scheduler started - images will update every hour")

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
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logger.info(f"New photo uploaded: {filename}")
            uploaded_files.append(filename)
            
            # Also copy to static directory if symlink failed
            static_file_path = os.path.join(static_photos_dir, filename)
            try:
                if not os.path.islink(static_photos_dir):
                    shutil.copy2(file_path, static_file_path)
                    logger.info(f"Copied photo to static directory: {filename}")
            except Exception as e:
                logger.error(f"Error copying to static directory: {e}")
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
            
            # Calculate scaling ratios
            width_ratio = display.width / image.width
            height_ratio = display.height / image.height
            scale_ratio = max(width_ratio, height_ratio)
            
            # Calculate new dimensions
            new_width = int(image.width * scale_ratio)
            new_height = int(image.height * scale_ratio)
            
            # Resize the image
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create a new white image
            new_image = Image.new("RGB", (display.width, display.height), (255, 255, 255))
            
            # Center the image
            x = (display.width - new_width) // 2
            y = (display.height - new_height) // 2
            
            # Paste the resized image
            new_image.paste(image, (x, y))
            
            # Update the display
            display.set_image(new_image)
            display.show()
            
            logger.info("Display updated successfully")
        else:
            logger.error(f"Selected image not found: {image_path}")
    except Exception as e:
        logger.error(f"Error updating display with selected image: {e}")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    logger.info("Starting Flask web server")
    app.run(host='0.0.0.0', port=5000) 