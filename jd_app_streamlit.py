import streamlit as st
import google.generativeai as genai
import docx
import os

# Cấu hình Gemini API
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Hàm đọc nội dung từ file .docx
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip() != ""])

# Load prompt phương pháp PwC từ file
@st.cache_data
def load_pwc_prompt():
    with open("pwc_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

# Khởi tạo model Gemini
model = genai.GenerativeModel("gemini-pro")

# Giao diện chính
st.set_page_config(page_title="Đánh giá công việc PwC", layout="wide")
st.title("📋 Đánh giá mô tả công việc theo 12 yếu tố PwC")
st.markdown("Hãy tải lên file mô tả công việc (.docx) để được hệ thống AI đánh giá tự động.")

# Nhập tên vị trí
job_title = st.text_input("🔤 Nhập tên vị trí công việc:")

# Upload file .docx
uploaded_file = st.file_uploader("📎 Tải lên file mô tả công việc (.docx)", type=["docx"])

# Xử lý khi có file và tên vị trí
if uploaded_file and job_title:
    with st.spinner("🔍 Đang phân tích và đánh giá..."):
        jd_content = read_docx(uploaded_file)
        prompt = load_pwc_prompt() + f"\n\nĐây là mô tả công việc của vị trí: {job_title}\n\n{jd_content}"
        response = model.generate_content(prompt)
        result = response.text

        # Hiển thị kết quả đánh giá
        st.markdown("### ✅ Kết quả đánh giá theo 12 yếu tố PwC")
        st.markdown(result)

        # Lưu vào lịch sử để so sánh
        if "jd_history" not in st.session_state:
            st.session_state.jd_history = []
        st.session_state.jd_history.append({
            "position": job_title,
            "content": jd_content
        })

        # So sánh với các JD trước đó nếu có
        if len(st.session_state.jd_history) > 1:
            st.markdown("### 🔄 So sánh phạm vi công việc với các vị trí trước đó")

            compare_prompt = (
                "Hãy so sánh phạm vi công việc (scope) của mô tả sau với những mô tả đã được phân tích trước đó.\n\n"
                f"JD mới ({job_title}):\n{jd_content}\n\n"
            )
            for past in st.session_state.jd_history[:-1]:
                compare_prompt += f"\n---\nJD đã đánh giá ({past['position']}):\n{past['content']}\n"

            compare_prompt += (
                "\n\nĐưa ra các vị trí tương đồng, mức độ giống nhau ước lượng theo %, và lý do tương đồng."
            )

            compare_response = model.generate_content(compare_prompt)
            st.markdown(compare_response.text)
