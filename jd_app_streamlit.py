import streamlit as st
import google.generativeai as genai
import docx
import os

# Cấu hình API Key từ secrets
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Hàm đọc nội dung file .docx
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip() != ""])

# Load phương pháp PwC từ file text
@st.cache_data
def load_pwc_prompt():
    with open("pwc_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

# Khởi tạo model Gemini
model = genai.GenerativeModel("gemini-pro")

# Giao diện Streamlit
st.set_page_config(page_title="Đánh giá giá trị công việc (PwC)", layout="wide")
st.title("📋 Đánh giá mô tả công việc theo 12 yếu tố PwC")
st.markdown("Tải lên mô tả công việc (.docx) để hệ thống AI đánh giá.")

# Nhập tên vị trí
job_title = st.text_input("🔤 Nhập tên vị trí công việc:")

# Upload file mô tả công việc
uploaded_file = st.file_uploader("📎 Tải lên JD định dạng .docx", type=["docx"])

if uploaded_file and job_title:
    with st.spinner("🧠 Đang phân tích..."):
        jd_content = read_docx(uploaded_file)
        full_prompt = load_pwc_prompt() + f"\n\nĐây là JD cho vị trí: {job_title}\n\n{jd_content}"
        response = model.generate_content(full_prompt)
        result = response.text

        # Hiển thị kết quả
        st.markdown("### ✅ Kết quả đánh giá theo 12 yếu tố PwC")
        st.markdown(result)

        # Lưu JD đã đánh giá để so sánh sau
        if "jd_history" not in st.session_state:
            st.session_state.jd_history = []

        st.session_state.jd_history.append({"position": job_title, "content": jd_content})

        # So sánh JD mới với các JD đã upload trước đó
        if len(st.session_state.jd_hi
