"""
使用者登入工具
- 帳號密碼存在 .streamlit/secrets.toml 的 [USERS] 區塊
- 登入後在瀏覽器寫入 HMAC cookie，下次自動認證，無需重新登入
- 主動登出才會清除 cookie
"""

from __future__ import annotations
import hashlib
import hmac
import streamlit as st

try:
    from streamlit_cookies_controller import CookieController
    _COOKIES_AVAILABLE = True
except ImportError:
    _COOKIES_AVAILABLE = False

COOKIE_NAME = "portfolio_auth"
COOKIE_MAX_AGE = 365 * 24 * 3600  # 1 年（秒）


# ── Token 工具 ────────────────────────────────────────────────────────────────

def _secret() -> str:
    return str(st.secrets.get("AUTH_SECRET", "portfolio-default-secret"))


def _make_token(username: str) -> str:
    return hmac.new(_secret().encode(), username.encode(), hashlib.sha256).hexdigest()


def _validate_cookie(cookie_val: str) -> str | None:
    """解析 cookie 值，回傳合法的 username 或 None"""
    try:
        username, token = cookie_val.rsplit(":", 1)
        if hmac.compare_digest(token, _make_token(username)):
            return username
    except Exception:
        pass
    return None


# ── 公開 API ──────────────────────────────────────────────────────────────────

def require_login() -> str:
    """
    確認登入狀態。未登入則顯示登入表單並停止執行。
    回傳目前使用者名稱。
    """
    ctrl = CookieController(key="auth_ctrl") if _COOKIES_AVAILABLE else None

    # 1. 快速路徑：session_state 已有登入狀態（同一 session 內換頁）
    if st.session_state.get("auth_user"):
        _show_sidebar_user(ctrl)
        return st.session_state["auth_user"]

    # 2. 嘗試從 cookie 自動登入
    if ctrl is not None:
        try:
            cookie_val = ctrl.get(COOKIE_NAME)
            if cookie_val:
                username = _validate_cookie(cookie_val)
                if username:
                    st.session_state["auth_user"] = username
                    _show_sidebar_user(ctrl)
                    return username
        except Exception:
            pass

    # 3. 顯示登入表單
    _show_login_form(ctrl)
    st.stop()


# ── 內部函數 ──────────────────────────────────────────────────────────────────

def _show_login_form(ctrl) -> None:
    st.set_page_config(page_title="登入", page_icon="🔒", layout="centered")
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
                # 寫入 cookie（永久保持登入，直到登出）
                if ctrl is not None:
                    try:
                        token = f"{username}:{_make_token(username)}"
                        ctrl.set(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE)
                    except Exception:
                        pass
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")


def _show_sidebar_user(ctrl) -> None:
    with st.sidebar:
        st.caption(f"👤 {st.session_state['auth_user']}")
        if st.button("登出", key="_logout_btn", use_container_width=True):
            # 清除 cookie
            if ctrl is not None:
                try:
                    ctrl.remove(COOKIE_NAME)
                except Exception:
                    pass
            st.session_state.pop("auth_user", None)
            st.cache_data.clear()
            st.rerun()
