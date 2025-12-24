import os
import time
import json
import streamlit as st
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import docx

# =========================
# STREAMLIT CONFIG
# =========================
st.set_page_config(page_title="Đánh giá công việc PwC", layout="wide")
st.title("📋 Đánh giá mô tả công việc theo 12 yếu tố PwC")
st.markdown("Hãy tải lên file mô tả công việc để được hệ thống đánh giá tự động.")

# =========================
# API KEY (FIX: KHÔNG HARDCODE)
# =========================
api_key = st.secrets.get("AIzaSyALIFJZAmvuu5G5QVOMjp0bXb7sn-Hhfh4") or os.getenv("AIzaSyALIFJZAmvuu5G5QVOMjp0bXb7sn-Hhfh4")
if not api_key:
    st.error("❌ Thiếu GOOGLE_API_KEY. Hãy vào Streamlit Cloud → Manage app → Settings → Secrets và thêm GOOGLE_API_KEY.")
    st.stop()

genai.configure(api_key=api_key)

# Model: bạn đang dùng gemini-2.0-flash, ok
model = genai.GenerativeModel("gemini-2.0-flash")

# =========================
# HELPERS: RETRY + TRIM (FIX ResourceExhausted)
# =========================
MAX_JD_CHARS = 25000          # cắt JD để tránh token quá lớn
MAX_REF_CONTEXT_CHARS = 12000 # giới hạn phần reference_context để tránh prompt quá dài

def safe_trim(text: str, max_chars: int) -> str:
    text = text or ""
    return text[:max_chars]

def call_gemini_with_retry(prompt: str, retries: int = 4):
    """Retry theo backoff khi gặp ResourceExhausted (quota/rate limit)."""
    last_err = None
    for i in range(retries):
        try:
            return model.generate_content(prompt)
        except ResourceExhausted as e:
            last_err = e
            time.sleep(2 ** i)  # 1s,2s,4s,8s
    raise last_err

# =========================
# LOAD FILES
# =========================
@st.cache_data
def load_reference_data():
    with open("historical_evaluations.json", "r", encoding="utf-8") as f:
        return json.load(f)

REFERENCE_JD_EVALS = load_reference_data()

@st.cache_data
def load_pwc_prompt():
    with open("pwc_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip() != ""])

def read_txt(file):
    return file.read().decode("utf-8", errors="ignore")

def find_similar_jd(new_jd_text, reference_evals, top_k=5):
    # NOTE: code của bạn đang dùng e["job_title"] làm corpus, mình giữ nguyên logic,
    # nhưng nếu bạn muốn similarity theo nội dung JD thì cần đổi sang e["jd_content"] (nếu có).
    corpus = [e["job_title"] for e in reference_evals] + [new_jd_text]
    vec = TfidfVectorizer().fit_transform(corpus)
    sim_matrix = cosine_similarity(vec[-1], vec[:-1])
    top_indices = sim_matrix[0].argsort()[-top_k:][::-1]
    return [reference_evals[i] for i in top_indices]

# =========================
# UI INPUTS
# =========================
job_title = st.text_input("🔤 Nhập tên vị trí công việc:")
uploaded_file = st.file_uploader("📎 Tải lên file mô tả công việc (.docx hoặc .txt)", type=["docx", "txt"])

# =========================
# ANTI-RERUN LOCK (FIX gọi API lặp)
# =========================
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Nút bấm để tránh auto-run khi nhập text/upload (giảm gọi API ngoài ý muốn)
run_btn = st.button("🚀 Evaluate JD", disabled=st.session_state.is_running)

if run_btn:
    if not uploaded_file or not job_title:
        st.warning("Vui lòng nhập tên vị trí và tải lên file JD trước khi Evaluate.")
        st.stop()

    st.session_state.is_running = True
    try:
        with st.spinner("🔍 Đang phân tích và đánh giá..."):
            # ---- Read JD (fix txt/docx)
            if uploaded_file.name.lower().endswith(".docx"):
                jd_content = read_docx(uploaded_file)
            else:
                jd_content = read_txt(uploaded_file)

            jd_content = jd_content.strip()
            if not jd_content:
                st.error("File JD rỗng hoặc không đọc được nội dung.")
                st.stop()

            # ---- Trim JD để tránh prompt quá dài
            if len(jd_content) > MAX_JD_CHARS:
                st.warning(f"JD dài ({len(jd_content)} ký tự). Đã tự cắt còn {MAX_JD_CHARS} ký tự để tránh vượt giới hạn token.")
            jd_for_prompt = safe_trim(jd_content, MAX_JD_CHARS)

            # ---- Find similar cases
            similar_cases = find_similar_jd(jd_for_prompt, REFERENCE_JD_EVALS, top_k=5)
            reference_context = "\n".join([
                f"{case.get('job_title','(no title)')}: {json.dumps(case.get('factors', {}), ensure_ascii=False)}"
                for case in similar_cases
            ])
            reference_context = safe_trim(reference_context, MAX_REF_CONTEXT_CHARS)

            pwc_prompt = load_pwc_prompt()

            # ---- ONE SINGLE prompt (fix: bạn đang gọi generate_content 2 lần, lần đầu bị thừa)
            prompt = f"""
{pwc_prompt}

Dưới đây là các mẫu JD đã được đánh giá theo phương pháp PwC:

{reference_context}

Hãy đánh giá JD mới theo chuẩn PwC (12 yếu tố, xếp loại từ A → J).
Trả kết quả ở dạng bảng.
Nếu JD thiếu thông tin, hãy ghi rõ "Thiếu dữ liệu" ở yếu tố tương ứng và nêu giả định tối thiểu.

---

Tên vị trí: {job_title}

JD mới:
{jd_for_prompt}
""".strip()

            # ---- Call Gemini with retry
            response = call_gemini_with_retry(prompt, retries=4)
            result = getattr(response, "text", "") or ""
            st.markdown("### ✅ Kết quả đánh giá theo 12 yếu tố PwC")
            st.markdown(result)

            # ---- Lưu lịch sử để so sánh scope
            if "jd_history" not in st.session_state:
                st.session_state.jd_history = []
            st.session_state.jd_history.append({
                "position": job_title,
                "content": jd_for_prompt
            })

            # ---- Compare scope (cũng có thể tốn token -> trim + retry)
            if len(st.session_state.jd_history) > 1:
                st.markdown("### 🔄 So sánh phạm vi công việc với các vị trí trước đó")

                compare_prompt = (
                    "Hãy so sánh phạm vi công việc (scope) của mô tả sau với những mô tả đã được phân tích trước đó.\n\n"
                    f"JD mới ({job_title}):\n{jd_for_prompt}\n\n"
                )
                for past in st.session_state.jd_history[:-1]:
                    compare_prompt += f"\n---\nJD đã đánh giá ({past['position']}):\n{safe_trim(past['content'], 12000)}\n"

                compare_prompt += "\n\nĐưa ra các vị trí tương đồng, mức độ giống nhau ước lượng theo %, và lý do tương đồng."

                # Trim toàn prompt compare để tránh quá dài
                compare_prompt = safe_trim(compare_prompt, 35000)

                compare_response = call_gemini_with_retry(compare_prompt, retries=4)
                st.markdown(getattr(compare_response, "text", ""))

    except ResourceExhausted:
        st.error(
            "❌ ResourceExhausted: Bạn đang vượt quota/rate limit hoặc prompt quá lớn.\n\n"
            "Gợi ý: thử lại sau 1–2 phút, giảm độ dài JD, hoặc tăng quota/billing cho project."
        )
    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        st.session_state.is_running = False
