import sys

# 현재 실행 중인 파이썬 버전 출력
print(f"현재 파이썬 버전: {sys.version}")

# 데이터 정제 예시 리스트
raw_data = ["  강원도 춘천시 ", "강원도 원주시", " 강원도 강릉시  ", None, ""]

# 데이터 정제 (공백 제거 및 빈 값 제외)
cleaned_data = [item.strip() for item in raw_data if item and item.strip()]

print("\n--- 정제된 데이터 목록 ---")
for idx, region in enumerate(cleaned_data, 1):
    print(f"{idx}. {region}")