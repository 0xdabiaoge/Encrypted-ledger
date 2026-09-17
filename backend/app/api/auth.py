"""
Encrypted Ledger - Authentication & Access API
Admin login, session verification, setup token initialization, and IP brute-force guard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    rate_limiter,
)
from app.database.db import get_db_session
from app.database.models import AdminUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupAdminRequest(BaseModel):
    setup_token: str
    username: str
    password: str


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.post("/login")
async def login(req: LoginRequest, request: Request, session=Depends(get_db_session)):
    client_ip = get_client_ip(request)
    is_blocked, remaining_sec = rate_limiter.is_blocked(client_ip)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"由于多次登录失败，该 IP 已被临时锁定，请在 {remaining_sec} 秒后重试"
        )

    stmt = select(AdminUser).where(AdminUser.username == req.username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        is_now_blocked, block_time = rate_limiter.record_failure(client_ip)
        msg = f"用户名或密码错误。连续失败过多将锁定 IP。"
        if is_now_blocked:
            msg = f"失败次数过多，IP 已被封锁 {block_time} 秒。"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)

    rate_limiter.record_success(client_ip)
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"status": "success", "access_token": token, "token_type": "bearer", "username": user.username}


@router.post("/setup")
async def setup_admin(req: SetupAdminRequest, session=Depends(get_db_session)):
    if req.setup_token != settings.ADMIN_SETUP_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无效的系统初始化令牌 SETUP_TOKEN")

    stmt = select(AdminUser).where(AdminUser.username == req.username)
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该管理员用户名已存在")

    pw_hash = hash_password(req.password)
    new_user = AdminUser(username=req.username, password_hash=pw_hash, role="superadmin")
    session.add(new_user)
    await session.commit()
    token = create_access_token({"sub": new_user.username, "role": new_user.role})
    return {"status": "success", "message": "管理员账号创建成功", "access_token": token}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


async def verify_admin_session(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少身份验证凭证 Bearer Token")
    token = auth_header[7:]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或已过期的登录令牌")
    return payload


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    session=Depends(get_db_session),
    admin_payload=Depends(verify_admin_session)
):
    username = admin_payload.get("sub")
    stmt = select(AdminUser).where(AdminUser.username == username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user or not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码验证错误")

    user.password_hash = hash_password(req.new_password)
    await session.commit()
    return {"status": "success", "message": "管理员密码修改成功"}


@router.get("/me")
async def get_current_admin(admin_payload=Depends(verify_admin_session)):
    return {
        "status": "success",
        "username": admin_payload.get("sub"),
        "role": admin_payload.get("role", "admin")
    }

