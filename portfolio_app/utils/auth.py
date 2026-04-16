"""
使用者登入工具
- 帳號密碼存在 .streamlit/secrets.toml 的 [USERS] 區塊
- 登入狀態存在 session_state（瀏覽器 tab 內持續有效）
- 登出按鈕固定顯示在側邊欄頂端
"""

from __future__ import annotations
import streamlit as st


def require_login() -> str:
    """
    確認登入狀態。未登入則顯示登入表單並停止執行。
    已登入則在側邊欄頂端顯示用戶名 + 登出按鈕。
    回傳目前使用者名稱。
    """
    if not st.session_state.get("auth_user"):
        _show_login_form()
        st.stop()

    _show_sidebar_user()
    return st.session_state["auth_user"]


def _show_login_form() -> None:
    st.markdown("<br>" * 2, unsafe_allow_html=True)
    col = st.columns([1, 3, 1])[1]
    with col:
        st.markdown("## 📊 投資組合")
        st.divider()
        username = st.text_input("帳號", key="_login_user", placeholder="請輸入帳號")
        password = st.text_input("密碼", type="password", key="_login_pass", placeholder="請輸入密碼")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("登入", type="primary", use_container_width=True, key="_login_btn"):
            users: dict = dict(st.secrets.get("USERS", {}))
            if username in users and str(users[username]) == str(password):
                st.session_state["auth_user"] = username
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")


def _show_sidebar_user() -> None:
    """在側邊欄最頂端固定顯示用戶名 + 登出按鈕"""
    with st.sidebar:
        user = st.session_state.get("auth_user", "")
        st.markdown(
            f"<div style='padding:6px 0 2px 0;font-size:0.9em;color:#AAA;'>👤 {user}</div>",
            unsafe_allow_html=True,
        )
        if st.button("登出", key="_logout_btn", use_container_width=True):
            st.session_state.pop("auth_user", None)
            st.cache_data.clear()
            st.rerun()
        st.divider()
