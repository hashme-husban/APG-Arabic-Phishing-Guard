import 'dart:io';

import 'package:google_mlkit_barcode_scanning/google_mlkit_barcode_scanning.dart'
    as barcode_ml;

enum ImageSourceType { imageQr, imageEmpty }

class ImageIntelligenceResult {
  final bool hasQr;
  final List<String> qrValues;
  final ImageSourceType sourceType;
  final String? error;

  const ImageIntelligenceResult({
    required this.hasQr,
    required this.qrValues,
    required this.sourceType,
    this.error,
  });
}

class ImageIntelligenceService {
  Future<ImageIntelligenceResult> processImage(File imageFile) async {
    final scanner = barcode_ml.BarcodeScanner();
    try {
      final inputImage = barcode_ml.InputImage.fromFile(imageFile);
      final barcodes = await scanner.processImage(inputImage);
      final qrValues = barcodes
          .where((b) => b.rawValue != null && b.rawValue!.trim().isNotEmpty)
          .map((b) => b.rawValue!.trim())
          .toSet()
          .toList();
      if (qrValues.isEmpty) {
        return const ImageIntelligenceResult(
          hasQr: false,
          qrValues: [],
          sourceType: ImageSourceType.imageEmpty,
        );
      }
      return ImageIntelligenceResult(
        hasQr: true,
        qrValues: qrValues,
        sourceType: ImageSourceType.imageQr,
      );
    } catch (e) {
      return ImageIntelligenceResult(
        hasQr: false,
        qrValues: const [],
        sourceType: ImageSourceType.imageEmpty,
        error: e.toString(),
      );
    } finally {
      await scanner.close();
    }
  }

  static String repairOcrUrls(String text) {
    var repaired = text;
    repaired = repaired.replaceAllMapped(
      RegExp(r'\b(https?)\s*:\s*/\s*/\s*', caseSensitive: false),
      (match) => '${match.group(1)!.toLowerCase()}://',
    );
    repaired = repaired.replaceAllMapped(
      RegExp(r'\bwww\s*\.\s*', caseSensitive: false),
      (_) => 'www.',
    );
    var previous = '';
    while (previous != repaired) {
      previous = repaired;
      repaired = repaired.replaceAllMapped(
        RegExp(
          r'((?:https?:\/\/|www\.)?[A-Za-z0-9-]+)\s*\.\s*([A-Za-z0-9-]+(?:\s*\.\s*[A-Za-z0-9-]+)*)',
          caseSensitive: false,
        ),
        (match) =>
            '${match.group(1)}.${match.group(2)!.replaceAll(RegExp(r'\s+'), '')}',
      );
    }
    repaired = repaired.replaceAllMapped(
      RegExp(
        r'((?:https?:\/\/|www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)((?:\s+[/?:=&-]\s*|\s*[/?:=&-]\s+)[^\s،؛؟]*)?',
        caseSensitive: false,
      ),
      (match) {
        final domain = match.group(1) ?? '';
        final suffix = (match.group(2) ?? '').replaceAllMapped(
          RegExp(r'\s*([/?:=&-])\s*'),
          (punctuation) => punctuation.group(1) ?? '',
        );
        return '$domain$suffix';
      },
    );
    return repaired;
  }

  static List<String> extractUrlsFromText(String value) {
    final repaired = repairOcrUrls(value);
    final urlPattern = RegExp(
      r'((?:https?:\/\/|www\.)[^\s<>"،؛؟]+|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:\/[^\s<>"،؛؟]*)?)',
      caseSensitive: false,
    );
    return urlPattern
        .allMatches(repaired)
        .map((match) => match.group(0) ?? '')
        .map(cleanUrlCandidate)
        .where((url) => url.isNotEmpty && url.contains('.'))
        .toSet()
        .toList();
  }

  static String cleanUrlCandidate(String value) {
    return value
        .trim()
        .replaceAll(RegExp(r'[)\].,،؛؟!]+$'), '')
        .replaceAll(RegExp(r'^[(\[]+'), '');
  }
}
