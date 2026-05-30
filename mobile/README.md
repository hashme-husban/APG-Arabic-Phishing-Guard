# APG Flutter Mobile

The API base URL is centralized in `lib/config/app_config.dart` and read from:

```dart
APG_API_BASE_URL
```

Default server:

```text
http://YOUR_SERVER_IP/api
```

Run from this `mobile` folder:

```bash
flutter clean
flutter pub get
flutter run --dart-define=APG_API_BASE_URL=http://YOUR_SERVER_IP/api
```

Build a release APK:

```bash
flutter build apk --release --dart-define=APG_API_BASE_URL=http://YOUR_SERVER_IP/api
```

Android Studio: open Run/Debug Configurations and add this to Additional run args:

```text
--dart-define=APG_API_BASE_URL=http://YOUR_SERVER_IP/api
```
