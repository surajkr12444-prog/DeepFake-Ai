import requests
import json
import base64
import numpy as np
import cv2
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = 'http://localhost:8050'

print('========================================')
print('TESTING DEEPSHIELD BACKEND API ENDPOINTS')
print('========================================\n')

# 1. Test /api/status
r = requests.get(f'{BASE_URL}/api/status')
print(f'1. GET /api/status -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 200

# 2. Test /api/settings
r = requests.get(f'{BASE_URL}/api/settings')
print(f'\n2. GET /api/settings -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 200

# 3. Test POST /api/settings (Valid update)
r = requests.post(f'{BASE_URL}/api/settings', json={'similarity_threshold': 0.65})
print(f'\n3. POST /api/settings (valid 0.65) -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 200

# 4. Test POST /api/settings (Invalid threshold > 1.0)
r = requests.post(f'{BASE_URL}/api/settings', json={'similarity_threshold': 1.5})
print(f'\n4. POST /api/settings (invalid 1.5) -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 400

# 5. Test /api/stats
r = requests.get(f'{BASE_URL}/api/stats')
print(f'\n5. GET /api/stats -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 200

# 6. Test /api/logs
r = requests.get(f'{BASE_URL}/api/logs?limit=5')
print(f'\n6. GET /api/logs?limit=5 -> Status: {r.status_code}')
data = r.json()
print(f'   Total records in log: {data.get("total_records")}, returned: {len(data.get("logs", []))}')
print('   Sample row:', data['logs'][0] if data.get('logs') else 'None')
assert r.status_code == 200

# 7. Test POST /api/logs
new_entry = {'confidence': 88, 'label': 'Authentic (88%)', 'mean_liveness_sim': 0.997}
r = requests.post(f'{BASE_URL}/api/logs', json=new_entry)
print(f'\n7. POST /api/logs -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 200

# 8. Test POST /api/detect with simulated camera frame
test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.rectangle(test_frame, (0, 0), (640, 480), (40, 30, 20), -1)
cv2.ellipse(test_frame, (320, 240), (100, 130), 0, 0, 360, (140, 170, 210), -1)
cv2.circle(test_frame, (280, 210), 12, (20, 20, 20), -1)
cv2.circle(test_frame, (360, 210), 12, (20, 20, 20), -1)
cv2.line(test_frame, (290, 290), (350, 290), (30, 40, 160), 4)
_, buffer = cv2.imencode('.jpg', test_frame)
b64_frame = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')

r = requests.post(f'{BASE_URL}/api/detect', json={'image_base64': b64_frame, 'threshold': 0.60})
print(f'\n8. POST /api/detect (with valid synthetic frame) -> Status: {r.status_code}')
detect_res = r.json()
print('   Face detected:', detect_res['face_detected'])
print('   Label:', detect_res['label'])
print('   Confidence:', detect_res['confidence'], '%')
print('   Liveness Score:', detect_res['liveness_score'], '%')
print('   BBox:', detect_res['bbox'])
print('   Landmarks:', len(detect_res['landmarks']), 'points')
assert r.status_code == 200

# 9. Test POST /api/detect with corrupted base64 data
r = requests.post(f'{BASE_URL}/api/detect', json={'image_base64': 'invalid_garbage_base64'})
print(f'\n9. POST /api/detect (corrupted data) -> Status: {r.status_code}')
print('   Response:', r.json())
assert r.status_code == 400

# 10. Test GET /api/export_csv
r = requests.get(f'{BASE_URL}/api/export_csv')
print(f'\n10. GET /api/export_csv -> Status: {r.status_code}, Content-Type: {r.headers.get("content-type")}')
print(f'    CSV snippet: {r.text[:80]}...')
assert r.status_code == 200

# 11. Test POST /api/report
r = requests.post(f'{BASE_URL}/api/report')
print(f'\n11. POST /api/report -> Status: {r.status_code}')
print('    Response:', r.json())
assert r.status_code == 200

# 12. Test GET / (Frontend serving)
r = requests.get(f'{BASE_URL}/')
print(f'\n12. GET / (Frontend root) -> Status: {r.status_code}')
print(f'    Contains DeepShield title: {"DeepShield" in r.text}')
assert r.status_code == 200

# 13. Test GET /non_existent_page (404 handling)
r = requests.get(f'{BASE_URL}/non_existent_page')
print(f'\n13. GET /non_existent_page -> Status: {r.status_code}')
assert r.status_code == 404

print('\n========================================')
print('ALL 13 API / BACKEND TESTS PASSED 100%!')
print('========================================')
