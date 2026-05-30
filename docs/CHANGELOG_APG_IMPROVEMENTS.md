# APG Improvements Changelog

## Critical Fixes

- Replaced the stale Flutter counter test that referenced `MyApp` with an APG onboarding smoke test.
- Changed Android namespace and application ID from `com.example.mobile` to `com.apg.arabicphishingguard`.
- Changed Android app label from `mobile` to `APG`.
- Moved `MainActivity` to the matching APG Kotlin package path.
- Added clear Android manifest note that cleartext HTTP is for local demo only.
- Verified core Arabic UI/localization files are valid UTF-8; visible Arabic copy remains readable and professional.
- Forced UTF-8 stdout in backend demo scripts so Arabic JSON output does not crash on Windows consoles.

## UI/UX Improvements

- Improved demo login language by using "مشرف" instead of informal admin wording in visible Arabic copy.
- Removed decorative orb backgrounds and kept a calmer cybersecurity-style grid/background treatment.
- Added a Settings privacy note explaining local history/notification storage risk.
- Improved notification permission wording to clarify Android-only access and monitored-app scope.
- Added manual "Analyze this notification" action for raw captured notifications.
- Kept high-risk result guidance focused on clear user actions such as not clicking links or sharing OTPs.
- Removed negative letter spacing from edited UI surfaces.

## Backend/API Improvements

- Hardened `/analyze` validation for `urls` and `metadata`.
- Removed raw exception details from default 500 responses.
- Added `APG_DEBUG_ERRORS=1` escape hatch for local debugging.
- Improved Flutter API client handling of backend error messages.
- Added user-friendly mapping for new backend validation errors.

## Documentation

- Added root `README.md` with setup, architecture, demo accounts, API URL notes, notification permission steps, limitations, and troubleshooting.
- Added `DEMO_GUIDE.md` with a step-by-step presentation script and sample Arabic messages.
- Added `APG_FINAL_CHECKLIST.md` for final demo readiness.
- Added root `requirements.txt` for backend dependency setup.

## Tests

- Added a Flutter widget smoke test that pumps `ApgMobileApp` and verifies Arabic onboarding UI appears.

## Known Remaining Limitations

- Authentication is still local demo-only.
- Admin dashboard is still local/demo, not production backend telemetry.
- Local history and notification inbox are not encrypted.
- Cleartext HTTP remains enabled for local Flask demo.
- Notification listener remains Android-only.
- Production release signing is not configured.
