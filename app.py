# -*- coding: utf-8 -*-
import json
import streamlit as st

from image_analysis_points import (
    IMAGE_ANALYSIS_POINTS,
    IMAGE_ANALYSIS_SCHEMA,
    build_image_analysis_prompt,
    build_image_summary_prompt,
    get_high_priority_indicators,
    build_image_analysis_checklist,
    flatten_analysis_points,
)

st.set_page_config(
    page_title="المشهد التنفيذي",
    page_icon="🔍",
    layout="wide"
)


def inject_css():
    st.markdown("""
    <style>
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
    }
    .stApp {
        background-color: #0f1117;
        color: #e2e8f0;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .custom-card {
        background: #1a1f2e;
        border: 1px solid #2d3748;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .small-muted {
        color: #94a3b8;
        font-size: 0.92rem;
    }
    </style>
    """, unsafe_allow_html=True)


def show_header():
    st.markdown("## 🔍 المشهد التنفيذي")
    st.markdown("### أداة تحليل الصور ومنشورات X بالذكاء الاصطناعي")
    st.markdown(
        '<div class="small-muted">نسخة تشغيلية مستقرة لعرض نقاط تحليل الصور وبناء Prompt جاهز</div>',
        unsafe_allow_html=True
    )
    st.divider()


def show_sidebar():
    st.sidebar.title("الإعدادات")
    mode = st.sidebar.radio(
        "نوع المخرجات",
        ["Prompt مفصل", "Prompt مختصر", "عرض النقاط فقط", "عرض مخطط JSON"]
    )
    strict_json = st.sidebar.checkbox("إجبار المخرجات بصيغة JSON فقط", value=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### مؤشرات عالية الأولوية")
    for item in get_high_priority_indicators():
        st.sidebar.markdown(f"- {item}")
    return mode, strict_json


def show_points():
    st.subheader("نقاط تحليل الصور")
    for section in IMAGE_ANALYSIS_POINTS:
        with st.expander(section["section"], expanded=False):
            for point in section["points"]:
                st.markdown(f"- {point}")


def show_schema():
    st.subheader("مخطط JSON المطلوب")
    st.code(
        json.dumps(IMAGE_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2),
        language="json"
    )


def show_checklist():
    st.subheader("قائمة الفحص السريع")
    checklist = build_image_analysis_checklist()
    cols = st.columns(len(checklist))
    for idx, (title, items) in enumerate(checklist.items()):
        with cols[idx]:
            st.markdown(f"#### {title}")
            for item in items:
                st.markdown(f"- {item}")


def main():
    inject_css()
    show_header()
    mode, strict_json = show_sidebar()

    tab1, tab2, tab3 = st.tabs([
        "بناء الـ Prompt",
        "نقاط التحليل",
        "الفحص السريع"
    ])

    with tab1:
        col1, col2 = st.columns([1.2, 1])

        with col1:
            st.subheader("بيانات الإدخال")
            account_name = st.text_input("اسم الحساب", placeholder="مثال: حساب تجريبي")
            account_username = st.text_input("اسم المستخدم", placeholder="مثال: demo_account")
            post_text = st.text_area(
                "نص المنشور المرتبط",
                height=140,
                placeholder="اكتب نص المنشور المرتبط بالصورة إن وجد"
            )
            extra_context = st.text_area(
                "سياق إضافي",
                height=100,
                placeholder="أي سياق إضافي تريد تضمينه في التحليل"
            )

            build_btn = st.button("إنشاء الـ Prompt", use_container_width=True)

        with col2:
            st.subheader("معلومات سريعة")
            st.markdown("""
            <div class="custom-card">
                <b>ما الذي يفعله هذا التطبيق؟</b><br><br>
                - يعرض نقاط تحليل الصور<br>
                - يبني Prompt جاهز للتحليل<br>
                - يوفّر مخطط JSON موحد<br>
                - يساعدك في تجهيز مدخلات Gemini أو أي نموذج مشابه
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="custom-card">
                <b>سبب الصفحة البيضاء سابقًا</b><br><br>
                كان ملف <code>image_analysis_points.py</code> ملفًا مساعدًا فقط،
                وليس واجهة Streamlit رئيسية. لذلك يجب أن يكون ملف التشغيل هو
                <code>app.py</code>.
            </div>
            """, unsafe_allow_html=True)

        if build_btn:
            if mode == "Prompt مفصل":
                result = build_image_analysis_prompt(
                    post_text=post_text,
                    account_name=account_name,
                    account_username=account_username,
                    extra_context=extra_context,
                    strict_json=strict_json
                )
                st.subheader("الـ Prompt المفصل")
                st.code(result, language="text")
                st.download_button(
                    "تنزيل prompt_detailed.txt",
                    data=result,
                    file_name="prompt_detailed.txt",
                    mime="text/plain"
                )

            elif mode == "Prompt مختصر":
                result = build_image_summary_prompt(
                    short_mode=True,
                    post_text=post_text,
                    account_username=account_username
                )
                st.subheader("الـ Prompt المختصر")
                st.code(result, language="text")
                st.download_button(
                    "تنزيل prompt_summary.txt",
                    data=result,
                    file_name="prompt_summary.txt",
                    mime="text/plain"
                )

            elif mode == "عرض النقاط فقط":
                result = "\n".join(flatten_analysis_points())
                st.subheader("جميع نقاط التحليل")
                st.code(result, language="text")
                st.download_button(
                    "تنزيل image_points.txt",
                    data=result,
                    file_name="image_points.txt",
                    mime="text/plain"
                )

            else:
                result = json.dumps(IMAGE_ANALYSIS_SCHEMA, ensure_ascii=False, indent=2)
                st.subheader("مخطط JSON")
                st.code(result, language="json")
                st.download_button(
                    "تنزيل schema.json",
                    data=result,
                    file_name="schema.json",
                    mime="application/json"
                )

    with tab2:
        show_points()
        st.divider()
        show_schema()

    with tab3:
        show_checklist()


if __name__ == "__main__":
    main()
