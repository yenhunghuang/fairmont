"""
Session State 管理工具

提供 Streamlit Session State 的統一管理介面
"""

import streamlit as st
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SessionStateManager:
    """Session State 管理器"""

    # 預設值定義
    defaults: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化預設值"""
        for key, value in self.defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """取得 session state 值"""
        return st.session_state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """設定 session state 值"""
        st.session_state[key] = value

    def delete(self, key: str) -> None:
        """刪除 session state 值"""
        if key in st.session_state:
            del st.session_state[key]

    def clear(self) -> None:
        """清除所有 session state"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]

    def reset_to_defaults(self) -> None:
        """重設為預設值"""
        self.clear()
        self.__post_init__()

    def exists(self, key: str) -> bool:
        """檢查 key 是否存在"""
        return key in st.session_state

    def update(self, **kwargs) -> None:
        """批次更新多個值"""
        for key, value in kwargs.items():
            st.session_state[key] = value

    def get_all(self) -> Dict[str, Any]:
        """取得所有 session state（除了內部變數）"""
        return {
            k: v for k, v in st.session_state.items()
            if not k.startswith('_')
        }


# ==================== 應用程式特定的 Session State 管理 ====================

class AppSessionState(SessionStateManager):
    """應用程式專用的 Session State 管理器"""

    def __init__(self):
        # 定義應用程式的預設值
        defaults = {
            # 使用者資訊
            'user_name': '',
            'user_role': 'user',

            # 上傳檔案相關
            'uploaded_files': [],
            'current_task_id': None,
            'task_results': {},

            # UI 狀態
            'current_page': 'home',
            'show_sidebar': True,

            # 表單狀態
            'form_data': {},

            # 錯誤與訊息
            'last_error': None,
            'messages': [],

            # 設定
            'api_base_url': 'http://localhost:8000',
            'theme': 'light',
            'language': 'zh-TW',

            # 時間戳記
            'session_start_time': datetime.now().isoformat(),
            'last_activity_time': datetime.now().isoformat(),
        }
        super().__init__(defaults)

    # ========== 便利方法 ==========

    def add_message(self, message: str, msg_type: str = 'info'):
        """新增訊息到訊息列表"""
        messages = self.get('messages', [])
        messages.append({
            'text': message,
            'type': msg_type,
            'timestamp': datetime.now().isoformat()
        })
        self.set('messages', messages)

    def clear_messages(self):
        """清除所有訊息"""
        self.set('messages', [])

    def get_messages(self, msg_type: Optional[str] = None):
        """取得訊息（可依類型篩選）"""
        messages = self.get('messages', [])
        if msg_type:
            return [m for m in messages if m['type'] == msg_type]
        return messages

    def set_error(self, error: str):
        """設定錯誤訊息"""
        self.set('last_error', error)
        self.add_message(error, 'error')

    def clear_error(self):
        """清除錯誤訊息"""
        self.set('last_error', None)

    def update_activity(self):
        """更新最後活動時間"""
        self.set('last_activity_time', datetime.now().isoformat())

    def add_uploaded_file(self, filename: str, task_id: str):
        """新增已上傳的檔案記錄"""
        files = self.get('uploaded_files', [])
        files.append({
            'filename': filename,
            'task_id': task_id,
            'uploaded_at': datetime.now().isoformat()
        })
        self.set('uploaded_files', files)

    def get_uploaded_files(self):
        """取得已上傳的檔案列表"""
        return self.get('uploaded_files', [])

    def clear_uploaded_files(self):
        """清除已上傳的檔案列表"""
        self.set('uploaded_files', [])

    def set_task_result(self, task_id: str, result: Dict[str, Any]):
        """儲存任務結果"""
        results = self.get('task_results', {})
        results[task_id] = {
            'result': result,
            'completed_at': datetime.now().isoformat()
        }
        self.set('task_results', results)

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """取得任務結果"""
        results = self.get('task_results', {})
        return results.get(task_id)

    def update_form_data(self, form_name: str, data: Dict[str, Any]):
        """更新表單資料"""
        form_data = self.get('form_data', {})
        form_data[form_name] = data
        self.set('form_data', form_data)

    def get_form_data(self, form_name: str) -> Dict[str, Any]:
        """取得表單資料"""
        form_data = self.get('form_data', {})
        return form_data.get(form_name, {})

    def clear_form_data(self, form_name: str):
        """清除特定表單資料"""
        form_data = self.get('form_data', {})
        if form_name in form_data:
            del form_data[form_name]
            self.set('form_data', form_data)


# ==================== 全域實例 ====================

def get_session_state() -> AppSessionState:
    """取得全域 Session State 管理器"""
    if '_state_manager' not in st.session_state:
        st.session_state._state_manager = AppSessionState()
    return st.session_state._state_manager


# ==================== 裝飾器 ====================

def with_session_state(func: Callable) -> Callable:
    """
    裝飾器：自動注入 session_state 參數

    使用範例:
        @with_session_state
        def my_function(session_state):
            name = session_state.get('user_name')
            ...
    """
    def wrapper(*args, **kwargs):
        session_state = get_session_state()
        return func(session_state, *args, **kwargs)
    return wrapper


def track_activity(func: Callable) -> Callable:
    """
    裝飾器：自動追蹤使用者活動時間

    使用範例:
        @track_activity
        def my_page():
            ...
    """
    def wrapper(*args, **kwargs):
        session_state = get_session_state()
        session_state.update_activity()
        return func(*args, **kwargs)
    return wrapper
