
# JD Evaluation App (PwC - Gemini)

## 📦 Mô tả
Ứng dụng Streamlit cho phép bạn tải file JD (.docx) lên để đánh giá giá trị công việc theo phương pháp 12 yếu tố của PwC, sử dụng mô hình Gemini của Google.

## ▶️ Cách sử dụng
1. Cài thư viện:
   pip install streamlit python-docx google-generativeai

2. Chạy app:
   streamlit run jd_app_streamlit.py

3. Thêm API Key:
   Thay dòng YOUR_GEMINI_API_KEY bằng key từ https://aistudio.google.com/app/apikey

## 📝 File
- jd_app_streamlit.py: mã nguồn chính
- pwc_prompt.txt: system prompt chuẩn
