    # ─── قسم التحليل الاستخباراتي ──────────────────────────
    st.markdown("---")
    st.markdown("## 🔍 التحليل الاستخباراتي الشامل")

    tweets_list   = st.session_state.get("fetched_tweets", [])
    x_auth_token  = st.session_state.get("x_auth_token",  "")
    twitter_key   = st.session_state.get("twitter_api_key","")
    username      = user.get("screen_name","")

    # ─── أزرار الجلب ──────────────────────────────────────
    col_scweet, col_twitterapi = st.columns(2)

    # ── الطريقة 1: Scweet (بدون مفتاح) ───────────────────
    with col_scweet:
        scweet_disabled = not bool(x_auth_token)
        if st.button(
            "🍪 جلب 100 تغريدة (Scweet - مجاني)",
            key="fetch_scweet",
            disabled=scweet_disabled,
            use_container_width=True,
            help="يحتاج auth_token من المتصفح فقط - لا API key مطلوب"
        ):
            texts = fetch_tweets_scweet(username, x_auth_token, limit=100)
            if texts:
                st.session_state["fetched_tweets"] = texts
                tweets_list = texts
                st.success(f"✅ تم جلب {len(texts)} تغريدة عبر Scweet")
            else:
                st.warning("لم يُجلب أي نص. تحقق من auth_token.")

        if scweet_disabled:
            st.caption("⬆️ أدخل auth_token في الشريط الجانبي")

    # ── الطريقة 2: TwitterAPI.io (بمفتاح) ─────────────────
    with col_twitterapi:
        tapi_disabled = not bool(twitter_key)
        if st.button(
            "🔑 جلب 500 تغريدة (TwitterAPI.io)",
            key="fetch_tweets",
            disabled=tapi_disabled,
            use_container_width=True
        ):
            with st.spinner("جاري الجلب... قد يستغرق دقيقة"):
                raw = fetch_user_tweets_twitterapi(username, twitter_key, 500)
                texts = [
                    t.get("text","") if isinstance(t,dict) else str(t)
                    for t in raw if (t.get("text","") if isinstance(t,dict) else t)
                ]
                st.session_state["fetched_tweets"] = texts
                tweets_list = texts
            st.success(f"✅ تم جلب {len(texts)} تغريدة عبر TwitterAPI.io")

        if tapi_disabled:
            st.caption("⬆️ أدخل مفتاح TwitterAPI.io في الشريط الجانبي")

    # ── الطريقة 3: إدخال يدوي ─────────────────────────────
    with st.expander("✍️ أو أدخل التغريدات يدوياً"):
        manual = st.text_area(
            "الصق نصوص التغريدات (كل تغريدة في سطر)",
            height=150,
            key="manual_tweets",
            placeholder="الصق هنا نصوص التغريدات...")
        if manual.strip():
            manual_list = [l.strip() for l in manual.split('\n') if l.strip()]
            if st.button("➕ إضافة للتحليل", key="add_manual"):
                existing = st.session_state.get("fetched_tweets", [])
                st.session_state["fetched_tweets"] = existing + manual_list
                tweets_list = st.session_state["fetched_tweets"]
                st.success(f"✅ تمت إضافة {len(manual_list)} تغريدة")

    # ── إحصائية ───────────────────────────────────────────
    if tweets_list:
        st.info(f"📊 إجمالي التغريدات المتاحة للتحليل: **{len(tweets_list)}**")

        # فحص الكلمات المفتاحية
        kw_hits = scan_keywords(tweets_list)
        if kw_hits:
            st.markdown("### ⚠️ الكلمات المفتاحية المكتشفة")
            for cat, hits in kw_hits.items():
                st.error(f"**{cat}:** {' | '.join(hits)}")
        else:
            st.success("✅ لم تُكتشف كلمات مفتاحية مثيرة للقلق")

        model_id   = st.session_state.get("model_id", "gemini-2.5-flash")
        gemini_key = st.session_state.get("gemini_api_key","")

        if st.button("🧠 بدء التحليل الاستخباراتي الشامل",
                     key="run_intel", use_container_width=True):
            if not gemini_key:
                st.error("❌ أدخل مفتاح Gemini API أولاً")
            else:
                with st.spinner("جاري التحليل الاستخباراتي..."):
                    report = generate_intel_summary(
                        user, tweets_list, kw_hits, model_id)
                st.session_state["intel_report"] = report
                st.success("✅ اكتمل التحليل")

    intel_report = st.session_state.get("intel_report","")
    if intel_report:
        st.markdown("### 📋 التقرير الاستخباراتي")
        st.markdown(intel_report)
