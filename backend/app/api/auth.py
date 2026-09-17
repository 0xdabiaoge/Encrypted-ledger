"""
Encrypted Ledger - Authentication & Commercial User Access API
Superadmin credentials, member registration (open & invite-only), role-based session
verification, and public vs admin data masking tokens.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    rate_limiter,
)
from app.database.db import get_db_session
from app.database.models import AdminUser, InviteCode

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: Optional[str] = None


class SetupAdminRequest(BaseModel):
    setup_token: str
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    telegram_chat_id: Optional[str] = None


class CreateInviteCodeRequest(BaseModel):
    code: Optional[str] = None
    max_uses: Optional[int] = 1
    note: Optional[str] = ""


class SetRegistrationModeRequest(BaseModel):
    mode: str  # "open" | "invite_only"


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def get_optional_session(request: Request) -> Optional[dict]:
    """Extract and decode JWT session if present; returns None if unauthenticated."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return decode_access_token(token)


async def verify_any_session(request: Request) -> dict:
    """Verify session for any registered user or admin."""
    payload = await get_optional_session(request)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少有效访问凭证 Bearer Token")
    return payload


async def verify_admin_session(request: Request) -> dict:
    """Verify session strictly for Superadmin or Admin roles."""
    payload = await verify_any_session(request)
    role = payload.get("role", "user")
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="越权访问拒绝：该操作仅限超级管理员权限")
    return payload


@router.post("/login")
async def login(req: LoginRequest, request: Request, session=Depends(get_db_session)):
    client_ip = get_client_ip(request)
    is_blocked, remaining_sec = rate_limiter.is_blocked(client_ip)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"由于多次登录失败，该 IP 已被临时封锁，请在 {remaining_sec} 秒后重试"
        )

    stmt = select(AdminUser).where(AdminUser.username == req.username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        is_now_blocked, block_time = rate_limiter.record_failure(client_ip)
        msg = "用户名或密码错误。连续失败将触发安全防御锁定 IP。"
        if is_now_blocked:
            msg = f"登录失败次数过多，IP 已被安全拦截封锁 {block_time} 秒。"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号已被停用，请联系超级管理员")

    rate_limiter.record_success(client_ip)
    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }


@router.post("/register")
async def register(req: RegisterRequest, session=Depends(get_db_session)):
    """Commercial member registration supporting open or invite-code-only modes."""
    # 1. Check registration mode
    if settings.REGISTRATION_MODE == "invite_only" and not req.invite_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前系统开启了专属邀请制，请输入有效邀请码")

    # 2. Validate invite code if provided
    invite_obj = None
    if req.invite_code:
        code_str = req.invite_code.strip().upper()
        stmt = select(InviteCode).where(InviteCode.code == code_str, InviteCode.is_active == True)
        res = await session.execute(stmt)
        invite_obj = res.scalar_one_or_none()

        if not invite_obj:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效或已被作废的邀请码")
        if invite_obj.max_uses > 0 and invite_obj.used_count >= invite_obj.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邀请码已被使用完毕")

    # 3. Check username uniqueness
    stmt = select(AdminUser).where(AdminUser.username == req.username.strip())
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该用户名已被注册，请更换")

    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="登录密码长度至少需要 6 位字符")

    pw_hash = hash_password(req.password)
    new_user = AdminUser(
        username=req.username.strip(),
        password_hash=pw_hash,
        role="user",
        invite_code=req.invite_code.strip().upper() if req.invite_code else None,
        is_active=True
    )
    session.add(new_user)

    if invite_obj:
        invite_obj.used_count += 1

    await session.commit()

    token = create_access_token({"sub": new_user.username, "role": new_user.role})
    return {
        "status": "success",
        "message": "用户注册成功，欢迎加入 Encrypted Ledger",
        "access_token": token,
        "username": new_user.username,
        "role": new_user.role
    }


@router.get("/registration-mode")
async def get_registration_mode():
    """Check whether platform is open or invite-code only."""
    return {
        "registration_mode": settings.REGISTRATION_MODE,
        "is_invite_only": settings.REGISTRATION_MODE == "invite_only"
    }


