"""
使用者登入工具
- 帳號密碼存在 .streamlit/secrets.toml 的 [USERS] 區塊
- Cookie 保持登入狀態（預設 30 天，勾選「記住我」）
- 登出按鈕固定顯示在側邊欄頂端
"""

from __future__ import annotations
import hashlib
import streamlit as st

try:
    import extra_streamlit_components as stx
    _HAS_COOKIES = True
except ImportError:
    _HAS_COOKIES = False

_COOKIE_NAME = "sap_auth_v1"
_COOKIE_DAYS = 30


def _make_token(username: str, password: str) -> str:
    """產生登入 token（SHA-256）"""
    salt = str(st.secrets.get("SECRET_SALT", "smart-asset-pilot-2025"))
    return hashlib.sha256(f"{username}:{password}:{salt}".encode()).hexdigest()


def _get_cookie_manager():
    if not _HAS_COOKIES:
        return None
    # key 固定，確保跨頁面共用同一個 cookie manager
    return stx.CookieManager(key="_sap_cookie_mgr")


def require_login() -> str:
    """
    確認登入狀態。未登入則顯示登入表單並停止執行。
    已登入則在側邊欄頂端顯示用戶名 + 登出按鈕。
    回傳目前使用者名稱。
    """
    cm = _get_cookie_manager()

    # 1. session 已有 → 直接用
    # 2. session 無 → 嘗試從 cookie 還原
    if not st.session_state.get("auth_user") and cm is not None:
        token = cm.get(_COOKIE_NAME)
        if token:
            users: dict = dict(st.secrets.get("USERS", {}))
            for uname, pwd in users.items():
                if token == _make_token(uname, str(pwd)):
                    st.session_state["auth_user"] = uname
                    break

    if not st.session_state.get("auth_user"):
        _show_login_form(cm)
        st.stop()

    # 登出按鈕固定在側邊欄最頂端
    _show_sidebar_user(cm)
    return st.session_state["auth_user"]


def _show_login_form(cm) -> None:
    st.markdown("<br>" * 2, unsafe_allow_html=True)
    col = st.columns([1, 3, 1])[1]
    with col:
        st.markdown("## 📊 投資組合")
        st.divider()
        username = st.text_input("帳號", key="_login_user", placeholder="請輸入帳號")
        password = st.text_input("密碼", type="password", key="_login_pass", placeholder="請輸入密碼")
        remember = st.checkbox("記住我（30 天）", value=True, key="_login_remember")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("登入", type="primary", use_container_width=True, key="_login_btn"):
            users: dict = dict(st.secrets.get("USERS", {}))
            if username in users and str(users[username]) == str(password):
                st.session_state["auth_user"] = username
                if remember and cm is not None:
                    token = _make_token(username, str(users[username]))
                    cm.set(_COOKIE_NAME, token, max_age=_COOKIE_DAYS * 86400)
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")


def _show_sidebar_user(cm) -> None:
    """在側邊欄最頂端固定顯示用戶名 + 登出按鈕"""
    with st.sidebar:
        user = st.session_state.get("auth_user", "")
        st.markdown(
            f"<div style='padding:6px 0 2px 0;font-size:0.9em;color:#AAA;'>👤 {user}</div>",
            unsafe_allow_html=True,
        )
        if st.button("登出", key="_logout_btn", use_container_width=True):
            if cm is not None:
                try:
                    cm.delete(_COOKIE_NAME)
                except Exception:
                    pass
            st.session_state.pop("auth_user", None)
            st.cache_data.clear()
            st.rerun()
        st.divider()
