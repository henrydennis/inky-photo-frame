from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from inky.auto import auto
from PIL import Image
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import random
import shutil

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.abspath('photos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Handle static photos directory
static_photos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'photos')

try:
    # Remove existing symlink or directory if it exists
    if os.path.islink(static_photos_dir):
        os.unlink(static_photos_dir)
    elif os.path.exists(static_photos_dir):
        shutil.rmtree(static_photos_dir)

    # Create new symlink
    os.symlink(app.config['UPLOAD_FOLDER'], static_photos_dir)
except Exception as e:
    print(f"Warning: Could not create symlink: {e}")
    # If symlink fails, try to create directory and copy files
    try:
        os.makedirs(static_photos_dir, exist_ok=True)
        for file in os.listdir(app.config['UPLOAD_FOLDER']):
            src = os.path.join(app.config['UPLOAD_FOLDER'], file)
            dst = os.path.join(static_photos_dir, file)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
    except Exception as e:
        print(f"Error setting up static photos directory: {e}")

# Initialize the Inky display
try:
    display = auto()
except Exception as e:
    print(f"Warning: Could not initialize Inky display: {e}")
    display = None

def get_random_image():
    """Get a random image from the photos directory"""
    photos = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if photos:
        return os.path.join(app.config['UPLOAD_FOLDER'], random.choice(photos))
    return None

def update_display():
    """Update the Inky display with a random image"""
    if not display:
        print("Display not initialized")
        return

    image_path = get_random_image()
    if not image_path:
        print("No images available")
        return

    try:
        # Open the image
        image = Image.open(image_path)
        
        # Resize the image to fit the display while maintaining aspect ratio
        image.thumbnail((display.width, display.height))
        
        # Create a new white image with the display's dimensions
        new_image = Image.new("RGB", (display.width, display.height), (255, 255, 255))
        
        # Calculate position to center the image
        x = (display.width - image.width) // 2
        y = (display.height - image.height) // 2
        
        # Paste the resized image onto the white background
        new_image.paste(image, (x, y))
        
        # Show the image on the display
        display.set_image(new_image)
        display.show()
        
        print(f"Updated display with image: {image_path}")
    except Exception as e:
        print(f"Error updating display: {e}")

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(update_display, 'interval', hours=1)  # Change image every hour
scheduler.start()

@app.route('/')
def index():
    """Display the upload form and list of images"""
    photos = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    return render_template('index.html', photos=photos)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle photo uploads"""
    if 'photo' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['photo']
    if file.filename == '':
        return redirect(url_for('index'))
    
    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Also copy to static directory if symlink failed
        static_file_path = os.path.join(static_photos_dir, filename)
        try:
            if not os.path.islink(static_photos_dir):
                shutil.copy2(file_path, static_file_path)
        except Exception as e:
            print(f"Error copying to static directory: {e}")
            
        update_display()  # Update display with new image
    
    return redirect(url_for('index'))

@app.route('/update_display', methods=['POST'])
def trigger_update_display():
    """Manually trigger a display update"""
    update_display()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 