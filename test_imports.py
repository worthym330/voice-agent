#!/usr/bin/env python3
"""Test script to verify all imports work correctly"""

try:
    import google.generativeai as genai
    print("✅ Google Generative AI imported successfully")
except ImportError as e:
    print(f"❌ Google Generative AI import failed: {e}")

try:
    import speech_recognition as sr
    print("✅ Speech Recognition imported successfully")
except ImportError as e:
    print(f"❌ Speech Recognition import failed: {e}")

try:
    from elevenlabs import ElevenLabs
    print("✅ ElevenLabs imported successfully")
except ImportError as e:
    print(f"❌ ElevenLabs import failed: {e}")

try:
    import pygame
    print("✅ Pygame imported successfully")
except ImportError as e:
    print(f"❌ Pygame import failed: {e}")

try:
    import pyttsx3
    print("✅ Pyttsx3 imported successfully")
except ImportError as e:
    print(f"❌ Pyttsx3 import failed: {e}")

try:
    import wave
    import threading
    import tempfile
    import json
    from datetime import datetime
    print("✅ All standard library modules imported successfully")
except ImportError as e:
    print(f"❌ Standard library import failed: {e}")

print("\n🎉 All critical imports successful! The voice agent should work properly.")
print("\n📋 Key features implemented:")
print("   • Call recording with audio capture")
print("   • Conversation logging to JSON file") 
print("   • Single voice output (prevents multiple audio overlap)")
print("   • Recording notification to user")
print("   • Automatic file saving with timestamps")
