"""Persistent in-memory state for pending items and drafts.

Two dicts survive restarts via state.json:
- pending_adoption : msg_id -> raw item awaiting a "Generuj post" click
- pending_posts    : msg_id -> generated draft awaiting review/publish

Telethon message objects are runtime-only and are not persisted.
"""
import json
import os
import time

STATE_FILE = os.getenv("STATE_FILE", "state.json")
_STATE_LOADING = False


def _parse_state_key(key):
    if isinstance(key, int):
        return key
    if isinstance(key, str) and key.isdigit():
        return int(key)
    return key


def _serialize_post(post):
    if not isinstance(post, dict):
        return {}
    return {
        "text": post.get("text", ""),
        "original_text": post.get("original_text", ""),
        "source": post.get("source", ""),
        "has_url": bool(post.get("has_url", False)),
        "article_url": post.get("article_url", ""),
        "user_instruction": post.get("user_instruction", ""),
        "title": post.get("title", ""),
        "image": post.get("image", ""),
        "platform": post.get("platform", ""),
        "phase": post.get("phase", ""),
        "phase1_msg_id": post.get("phase1_msg_id"),
        "edit_chain": [s for s in post.get("edit_chain", []) if isinstance(s, str)],
        "created_at": post.get("created_at", time.time()),
    }


def _deserialize_post(raw):
    if not isinstance(raw, dict):
        return {}
    post = _serialize_post(raw)
    post["messages"] = []  # runtime-only
    return post


def save_state():
    if _STATE_LOADING:
        return
    try:
        data = {
            "pending_adoption": {str(k): _serialize_post(v) for k, v in pending_adoption.items()},
            "pending_posts": {str(k): _serialize_post(v) for k, v in pending_posts.items()},
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STATE] save failed: {e}")


def load_state():
    global _STATE_LOADING
    if not os.path.exists(STATE_FILE):
        return
    try:
        _STATE_LOADING = True
        with open(STATE_FILE) as f:
            data = json.load(f)
        pending_adoption.clear()
        pending_posts.clear()
        for k, v in (data.get("pending_adoption") or {}).items():
            pending_adoption[_parse_state_key(k)] = _deserialize_post(v)
        for k, v in (data.get("pending_posts") or {}).items():
            pending_posts[_parse_state_key(k)] = _deserialize_post(v)
    except Exception as e:
        print(f"[STATE] load failed: {e}")
    finally:
        _STATE_LOADING = False


class PersistentDict(dict):
    """dict that persists to state.json on every mutation."""

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        save_state()

    def __delitem__(self, key):
        super().__delitem__(key)
        save_state()

    def pop(self, key, default=None):
        value = super().pop(key, default)
        save_state()
        return value

    def clear(self):
        super().clear()
        save_state()

    def setdefault(self, key, default=None):
        value = super().setdefault(key, default)
        save_state()
        return value


pending_adoption = PersistentDict()
pending_posts = PersistentDict()


def track_post(d, post, *, sent_id=None):
    """Stamp created_at and log tracking. `d` is the dict the post lives in."""
    post.setdefault("created_at", time.time())
    if sent_id is not None:
        source = post.get("source", "?")
        preview = (post.get("original_text") or post.get("text", ""))[:50]
        print(f"[TRACK] msg_id={sent_id} → {source}: {preview}")
    return post
