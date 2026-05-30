import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('APG app starts on the onboarding screen', (tester) async {
    await tester.pumpWidget(const ApgMobileApp());
    await tester.pump();

    expect(find.text('مرحبًا بك في Arabic Phishing Guard'), findsOneWidget);
    expect(find.text('التالي'), findsOneWidget);
    expect(find.text('تخطي'), findsOneWidget);
  });
}
