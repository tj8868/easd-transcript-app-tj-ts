import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def build_android_apk_bundle():
    print("=== Generating Android APK Package Configuration & Generator ===")
    
    # 1. Generate Capacitor / Android TWA manifest configuration
    twa_config = {
        "package_name": "com.easd.meetingminutes",
        "app_name": "EASD Meeting Assistant",
        "version_name": "1.0.0",
        "version_code": 1,
        "theme_color": "#6366f1",
        "background_color": "#0f172a",
        "start_url": "http://localhost:8000/",
        "features": {
            "file_upload": True,
            "offline_pwa": True,
            "gdrive_sync": True
        }
    }
    
    config_path = os.path.join(BASE_DIR, "android_package_config.json")
    with open(config_path, "w") as f:
        json.dump(twa_config, f, indent=2)
    print(f"[SUCCESS] Created Android configuration: {config_path}")

    # 2. Create automated Android APK build instructions & shell script
    apk_script_content = f"""@echo off
title Android APK Package Generator
echo ========================================================
echo   EASD Meeting Minutes - Android APK Build Script
echo ========================================================
echo 1. Ensure Node.js and Java JDK / Android SDK are installed.
echo 2. Option A (PWABuilder / Bubblewrap CLI):
echo    npx @bubblewrap/cli build --manifest=http://localhost:8000/manifest.json
echo 3. Option B (Capacitor Android wrapper):
echo    npm install @capacitor/core @capacitor/cli @capacitor/android
echo    npx cap init "EASD Meeting Assistant" com.easd.meetingminutes --web-dir static
echo    npx cap add android
echo    npx cap open android
echo ========================================================
pause
"""
    apk_bat_path = os.path.join(BASE_DIR, "Build_Android_APK.bat")
    with open(apk_bat_path, "w") as f:
        f.write(apk_script_content)
    print(f"[SUCCESS] Created Android APK Build script: {apk_bat_path}")

if __name__ == "__main__":
    build_android_apk_bundle()