@router.post("/registration-mode", dependencies=[Depends(verify_admin_session)])
async def set_registration_mode(req: SetRegistrationModeRequest):
    """Toggle between open registration and invite-only mode."""
    mode = req.mode.lower()
    if mode not in ("open", "invite_only"):
        raise HTTPException(status_code=400, detail="模式仅支持 open 或 invite_only")
    settings.REGISTRATION_MODE = mode
    return {"status": "success", "registration_mode": settings.REGISTRATION_MODE}


@router.get("/me")
async def get_current_user(session_payload=Depends(verify_any_session), session=Depends(get_db_session)):
    """Retrieve profile and role for current authenticated user."""
    username = session_payload.get("sub")
    stmt = select(AdminUser).where(AdminUser.username == username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "status": "success",
        "username": user.username,
        "role": user.role,
        "is_admin": user.role in ("superadmin", "admin"),
        "telegram_chat_id": user.telegram_chat_id or "",
        "invite_code": user.invite_code or ""
    }


@router.post("/profile/telegram")
async def update_user_telegram(
    req: UpdateProfileRequest,
    session_payload=Depends(verify_any_session),
    session=Depends(get_db_session)
):
    """Allow user to bind their personal Telegram Chat ID for signal notifications."""
    username = session_payload.get("sub")
    stmt = select(AdminUser).where(AdminUser.username == username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.telegram_chat_id = req.telegram_chat_id.strip() if req.telegram_chat_id else None
    await session.commit()
    return {"status": "success", "message": "Telegram 通知 Chat ID 绑定成功", "telegram_chat_id": user.telegram_chat_id}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    session=Depends(get_db_session),
    admin_payload=Depends(verify_any_session)
):
    username = admin_payload.get("sub")
    stmt = select(AdminUser).where(AdminUser.username == username)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user or not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码验证错误")

    user.password_hash = hash_password(req.new_password)
    await session.commit()
    return {"status": "success", "message": "登录密码修改成功"}


# ------------------------------------------------------------------------------
# Superadmin Invite Code Management
# ------------------------------------------------------------------------------

@router.get("/invite-codes", dependencies=[Depends(verify_admin_session)])
async def list_invite_codes(session=Depends(get_db_session)):
    """List all registered invite codes with usage counts."""
    stmt = select(InviteCode).order_by(InviteCode.created_at.desc())
    res = await session.execute(stmt)
    codes = res.scalars().all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "created_by": c.created_by,
            "max_uses": c.max_uses,
            "used_count": c.used_count,
            "is_active": c.is_active,
            "note": c.note,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for c in codes
    ]


@router.post("/invite-codes", dependencies=[Depends(verify_admin_session)])
async def create_invite_code(
    req: CreateInviteCodeRequest,
    admin_payload=Depends(verify_admin_session),
    session=Depends(get_db_session)
):
    """Generate a new commercial invite code."""
    code_str = req.code.strip().upper() if req.code else f"EL-{secrets.token_hex(3).upper()}"
    stmt = select(InviteCode).where(InviteCode.code == code_str)
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邀请码已存在，请更换")

    new_code = InviteCode(
        code=code_str,
        created_by=admin_payload.get("sub", "admin"),
        max_uses=req.max_uses if req.max_uses is not None else 1,
        note=req.note or "",
        is_active=True
    )
    session.add(new_code)
    await session.commit()
    return {"status": "success", "message": f"邀请码 {code_str} 创建成功", "code": code_str}


@router.delete("/invite-codes/{code}", dependencies=[Depends(verify_admin_session)])
async def revoke_invite_code(code: str, session=Depends(get_db_session)):
    """Revoke/deactivate an existing invite code."""
    stmt = select(InviteCode).where(InviteCode.code == code.strip().upper())
    res = await session.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="未找到该邀请码")
    c.is_active = False
    await session.commit()
    return {"status": "success", "message": f"邀请码 {code.upper()} 已作废禁用"}
