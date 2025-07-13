import random
import numpy as np
import copy
from collections import Counter
from pymongo import MongoClient
from bson import ObjectId
import math
import os

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")

# 연결 및 DB/컬렉션 선택
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]  # DB 이름이 정확히 뭔지는 확인 필요
collection = db[MONGO_COLLECTION_NAME]  # 컬렉션 이름도 확인 필요

# 합격자 정보만 가져오기
applicants = list(collection.find({"status": "합격"}))


# 전처리: _id를 str로 변환 (genetic algorithm에서 쓰기 편하게)
for a in applicants:
    a["_id"] = str(a["_id"])

# 예시 출력
print(f"불러온 합격자 수: {len(applicants)}")
missing_field = [a["_id"] for a in applicants if "categorized_abroad_exp" not in a]
print("❗ categorized_abroad_exp 누락된 지원자:", missing_field)

# 다양성 기준에 대한 중요도 가중치
weights = {
    "university" : 5,
    "mbti": 3,
    "categorized_abroad_exp": 2,
    "categorized_club_exp": 2,
    "categorized_hobbies": 1,
    "categorized_immersion_exp": 2,
    "categorized_intern_exp": 2,
    "categorized_major": 2,
    "score": 4
}
def print_group_fitness_details(grouping, applicants_dict, weights):
    print("\n📊 최종 그룹별 Fitness 상세 점수:")

    for i, group in enumerate(grouping):
        group_grouping = [group]  # 단일 그룹만 포함된 리스트
        mbti_score = calculate_mbti_diversity(group_grouping, applicants_dict)
        university_score = calculate_university_diversity(group_grouping, applicants_dict)
        abroad_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_abroad_exp') + calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_abroad_exp')
        club_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_club_exp')+ calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_club_exp')
        hobby_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_hobbies')+ calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_hobbies')
        immersion_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_immersion_exp')+ calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_immersion_exp')
        intern_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_intern_exp')+ calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_intern_exp')
        major_score = calculate_categorical_balance(group_grouping, applicants_dict, 'categorized_major')+ calculate_categorical_entropy(group_grouping, applicants_dict, 'categorized_major')

        devs = [safe_score(applicants_dict[aid].get("dev_score", 0)) for aid in group]
        passions = [safe_score(applicants_dict[aid].get("passion_score", 0)) for aid in group]
        personalities = [safe_score(applicants_dict[aid].get("personality_score", 0)) for aid in group]
        dev_avg, passion_avg, personality_avg = np.mean(devs), np.mean(passions), np.mean(personalities)

        print(f"\n🟦 Group {i+1}")
        print(f"MBTI 다양성: {mbti_score} × {weights['mbti']} = {mbti_score * weights['mbti']}")
        print(f"대학 다양성: {university_score} × {weights['university']} = {university_score * weights['university']}")
        print(f"해외 경험 균형 점수: {abroad_score:.2f} × {weights['categorized_abroad_exp']} = {abroad_score * weights['categorized_abroad_exp']:.2f}")
        print(f"동아리 경험 균형 점수: {club_score:.2f} × {weights['categorized_club_exp']} = {club_score * weights['categorized_club_exp']:.2f}")
        print(f"취미 균형 점수: {hobby_score:.2f} × {weights['categorized_hobbies']} = {hobby_score * weights['categorized_hobbies']:.2f}")
        print(f"몰입 경험 균형 점수: {immersion_score:.2f} × {weights['categorized_immersion_exp']} = {immersion_score * weights['categorized_immersion_exp']:.2f}")
        print(f"인턴 경험 균형 점수: {intern_score:.2f} × {weights['categorized_intern_exp']} = {intern_score * weights['categorized_intern_exp']:.2f}")
        print(f"전공 균형 점수: {major_score:.2f} × {weights['categorized_major']} = {major_score * weights['categorized_major']:.2f}")
        print(f"개발/열정/성격 점수 평균: dev={dev_avg:.2f}, passion={passion_avg:.2f}, personality={personality_avg:.2f}")
        group_total_fitness = ( mbti_score + university_score + abroad_score + club_score + hobby_score + immersion_score + intern_score + major_score )
        print(f"👉 Group {i+1} Total Fitness Score: {group_total_fitness:.2f}")


