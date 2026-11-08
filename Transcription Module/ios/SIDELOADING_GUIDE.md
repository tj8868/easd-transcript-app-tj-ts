# iPhone Sideloading & Offline Installation Guide
*(Bypassing the App Store without Paid Developer Accounts)*

This guide provides three practical pathways to install and run offline speech-to-text (Bangla & English) on an iPhone without relying on Apple App Store approvals.

---

## Method 1: Progressive Web App (PWA) via WebGPU *(Easiest & Most Reliable)*

This method requires **zero sideloading tools, no computer tethering, and never expires**.

### How it Works:
1. iOS 17+ Safari natively supports **WebGPU** and **CacheStorage**.
2. Whisper models run inside Safari using WebGPU matrix multiplication (compiled directly to Apple Metal shaders).
3. The model and web assets are cached inside the iPhone's `IndexedDB` and `CacheStorage`. Once loaded, it works **completely offline with Airplane Mode turned ON**.

### Steps to Install on iPhone:
1. Host `pwa_offline_transcriber.html` locally or deploy it to a free host like GitHub Pages, Cloudflare Pages, or Vercel.
2. Open the URL in **Safari** on your iPhone.
3. Tap the **Share** button (the square with an arrow pointing up at the bottom of the screen).
4. Scroll down and tap **"Add to Home Screen"**.
5. Tap **Add**.
6. An app icon will now appear on your iPhone's home screen. Launching it opens a full-screen, standalone app with zero browser toolbars.

---

## Method 2: Sideloading via SideStore *(Native Apple Neural Engine Speed)*

If you want maximum performance by running native Swift + CoreML code on the **Apple Neural Engine (ANE)**, you can sideload native `.ipa` builds without paying for an Apple Developer Account.

### Why SideStore instead of AltStore?
* Traditional AltStore requires your iPhone to be on the same local Wi-Fi network as a running computer every 7 days to refresh certificates.
* **SideStore** only requires a computer for the initial 5-minute install. Afterwards, it self-refreshes app certificates **directly on the phone** using a local loopback WireGuard VPN.

### Prerequisites:
* A free personal Apple ID.
* A computer (Mac or Windows/Linux) for initial setup only.
* Native Whisper IPA (e.g., compiled from [WhisperKit](https://github.com/argmaxinc/WhisperKit) or [whisper.cpp iOS](https://github.com/ggerganov/whisper.cpp/tree/master/examples/whisper.swiftui)).

### Initial Setup Steps:
1. Download **SideServer** on your computer from [sidestore.io](https://sidestore.io).
2. Connect your iPhone to your computer via USB cable.
3. In SideServer, choose **"Install SideStore"** and enter your free Apple ID credentials.
4. On your iPhone:
   - Go to **Settings > General > VPN & Device Management** and trust your Developer App certificate.
   - On iOS 16+, go to **Settings > Privacy & Security > Developer Mode** and toggle it **ON** (restarts device).
5. Open the SideStore app on your iPhone and set up the local WireGuard pairing file following the in-app prompt.

### Installing Your Transcription App:
1. Download or transfer your `.ipa` file to the iPhone (via AirDrop, iCloud Drive, or Files app).
2. Open **SideStore** on the iPhone.
3. Tap the **`+`** icon in the top left corner.
4. Select your `.ipa` file.
5. SideStore signs and installs the app directly to your home screen.
6. The app now runs with native Apple Neural Engine speed. SideStore will auto-refresh the 7-day timer in the background whenever you are connected to Wi-Fi.

---

## Method 3: Internal TestFlight *(Best for Teams up to 100 Devices)*

If you or your organization has a standard Apple Developer account ($99/year), you do **not** need App Store review for team deployment:

1. In **App Store Connect**, upload your build via Xcode.
2. Go to **TestFlight > Internal Testing**.
3. Create an internal group and add up to **100 internal testers** by email.
4. **No Apple review is performed** for internal testing builds.
5. Users receive an invitation email, install TestFlight from the App Store, and install your build with 1 tap.
6. Each build remains active on devices for **90 days**.

---

## Summary Recommendation

* **For Instant, Effortless Deployment (Anyone with an iPhone):** Use **Method 1 (PWA)**. Works instantly, no computer required, no certificate renewals.
* **For Maximum Performance (Apple Neural Engine / CoreML):** Use **Method 2 (SideStore)**.
