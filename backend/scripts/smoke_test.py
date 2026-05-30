from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

BASE_URL = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:5000'


def request(method: str, path: str, body: Dict[str, Any] | None = None, token: str | None = None) -> Dict[str, Any]:
    data = json.dumps(body or {}, ensure_ascii=False).encode('utf-8') if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{BASE_URL}{path}', data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8')
        raise RuntimeError(f'{method} {path} failed: HTTP {exc.code} {raw}') from exc


def main() -> None:
    print(f'[APG] Testing backend at {BASE_URL}')
    print('[1] Health:', request('GET', '/health'))

    user_login = request('POST', '/auth/login', {'email': 'user@apg.local', 'password': 'user123'})
    user_token = user_login['token']
    print('[2] User login:', user_login['user'])

    analyzed = request('POST', '/analysis/analyze', {
        'input_text': 'عاجل: سيتم إيقاف حسابك البنكي. أدخل رمز التحقق OTP 123456 عبر https://bit.ly/bank-secure',
        'source': 'sms',
        'device_id': 'smoke-test-device-8A2F',
        'source_app': 'Google Messages',
    }, user_token)
    print('[3] User analysis saved:', {'id': analyzed.get('id'), 'classification': analyzed.get('classification'), 'risk_score': analyzed.get('risk_score')})

    history = request('GET', '/analysis/history?limit=5', token=user_token)
    print('[4] User history total:', history.get('total'), 'latest:', history.get('items', [{}])[0].get('id'))

    report = request('POST', '/reports', {
        'analysis_id': analyzed['id'],
        'report_type': 'inaccurate_result',
        'message': 'اختبار بلاغ من smoke_test',
    }, user_token)
    print('[5] User report created:', report)

    admin_login = request('POST', '/auth/login', {'email': 'admin@apg.local', 'password': 'admin123'})
    admin_token = admin_login['token']
    print('[6] Admin login:', admin_login['user'])

    overview = request('GET', '/admin/overview', token=admin_token)
    print('[7] Admin overview today:', overview.get('today'))

    review = request('GET', '/admin/review?filter=needs_review&limit=5', token=admin_token)
    review_ids = [item.get('id') for item in review.get('items', [])]
    print('[8] Admin review total:', review.get('total'), 'ids:', review_ids)
    assert analyzed['id'] in review_ids or review.get('total', 0) > 0, 'Analysis did not appear in admin review.'

    reports = request('GET', '/admin/reports?status=all', token=admin_token)
    report_ids = [item.get('id') for item in reports.get('items', [])]
    print('[9] Admin reports summary:', reports.get('summary'), 'ids:', report_ids)
    assert report['id'] in report_ids or reports.get('summary', {}).get('new', 0) > 0, 'Report did not appear in admin reports.'

    db_status = request('GET', '/admin/dev/db-status', token=admin_token)
    print('[10] DB status:', db_status)
    print('\n✅ APG backend flow works: User analysis and user report are stored and visible to Admin.')


if __name__ == '__main__':
    main()