def fitness(grouping, applicants_dict, weights):
    mbti_score = calculate_mbti_diversity(grouping, applicants_dict)
    university_score = calculate_university_diversity(grouping, applicants_dict)
    abroad_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_abroad_exp') + calculate_categorical_entropy(grouping, applicants_dict, 'categorized_abroad_exp')
    club_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_club_exp')+ calculate_categorical_entropy(grouping, applicants_dict, 'categorized_club_exp')
    hobby_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_hobbies')+ calculate_categorical_entropy(grouping, applicants_dict, 'categorized_hobbies')
    immersion_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_immersion_exp')+ calculate_categorical_entropy(grouping, applicants_dict, 'categorized_immersion_exp')
    intern_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_intern_exp')+ calculate_categorical_entropy(grouping, applicants_dict, 'categorized_intern_exp')
    major_score = calculate_categorical_balance(grouping, applicants_dict, 'categorized_major')+ calculate_categorical_entropy(grouping, applicants_dict, 'categorized_major')
    
    score_balance = calculate_score_std(grouping, applicants_dict)



    # 총점 계산: 각 점수 × int형 가중치
    total_fitness = (
        weights["university"] * university_score + 
        weights["mbti"] * mbti_score +
        weights["categorized_abroad_exp"] * abroad_score +
        weights["categorized_club_exp"] * club_score +
        weights["categorized_hobbies"] * hobby_score +
        weights["categorized_immersion_exp"] * immersion_score +
        weights["categorized_intern_exp"] * intern_score +
        weights["categorized_major"] * major_score +
        weights["score"] * score_balance
    )

    return int(round(total_fitness))

def calculate_university_diversity(grouping, applicants_dict):
    score = 0
    for group in grouping:
        universities = [applicants_dict[aid]["university"] for aid in group]
        unique_universities = set(universities)
        score += len(unique_universities)  # 최대 
    return score

def calculate_mbti_diversity(grouping, applicants_dict):
    score = 0
    for group in grouping:
        mbtis = [applicants_dict[aid]["mbti"] for aid in group]
        unique_mbtis = set(mbtis)
        score += len(unique_mbtis)  # 최대 16
    return score  # 최대값: 4반 × 16 = 64

def calculate_categorical_entropy(grouping, applicants_dict, field):
    entropies = []

    for group in grouping:
        values = [applicants_dict[aid][field] for aid in group]
        total = len(values)
        counts = Counter(values)
        probs = [count / total for count in counts.values()]

        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        entropies.append(entropy)

    # 평균 엔트로피를 반환 (전체 diversity 평가)
    return sum(entropies) / len(entropies)

def calculate_categorical_balance(grouping, applicants_dict, field):
    # 각 반에서 해당 field의 카테고리 분포 확인
    per_group_counters = []
    for group in grouping:
        values = [applicants_dict[aid][field] for aid in group]
        per_group_counters.append(Counter(values))
    
    # 전체 카테고리 목록 확보
    all_categories = set()
    for counter in per_group_counters:
        all_categories.update(counter.keys())
    
    # 각 카테고리별로 반들 간 분포의 분산을 계산 → 낮을수록 점수 높음
    category_variances = []
    for cat in all_categories:
        counts = [counter.get(cat, 0) for counter in per_group_counters]
        category_variances.append(np.var(counts))
    
    # 점수는 음수 분산의 합 (작을수록 좋으니까)
    return -sum(category_variances)

def debug_print_category_distribution(grouping, applicants_dict, field):
    print(f"\n🧩 Field: {field}")
    for i, group in enumerate(grouping):
        values = [applicants_dict[aid][field] for aid in group]
        print(f"Group {i+1}: {dict(Counter(values))}")

def safe_score(val):
    try:
        return int(val)  # 또는 float(val)도 가능
    except:
        return 0  # 변환 안 되면 0으로 대체

def calculate_score_std(grouping, applicants_dict):
    dev_avgs, passion_avgs, personality_avgs = [], [], []

    for group in grouping:
        devs = [safe_score(applicants_dict[aid].get("dev_score", 0)) for aid in group]
        passions = [safe_score(applicants_dict[aid].get("passion_score", 0)) for aid in group]
        personalities = [safe_score(applicants_dict[aid].get("personality_score", 0)) for aid in group]

        dev_avgs.append(np.mean(devs))
        passion_avgs.append(np.mean(passions))
        personality_avgs.append(np.mean(personalities))

    return - (np.std(dev_avgs) + np.std(passion_avgs) + np.std(personality_avgs))


def generate_random_grouping(male_ids, female_ids):
    random.shuffle(male_ids)
    random.shuffle(female_ids)

    grouping = []
    for i in range(4):
        group = male_ids[i*10:(i+1)*10] + female_ids[i*10:(i+1)*10]
        random.shuffle(group)
        grouping.append(group)
    return grouping


def generate_initial_population(applicants, population_size=100):
    male_ids = [a["_id"] for a in applicants if a["gender"] == "남자"]
    female_ids = [a["_id"] for a in applicants if a["gender"] == "여자"]

    population = []
    for _ in range(population_size):
        grouping = generate_random_grouping(male_ids, female_ids)
        population.append(grouping)

    return population



