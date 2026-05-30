# APG Smoke Test Checklist

Use this checklist before launch or after deployment changes.

## Authentication

- Register a new user with a real email address.
- Confirm the user receives the APG verification email.
- Verify the email using the 6 digit code.
- Log in with the verified account.
- Log out and confirm the app returns to the login screen.
- Confirm an unverified account cannot log in until verified.
- Confirm admin/demo accounts still work as expected.

## Analysis

- Analyze a clearly safe message and confirm it does not escalate.
- Analyze a suspicious message and confirm it returns needs verification.
- Analyze a dangerous phishing message with a fake login/payment URL and confirm it escalates.
- Confirm result reasons match the strongest evidence shown to the user.

## History And Isolation

- Log in as user A and create at least one analysis result.
- Log out.
- Log in as user B on the same device.
- Confirm user B does not see user A local history.
- Delete a history item for one user and confirm it does not suppress another user's history.

## Monitoring

- Request notification monitoring permission on Android.
- Confirm monitored notifications are captured only after permission is granted.
- Confirm disabling monitoring stops new notification analysis.

## Release Build

- Build the release APK/AAB.
- Launch the release build on a clean device.
- Confirm no raw server IPs, localhost URLs, ports, or internal API addresses are visible to end users.
- Confirm registration, email verification, login, logout, analysis, history sync, and monitoring still work.
