import 'apg_api_service.dart';

class ReportsService {
  const ReportsService({this.api = const ApgApiService()});
  final ApgApiService api;

  Future<void> create({
    required String analysisId,
    required String reportType,
    required String message,
  }) {
    return api.submitReport(
      analysisId: analysisId,
      reportType: reportType,
      message: message,
    );
  }
}
