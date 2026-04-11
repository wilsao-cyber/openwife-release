#!/bin/bash

echo "=== AI Wife App Setup ==="

# Check Python version
python3 --version || { echo "Python 3 required"; exit 1; }

# Check Flutter
flutter --version || { echo "Flutter not installed. Install from https://flutter.dev"; exit 1; }

# Check OpenCode
opencode --version || { echo "OpenCode not installed. Run: curl -fsSL https://opencode.ai/install | bash"; exit 1; }

# Setup Python server
echo "Setting up Python server..."
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Setup Flutter app
echo "Setting up Flutter app..."
cd mobile_app
flutter pub get
cd ..

# Create output directories
mkdir -p output/audio output models/3d models/tts

# Create voice_samples directory
mkdir -p voice_samples

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Place voice samples in voice_samples/ directory"
echo "2. Update config/credentials.json with your Google OAuth credentials"
echo "3. Update config/server_config.yaml with your settings"
echo "4. Start server: bash scripts/start_server.sh"
echo "5. Run Flutter app: cd mobile_app && flutter run"