def crossover(parent1, parent2, applicants_dict):
    all_ids = set(sum(parent1, []))
    male_ids = {aid for aid in all_ids if is_male(aid, applicants_dict)}
    female_ids = all_ids - male_ids

    # 부모로부터 일부 그룹 선택
    p1_selected = random.sample(parent1, 2)
    p2_selected = random.sample(parent2, 2)

    child = [list(g) for g in p1_selected + p2_selected]

    used_ids_flat = sum(child, [])
    used_counts = Counter(used_ids_flat)

    # 중복 및 누락 ID 목록
    duplicate_ids = [aid for aid, count in used_counts.items() if count > 1]
    missing_ids = list(all_ids - set(used_ids_flat))

    # 중복 ID 교체 (성별 유지)
    for i in range(4):
        for j in range(len(child[i])):
            current_id = child[i][j]
            if used_counts[current_id] > 1:
                gender = applicants_dict[current_id]["gender"]
                same_gender_missing = [
                    mid for mid in missing_ids if applicants_dict[mid]["gender"] == gender
                ]

                if same_gender_missing:
                    new_id = same_gender_missing.pop()
                    missing_ids.remove(new_id)

                    used_counts[current_id] -= 1
                    child[i][j] = new_id
                    used_counts[new_id] += 1

    # 성비 확인
    for i in range(4):
        males = [aid for aid in child[i] if is_male(aid, applicants_dict)]
        females = [aid for aid in child[i] if not is_male(aid, applicants_dict)]
        assert len(males) == 10 and len(females) == 10, f"성비 오류 in group {i}"

    return child





def mutate(grouping, applicants_dict, num_swaps=1):
    """
    grouping: 4개 그룹 (각 20명) 리스트
    applicants_dict: ID → applicant 정보 딕셔너리
    num_swaps: 성별별 스왑 횟수 (기본 1)
    """
    # 깊은 복사로 원본 훼손 방지
    new_grouping = copy.deepcopy(grouping)

    def get_gender(aid):
        return applicants_dict[aid]["gender"]

    # 그룹 인덱스 조합 리스트
    group_indices = list(range(4))

    for _ in range(num_swaps):
        for gender in ["남자", "여자"]:
            # 그룹 두 개 랜덤 선택
            g1, g2 = random.sample(group_indices, 2)

            # 각 그룹에서 해당 성별 지원자 추출
            g1_candidates = [aid for aid in new_grouping[g1] if get_gender(aid) == gender]
            g2_candidates = [aid for aid in new_grouping[g2] if get_gender(aid) == gender]

            # 스왑 가능할 경우 진행
            if g1_candidates and g2_candidates:
                aid1 = random.choice(g1_candidates)
                aid2 = random.choice(g2_candidates)

                # 실제 스왑
                idx1 = new_grouping[g1].index(aid1)
                idx2 = new_grouping[g2].index(aid2)
                new_grouping[g1][idx1], new_grouping[g2][idx2] = aid2, aid1

    return new_grouping


def is_male(applicant_id, applicants_dict):
    return applicants_dict[applicant_id]["gender"] == "남자"

def tournament_selection(scored_population, k=3):
    competitors = random.sample(scored_population, k)
    competitors.sort(key=lambda x: x[1], reverse=True)
    return competitors[0][0]  # 상위 개체의 grouping만 반환

### ✅ 유전 알고리즘 실행 함수
def genetic_algorithm(applicants, weights, generations=50, population_size=50, elite_size=5, mutation_rate=0.3):
    # 사전 처리
    applicants_dict = {a["_id"]: a for a in applicants}

    population = generate_initial_population(applicants, population_size)

    best_solution = None
    best_fitness = float('-inf')

    for gen in range(generations):
        # 적합도 평가
        scored_population = [
            (grouping, fitness(grouping, applicants_dict, weights))
            for grouping in population
        ]
        scored_population.sort(key=lambda x: x[1], reverse=True)

        # 최고 해 갱신
        if scored_population[0][1] > best_fitness:
            best_solution = scored_population[0][0]
            best_fitness = scored_population[0][1]

        print(f"Generation {gen+1}: Best Fitness = {best_fitness}")

        # 엘리트 보존
        new_population = [grouping for grouping, _ in scored_population[:elite_size]]

        # 교차 + 돌연변이로 개체 생성
        while len(new_population) < population_size:
            parent1 = tournament_selection(scored_population)
            parent2 = tournament_selection(scored_population)
            child = crossover(parent1, parent2,applicants_dict)
            if random.random() < mutation_rate:
                child = mutate(child, applicants_dict)
            new_population.append(child)

        population = new_population

    return best_solution

def print_final_grouping(grouping, applicants_dict):
    for i, group in enumerate(grouping):
        print(f"\n🟦 Group {i+1}")
        for aid in group:
            info = applicants_dict[aid]
            print(f"{info['name']} ({info['gender']}, {info['mbti']}, {info['categorized_major']})")


best_grouping = genetic_algorithm(applicants, weights)
applicants_dict = {a["_id"]: a for a in applicants}
print_final_grouping(best_grouping, applicants_dict)
print_group_fitness_details(best_grouping, applicants_dict, weights)

print("================ 카테고리 분포 확인 ================= ")
debug_print_category_distribution(best_grouping, applicants_dict, "categorized_major")
debug_print_category_distribution(best_grouping, applicants_dict, "categorized_abroad_exp")
debug_print_category_distribution(best_grouping, applicants_dict, "categorized_hobbies")