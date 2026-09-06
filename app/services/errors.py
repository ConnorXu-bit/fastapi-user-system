"""业务层异常：由路由层捕获并转换为 HTTP 响应。"""


class ServiceError(Exception):
    """业务层异常基类。"""


class EmailAlreadyRegisteredError(ServiceError):
    """注册邮箱已存在。"""


class UserNotFoundError(ServiceError):
    """用户不存在。"""


class RoleNotFoundError(ServiceError):
    """角色不存在。"""


class PermissionDeniedError(ServiceError):
    """用户缺少所需权限。"""
