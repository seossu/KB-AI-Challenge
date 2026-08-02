import os
import json
import subprocess
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pydantic 클래스 정의 
class ExtractedData(BaseModel):
    purpose: str | None = None
    business_type: str | None = None
    capital: int | None = Field(default=None, description="자본금 (숫자)")
    preferred_region: str | None = Field(default=None, description="선호 지역 (문자열)")
    store_size_pyeong: float | None = Field(default=None, description="매장 크기 평수 (숫자)")
    
    target_customer: str | None = None
    priority: list[str] | None = Field(default=None, description="우선순위 영문 배열")
    parking: bool | None = None
    public_transport: bool | None = None

class ConsultingResponse(BaseModel):
    extracted_data: ExtractedData
    next_question: Optional[str] = Field(default=None, description="누락된 정보를 묻는 질문")
    ready_to_proceed: bool = Field(default=False, description="추천을 바로 진행하길 원하거나 모든 정보를 다 받아 종료해도 되면 true")


# 시스템 프롬프트 
chat_history = [
    {"role": "system", "content": """
    당신은 창업 입지 컨설팅 에이전트입니다.
    사용자의 입력에서 상권 분석에 필요한 9가지 정보를 추출하세요.

    [행동 지침 - 매우 중요]
    1. 정보 누적 (Accumulation): 대화가 진행됨에 따라 이전 대화에서 이미 추출한 정보는 절대 지우지 말고 계속 유지 및 업데이트해야 합니다. 없는 정보는 `null`로 처리하세요.

    2. 유연한 대화와 문맥 파악 (Context Awareness):
       - 사용자가 한 번의 대답에 여러 정보("합정에 5억으로 애플스토어 낼거야")를 제공하면, 문맥을 파악해 해당되는 필드를 모두 한 번에 채우세요.
       - 사용자가 "지금까지 모인 정보가 뭐야?", "무슨 질문이었지?", "내가 뭐라고 했지?" 등 되묻거나 딴청을 피우면, 절대 그냥 다음 빈칸을 묻지 마세요. 반드시 `next_question` 필드의 문장 맨 앞에서 사용자의 질문에 먼저 답한 뒤(지금까지 취합된 정보를 나열), 이어서 다음 질문을 붙이세요. (예: "지금까지 취합된 정보는 업종(애플스토어), 지역(합정), 자본금(5억원)입니다. 이제 매장 평수를 알려주시겠어요?")

    3. 대화 단계 및 질문(next_question) 생성 규칙:
       - 1단계 (필수 수집): 필수 5가지 정보(purpose, business_type, capital, preferred_region, store_size_pyeong) 중 하나라도 `null`이라면 부족한 정보를 가장 먼저 물어보세요.
       - 2단계 (선택 수집 및 남은 항목 안내): 필수 5가지 정보가 모두 채워진 이후부터는, 하나씩 꼬치꼬치 묻지 마세요. 대신 사용자에게 진행 여부를 묻고, 문장 끝에 괄호 안에서 현재 `null`로 비어있는 항목들의 이름(한국어)을 나열해 주세요. (최초 1번만 나열)
         (예시 포맷: "이대로 추천을 진행할까요? 아니면 추가적인 정보를 더 입력하시겠어요? (ex. 매장 크기, 주차 여부, 타겟층, 대중교통, 우선순위)")
       - 3단계 (반복 안내): 사용자가 선택 정보를 일부만 대답했다면, 해당 정보를 반영한 뒤 계속 진행 여부를 물어보세요. null인 항목을 다시 리스트업 하지 마세요.
         이후부터도 종목을 캐묻지 말고 아래 질문 정도로만 안내하세요. 
         (예시: "주차 공간 50평 조건 반영했습니다! 이대로 진행할까요? 아니면 더 입력하시겠어요?")

    4. 종료 조건 (ready_to_proceed 설정):
       - 사용자가 "그냥 이대로 추천해줘", "괜찮아", "없어", "바로 진행해" 등 추가 정보 입력을 원하지 않는 의사를 밝히거나,
       - 총 9개의 모든 정보가 꽉 차서 더 이상 남은 항목이 없다면,
       - `ready_to_proceed`를 true로 설정하고 `next_question`은 null로 비워두세요.
       - 그 외의 모든 대화 진행 중에는 `ready_to_proceed`를 false로 유지하세요.

    [추출해야 할 JSON 키 값 및 데이터 타입 규칙 - 엄격히 준수]
        1. purpose (필수): 창업, 확장 등 (문자열, 문맥으로 자동 추론)
        2. business_type (필수): 업종 (문자열)
        3. capital (필수): 자본금. 반드시 순수 '정수(int)'로 출력 (예: 50000000)
        4. preferred_region (필수): 선호 지역 (문자열, 예: "성동구")
        5. store_size_pyeong (필수): 매장 크기. 평 단위의 '숫자(float)'로 출력 (예: 20.0)
        6. target_customer (선택): 타겟 고객층 (문자열, 예: "2030 직장인")
        7. priority (선택): 우선순위. 반드시 [foot_traffic, low_rent, low_competition, transit, residential_base] 중 해당하는 것만 배열에 넣을 것
        8. parking (선택): 주차 가능 여부 (boolean)
        9. public_transport (선택): 대중교통 접근성 중시 여부 (boolean)

    [금액 변환 필수 규칙]
        - 사용자가 입력한 자본금, 자금 등은 반드시 '원' 단위의 정확한 정수로 변환하여 추출해야 합니다.
        - 예시: "3억" -> 300000000, "3000만" -> 30000000, "1억 5천" -> 150000000
        - '만' 단위나 '억' 단위 변환 시 0의 개수를 절대 누락하지 마세요.

    [출력 JSON 포맷]
    반드시 아래의 중첩된(Nested) JSON 구조를 엄격하게 지켜서 출력하세요.
    {
      "extracted_data": {
        "purpose": "...",
        "business_type": "...",
        "capital": 100000000,
        "preferred_region": "...",
        "store_size_pyeong": 15.0,
        "target_customer": null,
        "priority": null,
        "parking": null,
        "public_transport": null
      },
      "next_question": "질문 내용 또는 null",
      "ready_to_proceed": false
    }
    """}
]

