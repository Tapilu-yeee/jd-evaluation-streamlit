import os
import json
import streamlit as st
import google.generativeai as genai
import docx

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =========================
# STREAMLIT CONFIG
# =========================
st.set_page_config(page_title="Đánh giá công việc PwC", layout="wide")
st.title("📋 Đánh giá mô tả công việc theo 12 yếu tố PwC")
st.markdown("Hãy tải lên file mô tả công việc để được hệ thống đánh giá tự động.")

# =========================
# API KEY (KHÔNG HARDCODE)
# =========================
api_key = st.secrets.get("AIzaSyA8a7ZxHfZAls3B_giKA-FVGWCqkopl07U") or os.getenv("AIzaSyA8a7ZxHfZAls3B_giKA-FVGWCqkopl07U")
if not api_key:
    st.error("❌ Thiếu GOOGLE_API_KEY. Vào Streamlit Cloud → Manage app → Settings → Secrets và thêm GOOGLE_API_KEY.")
    st.stop()

genai.configure(api_key=api_key)

# =========================
# LOAD DATA / PROMPT (CACHE)
# =========================
@st.cache_data
def load_reference_data():
    with open("historical_evaluations.json", "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_pwc_prompt():
    with open("pwc_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

REFERENCE_JD_EVALS = load_reference_data()
PWC_PROMPT = load_pwc_prompt()

# =========================
# CACHE MODEL (TRÁNH KHỞI TẠO LẠI)
# =========================
@st.cache_resource
def get_model():
    return genai.GenerativeModel("gemini-2.0-flash")

model = get_model()

# =========================
# FILE READERS
# =========================
def read_docx(file):
    d = docx.Document(file)
    return "\n".join([p.text for p in d.paragraphs if p.text.strip()])

def read_txt(file):
    return file.read().decode("utf-8", errors="ignore")

# =========================
# TF-IDF INDEX (CACHE) -> TĂNG TỐC find_similar_jd
# =========================
@st.cache_resource
def build_tfidf_index(reference_evals):
    # Giữ logic như bạn đang làm: corpus là job_title
    titles = [e.get("job_title", "") for e in reference_evals]
    vectorizer = TfidfVectorizer()
    ref_vecs = vectorizer.fit_transform(titles)
    return vectorizer, ref_vecs

def find_similar_jd(new_jd_text, reference_evals, top_k=5):
    vectorizer, ref_vecs = build_tfidf_index(reference_evals)
    new_vec = vectorizer.transform([new_jd_text])
    sim = cosine_similarity(new_vec, ref_vecs)[0]
    top_indices = sim.argsort()[-top_k:][::-1]
    return [reference_evals[i] for i in top_indices]

# =========================
# UI INPUTS
# =========================
job_title = st.text_input("🔤 Nhập tên vị trí công việc:")
uploaded_file = st.file_uploader("📎 Tải lên file mô tả công việc (.docx hoặc .txt)", type=["docx", "txt"])

# Chống gọi lặp do rerun
if "is_running" not in st.session_state:
    st.session_state.is_running = False

run_btn = st.button("🚀 Evaluate JD", disabled=st.session_state.is_running)

# =========================
# MAIN RUN
# =========================
if run_btn:
    if not uploaded_file or not job_title:
        st.warning("Vui lòng nhập tên vị trí và tải lên file JD trước khi Evaluate.")
        st.stop()

    st.session_state.is_running = True
    try:
        with st.spinner("🔍 Đang phân tích và đánh giá..."):
            # 1) Read JD
            if uploaded_file.name.lower().endswith(".docx"):
                jd_content = read_docx(uploaded_file)
            else:
                jd_content = read_txt(uploaded_file)

            jd_content = (jd_content or "").strip()
            if not jd_content:
                st.error("File JD rỗng hoặc không đọc được nội dung.")
                st.stop()

            # 2) Similar cases (TF-IDF cached)
            similar_cases = find_similar_jd(jd_content, REFERENCE_JD_EVALS, top_k=5)
            reference_context = "\n".join([
                f"{case.get('job_title','(no title)')}: {json.dumps(case.get('factors', {}), ensure_ascii=False)}"
                for case in similar_cases
            ])

            # 3) Build FINAL prompt (CHỈ 1 LẦN GỌI API — bỏ call thừa)
            prompt = f"""
{PWC_PROMPT}

Dưới đây là các mẫu JD đã được đánh giá theo phương pháp PwC:

{reference_context}

Hãy đánh giá JD mới theo chuẩn PwC (12 yếu tố, xếp loại từ A → J).
Trả kết quả ở dạng bảng.
---

Tên vị trí: {job_title}

JD mới:
{jd_content}
""".strip()

            # 4) Call Gemini (1 lần)
            response = model.generate_content(prompt)
            result = getattr(response, "text", "") or ""

            st.markdown("### ✅ Kết quả đánh giá theo 12 yếu tố PwC")
            st.markdown(result)

            # 5) Save history for later comparison (nhanh)
            if "jd_history" not in st.session_state:
                st.session_state.jd_history = []
            st.session_state.jd_history.append({
                "position": job_title,
                "content": jd_content
            })

    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        st.session_state.is_running = False

# =========================
# OPTIONAL: COMPARE SCOPE (TÁCH NÚT RIÊNG ĐỂ KHÔNG LÀM CHẬM ĐÁNH GIÁ)
# =========================
if "jd_history" in st.session_state and len(st.session_state.jd_history) > 1:
    st.markdown("### 🔄 So sánh phạm vi công việc với các vị trí trước đó")
    if st.button("So sánh scope (có thể mất thời gian)"):
        with st.spinner("Đang so sánh scope..."):
            current = st.session_state.jd_history[-1]
            compare_prompt = (
                "Hãy so sánh phạm vi công việc (scope) của mô tả sau với những mô tả đã được phân tích trước đó.\n\n"
                f"JD mới ({current['position']}):\n{current['content']}\n\n"
            )
            for past in st.session_state.jd_history[:-1]:
                compare_prompt += f"\n---\nJD đã đánh giá ({past['position']}):\n{past['content']}\n"

            compare_prompt += "\n\nĐưa ra các vị trí tương đồng, mức độ giống nhau ước lượng theo %, và lý do tương đồng."

            compare_response = model.generate_content(compare_prompt)
            st.markdown(getattr(compare_response, "text", ""))

