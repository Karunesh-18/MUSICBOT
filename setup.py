#!/usr/bin/env python3
"""
Discord Music Bot Setup Script
This script helps you set up the Discord Music Bot with all required dependencies.
"""

import os
import sys
import subprocess
import platform

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"❌ {description} failed:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error during {description}: {e}")
        return False
    return True

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def install_dependencies():
    """Install Python dependencies"""
    commands = [
        ("pip install --upgrade pip", "Upgrading pip"),
        ("pip install -r requirements.txt", "Installing Python dependencies"),
    ]

    for command, description in commands:
        if not run_command(command, description):
            return False
    return True

def setup_ffmpeg():
    """Setup FFmpeg based on the operating system"""
    system = platform.system()

    print(f"\n🎵 Setting up FFmpeg for {system}...")

    if system == "Windows":
        print("📋 Please follow these steps to install FFmpeg on Windows:")
        print("1. Go to https://ffmpeg.org/download.html")
        print("2. Download the Windows build")
        print("3. Extract to C:\\ffmpeg")
        print("4. Add C:\\ffmpeg\\bin to your PATH environment variable")
        print("\nAlternatively, use chocolatey: choco install ffmpeg")

    elif system == "Darwin":  # macOS
        print("🍎 Installing FFmpeg on macOS...")
        if not run_command("brew --version", "Checking Homebrew"):
            print("📋 Please install Homebrew first:")
            print("Visit: https://brew.sh/")
            return False
        return run_command("brew install ffmpeg", "Installing FFmpeg via Homebrew")

    elif system == "Linux":
        print("🐧 Installing FFmpeg on Linux...")
        # Try different package managers
        commands = [
            ("sudo apt update && sudo apt install -y ffmpeg", "Installing FFmpeg via apt"),
            ("sudo yum install -y ffmpeg", "Installing FFmpeg via yum"),
            ("sudo pacman -S ffmpeg", "Installing FFmpeg via pacman"),
        ]

        for command, description in commands:
            if run_command(command, description):
                return True

        print("❌ Could not install FFmpeg automatically")
        print("Please install FFmpeg manually using your package manager")
        return False

    return True

def verify_installation():
    """Verify that all components are installed correctly"""
    print("\n🔍 Verifying installation...")

    # Check Python packages
    packages = ["discord", "yt_dlp", "spotipy", "aiohttp"]
    for package in packages:
        try:
            __import__(package)
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is not installed")
            return False

    # Check FFmpeg
    if run_command("ffmpeg -version", "Checking FFmpeg"):
        print("✅ FFmpeg is properly installed")
    else:
        print("❌ FFmpeg is not available in PATH")
        return False

    return True

def create_config():
    """Help user create configuration"""
    print("\n⚙️  Configuration Setup")
    print("Please set up your environment variables:")

    if not os.path.exists('.env'):
        print("\n📋 Creating .env file from template...")
        if os.path.exists('.env.example'):
            import shutil
            shutil.copy('.env.example', '.env')
            print("✅ Created .env file")
            print("\n🔧 Please edit .env file with your bot tokens:")
            print("1. DISCORD_TOKEN - Get from https://discord.com/developers/applications")
            print("2. SPOTIFY_CLIENT_ID - Get from https://developer.spotify.com/dashboard")
            print("3. SPOTIFY_CLIENT_SECRET - Get from Spotify developer dashboard")
        else:
            print("❌ .env.example not found")
    else:
        print("✅ .env file already exists")

def main():
    """Main setup function"""
    print("🤖 Discord Music Bot Setup")
    print("=" * 50)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Install Python dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)

    # Setup FFmpeg
    setup_ffmpeg()

    # Verify installation
    if verify_installation():
        print("\n🎉 Setup completed successfully!")
    else:
        print("\n⚠️  Setup completed with warnings")

    # Create config
    create_config()

    print("\n🚀 Next steps:")
    print("1. Edit .env file with your tokens")
    print("2. Run: python discord_music_bot.py")
    print("3. Invite your bot to a Discord server")
    print("4. Use !help to see available commands")

if __name__ == "__main__":
    main()