# 메인 대화 루프
while True:
    user_input = input("\n사용자 (종료하려면 'q' 입력): ")
    if user_input.strip().lower() in ['q', 'quit', 'exit', '종료']:
        print("대화를 종료합니다.")
        break
        
    chat_history.append({"role": "user", "content": user_input})
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=chat_history,
        response_format={ "type": "json_object" } 
    )
    
    ai_message = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": ai_message})
    
    # Pydantic을 이용한 자동 형변환 및 검증
    try:
        parsed_response = ConsultingResponse.model_validate_json(ai_message)
        
        # AI가 종료해도 좋다고 판단했는지 (ready_to_proceed) 확인
        if parsed_response.ready_to_proceed:
            print("\nAI: 네, 알겠습니다! 취합된 정보를 바탕으로 맞춤형 입지 추천을 시작합니다... ⚙️")
            
            # 1. AI가 파싱한 9개의 데이터를 딕셔너리로 변환
            final_data = parsed_response.extracted_data.model_dump(exclude_none=True)
            
            # 2. 팀원 코드 에러 방지를 위해 desired_loan을 0으로 명시적 추가
            final_data["desired_loan"] = 0
            
            # 3. JSON 임시 저장
            output_json_path = "data/ai_input.json"
            os.makedirs("data", exist_ok=True)
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            print(f"\n[시스템] 사용자 데이터가 {output_json_path}에 저장되었습니다.\n")
            print("-" * 50)
            
            # 4. 저장된 JSON 파일을 이용해 팀원의 메인 스크립트 실행
            try:
                subprocess.run(["python", "scripts/run_request.py", output_json_path])
            except Exception as e:
                print(f"[시스템 에러] 팀원 코드를 실행하는 중 문제가 발생했습니다: {e}")
            
            print("-" * 50)
            break
            
        else:
            # AI가 만들어준 질문 출력
            question_to_ask = parsed_response.next_question
            if not question_to_ask:
                question_to_ask = "추가로 알려주실 정보가 있나요?"
            print(f"\nAI: {question_to_ask}")
            
    except ValidationError as e:
        print(f"\n[시스템 에러] AI가 잘못된 형식의 데이터를 생성했습니다: {e}")
    except Exception as e:
        print(f"\nAI: 응답을 처리하는 중 오류가 발생했습니다. 다시 말씀해 주시겠어요? (에러: {e})")