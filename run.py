from app import create_app
import sys
import os

# Ensure the model cache directory exists
os.makedirs(os.path.expanduser('~/.cache/huggingface/hub'), exist_ok=True)

try:
    app = create_app()
    
    if __name__ == '__main__':
        app.run(debug=True)
except Exception as e:
    print(f"Error starting the application: {str(e)}")
    sys.exit(1) 