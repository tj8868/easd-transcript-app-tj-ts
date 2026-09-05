@echo off
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
