from app import create_app
import sys
import os

# Ensure the model cache directory exists
os.makedirs(os.path.expanduser('~/.cache/huggingface/hub'), exist_ok=True)

try:
    app = create_app()
    
    if __name__ == '__main__':
        # Run the app without SSL for local development
        app.run(debug=True, host='127.0.0.1', port=5000)
except Exception as e:
    print(f"Error starting the application: {str(e)}")
    sys.exit(1) 