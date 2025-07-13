from pymongo import MongoClient
from bson import ObjectId

# MongoDB 연결
client = MongoClient("mongodb+srv://dldmsals3:eunmin03!!@campteammakercluster.yikpgdv.mongodb.net/?retryWrites=true&w=majority&appName=campTeamMakerCluster")

# 데이터베이스 및 컬렉션 선택
db = client["molipDB"]
collection = db["participants"]

# 어떤 문서를 수정할지 조건 설정 (예: 이름이 이승민인 문서)
query = {
    "_id": ObjectId("6871154e823f5ecec19818cc")
}
# 새로 추가하고 싶은 내용
new_fields = {
    "$set":  { "avg_score": 90.0,
  "categorized_abroad_exp": "North America",
  "categorized_club_exp": "art",
  "categorized_hobbies": "학문",
  "categorized_immersion_exp": "자기개발",
  "categorized_intern_exp": "ai",
  "categorized_major": "자연",
  "dev_score": 89,
  "dev_score_reason": "CS 과목을 고르게 이수했으며 Django 기반의 실전 프로젝트, 자연어처리 연구실 인턴 경험을 보유하고 있어 실전 감각과 응용력이 우수함.",
  "passion_score": 91,
  "passion_score_reason": "러닝 루틴과 독서 습관 등 자기관리에서 강한 의지가 드러나며, 영상 제작 및 봉사 등 다양한 활동에 꾸준히 참여해 실행력과 몰입력 모두 우수함.",
  "personality_score": 90,
  "personality_score_reason": "해외 봉사와 협업 기반의 단편영화 제작 등에서 공감 능력과 팀워크가 잘 드러났으며, 진정성 있는 커뮤니케이션 태도를 보여줌."
}
}

# 문서 업데이트 (필드가 없으면 새로 추가됨)
collection.update_one(query, new_fields)
result = collection.update_one(query, new_fields)

if result.matched_count == 0:
    print("❗ 일치하는 문서를 찾지 못했어요. _id가 맞는지 확인해주세요.")
elif result.modified_count == 0:
    print("⚠️ 문서는 찾았지만, 변경된 내용이 없습니다. 이미 같은 값일 수도 있어요.")
else:
    print("✅ 필드 추가 완료!")

