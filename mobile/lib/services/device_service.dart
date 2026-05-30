import 'local_storage_service.dart';

class DeviceService {
  const DeviceService();

  String get deviceId => LocalStorageService.instance.getOrCreateDeviceId();

  Map<String, dynamic> metadata() => {
    'device_id': deviceId,
    'device_name': 'APG Mobile',
    'platform': 'mobile',
    'app_version': '1.0.0',
  };
}
