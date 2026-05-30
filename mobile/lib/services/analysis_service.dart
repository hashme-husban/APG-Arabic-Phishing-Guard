import '../models/analysis_history_item.dart';
import '../models/analysis_result.dart';
import 'apg_api_service.dart';

class AnalysisService {
  const AnalysisService({this.api = const ApgApiService()});
  final ApgApiService api;

  Future<AnalysisResult> analyze({
    required String inputText,
    String source = 'manual',
    String sender = '',
  }) {
    return api.analyze(rawText: inputText, channel: source, sender: sender);
  }

  Future<List<AnalysisHistoryItem>> history({
    String classification = 'all',
    String source = 'all',
    String search = '',
    int page = 1,
    int limit = 20,
  }) {
    return api.fetchHistory(
      classification: classification,
      source: source,
      search: search,
      page: page,
      limit: limit,
    );
  }
}
