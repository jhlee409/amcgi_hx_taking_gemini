import streamlit as st
import sqlite3
from docx import Document
import io
import google.generativeai as genai
import requests

# Set up the model
generation_config = {
  "temperature": 0.1,
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 2048,
}

safety_settings = [
  {
    "category": "HARM_CATEGORY_HARASSMENT",
    "threshold": "BLOCK_NONE"
  },
  {
    "category": "HARM_CATEGORY_HATE_SPEECH",
    "threshold": "BLOCK_NONE"
  },
  {
    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "threshold": "BLOCK_NONE"
  },
  {
    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
    "threshold": "BLOCK_NONE"
  },
]

# Initialize Gemini-Pro
api_key = st.secrets["genai_api_key"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# Set page to wide mode
st.set_page_config(page_title="AI Hx. taking", page_icon=":robot_face:", layout="wide")

# Gemini uses 'model' for assistant; Streamlit uses 'assistant'
def role_to_streamlit(role):
    if role == "model":
        return "assistant"
    else:
        return role

# Add a Gemini Chat history object to Streamlit session state
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history = [])

# Initialize SQLite3 database connection
conn = sqlite3.connect('chat_history.db', check_same_thread=False)
c = conn.cursor()
# Create table to store chat history
c.execute('''CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY, role TEXT, message TEXT)''')

# Initialize doc_text
doc_text = ""

# Move file uploader to the sidebar
st.sidebar.subheader("증례 관련 자료")
st.sidebar.divider()

def get_file_list_from_github(repo, folder_path):
    url = f"https://api.github.com/repos/{repo}/contents/{folder_path}"
    headers = {'Accept': 'application/vnd.github.v3+json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        file_list = [file['name'] for file in response.json() if file['type'] == 'file']
        return file_list
    else:
        return []

# GitHub 리포지토리 정보 설정
github_repo = "jhlee409/amcgi_hx_taking_gemini"
folder_path = "case"

# 파일 목록 가져오기
file_list = get_file_list_from_github(github_repo, folder_path)
                
# Streamlit 사이드바에서 파일 선택 옵션 제공
selected_file = st.sidebar.selectbox("이 드롭다운 메뉴에서 증례를선택하세요.", file_list)
st.sidebar.divider()

if selected_file:
    # GitHub에서 파일 URL 구성
    file_url = f"https://raw.githubusercontent.com/jhlee409/amcgi_hx_taking_gemini/main/case/{selected_file}"

    # 파일 내용 가져오기
    response = requests.get(file_url)
    if response.status_code == 200:
        uploaded_file = io.BytesIO(response.content)
        
        if uploaded_file:
            # 파일 내용 읽기
            doc = Document(uploaded_file)
            full_text = [para.text for para in doc.paragraphs]
            doc_text = "\n".join(full_text)

            if doc_text.strip():
                # 문서 텍스트를 prompt로 사용
                prompt = doc_text

                # 사용자 메시지를 SQLite3 데이터베이스에 저장
                c.execute("INSERT INTO chat_history (role, message) VALUES (?, ?)", ("의사", prompt))
              
                # Gemini에 메시지 보내기 및 응답 읽기
                response = st.session_state.chat.send_message(prompt)

                # Gemini 응답을 데이터베이스에 저장
                c.execute("INSERT INTO chat_history (role, message) VALUES (?, ?)", ("환자", response.text))

                # 데이터베이스 변경사항 커밋
                conn.commit()
              
                # 세션 상태 업데이트
                st.session_state.file_processed = True

# GitHub 리포지토리 정보 설정
github_repo = "jhlee409/amcgi_hx_taking_gemini" # 예시: "octocat/Hello-World"
folder_path = "reference"
 
# 파일 목록 가져오기
file_list = get_file_list_from_github(github_repo, folder_path)

# Streamlit 사이드바에서 파일 선택 옵션 제공
selected_file = st.sidebar.selectbox("증례해설 파일 다운로드", file_list)

# 선택된 파일의 다운로드 링크 생성
download_url = f"https://github.com/{github_repo}/raw/main/{folder_path}/{selected_file}"

# 사이드바에 다운로드 링크 표시 (only if chat history has not been cleared)
if selected_file:
    st.sidebar.markdown(f"&emsp;[{selected_file}]({download_url})", unsafe_allow_html=True)

st.sidebar.divider()

# Display Form Title
st.subheader("&emsp;AI 환자 병력 청취 훈련 챗봇: gemini 버전&emsp;&emsp;&emsp;v 1.2.0")
with st.expander("사용방법을 보려면 여길 누르세요."):
  st.write("- 왼쪽 sidebar에서 증례 파일을 선택하고 AI가 다 읽으면 인터뷰를 시작하세요.")
  st.write("- 첫 질문은 어디가 불편해서 오셨나요? 이고 마치는 질문은 궁금한 점이 있으신가요? 입니다.")
  st.write("- 이 gemini 버전은 질문과 답변이 한 쌍씩만 보여지고, 마지막에 안 물어본 사항을 따로 보여주는 기능은 없습니다.")
  st.write("- 제작자: 이진혁: 제작에 서울아산병원 소화기 내과 교수님, 울산의대 관계자 분들께서 도와 주셨고 저작권 형식은 MIT 입니다.")
st.divider()

# Get user input from chat input
prompt = st.chat_input("첫 질문은 어디가 불편해서 오셨나요? 이고 마치는 질문은 궁금한 점이 있으신가요? 입니다.")

# Accept user's next message, add to context, resubmit context to Gemini
if prompt:
    # Save user message to SQLite3 database
    c.execute("INSERT INTO chat_history (role, message) VALUES (?, ?)", ("의사", prompt))

    # Send user entry to Gemini and read the response
    response = st.session_state.chat.send_message(prompt)

    # Save Gemini response to SQLite3 database
    c.execute("INSERT INTO chat_history (role, message) VALUES (?, ?)", ("환자", response.text))

    # Commit changes to database
    conn.commit()

# Display only the latest user and assistant messages
if "chat" in st.session_state and st.session_state.chat:
    last_user_message = c.execute("SELECT message FROM chat_history WHERE role = '의사' ORDER BY id DESC LIMIT 1").fetchone()
    last_assistant_message = c.execute("SELECT message FROM chat_history WHERE role = '환자' ORDER BY id DESC LIMIT 1").fetchone()

    # Check if '전체 지시 사항' is not in both the user and assistant messages before displaying
    if last_user_message and last_assistant_message:
        if '전체 지시 사항' not in last_user_message[0] and '전체 지시 사항' not in last_assistant_message[0]:
            st.markdown(f":male-doctor: :: {last_user_message[0]}")
            st.markdown(f":robot_face: :: {last_assistant_message[0]}")

# Close SQLite3 database connection
conn.commit()
conn.close()
