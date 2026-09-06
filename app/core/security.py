"""密码哈希与验证工具。"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希值匹配。"""
    return pwd_context.verify(plain_password, hashed_password)
