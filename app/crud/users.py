from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import ADMIN_PASSWORD, ADMIN_USERNAME
from app.core.security import hash_password, verify_password
from app.db.models import User

MIN_PASSWORD_LENGTH = 8


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return db.scalars(select(User).order_by(User.username)).all()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự.")


def create_user(db: Session, username: str, password: str, ho_ten: str | None = None, is_admin: bool = False) -> User:
    username = username.strip()
    if not username:
        raise ValueError("Tên đăng nhập không được để trống.")
    _check_password(password)
    if db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise ValueError(f"Tên đăng nhập \"{username}\" đã tồn tại.")
    user = User(username=username, ho_ten=ho_ten, password_hash=hash_password(password), is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_password(db: Session, user: User, password: str) -> None:
    _check_password(password)
    user.password_hash = hash_password(password)
    db.commit()


def count_active_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True), User.is_active.is_(True))) or 0


def update_user(db: Session, user: User, *, ho_ten: str | None, is_admin: bool, is_active: bool) -> None:
    # Không cho tự khóa/hạ quyền quản trị cuối cùng — nếu không sẽ không ai quản lý được tài khoản nữa.
    removing_admin = user.is_admin and user.is_active and (not is_admin or not is_active)
    if removing_admin and count_active_admins(db) <= 1:
        raise ValueError("Phải còn ít nhất 1 tài khoản quản trị đang hoạt động.")
    user.ho_ten = ho_ten
    user.is_admin = is_admin
    user.is_active = is_active
    db.commit()


def ensure_first_admin(db: Session) -> None:
    """CSDL chưa có tài khoản nào + có biến môi trường ADMIN_PASSWORD -> tạo tài khoản quản trị đầu tiên.
    Đã có tài khoản thì không làm gì (đổi ADMIN_PASSWORD sau đó KHÔNG đổi mật khẩu đã có)."""
    if ADMIN_PASSWORD and not db.scalar(select(func.count()).select_from(User)):
        create_user(db, ADMIN_USERNAME, ADMIN_PASSWORD, ho_ten="Quản trị", is_admin=True)
