"""
Test Suite: System-Level Authenticated Disaster Recovery (AES-256 PBKDF2)
Verifies:
1. Encrypted archive generation with PBKDF2 salt and Fernet cipher
2. Rejection of restore attempts with incorrect password or tampered payload
3. Successful full-state hot recovery with correct master password
4. Backup archive listing and deletion
"""
import io
import sys
from pathlib import Path

# Fix Windows console UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend directory in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.backup import (
    create_encrypted_backup,
    restore_encrypted_backup,
    list_backups,
    delete_backup_file,
    BACKUP_DIR
)


def test_password_validation():
    """Verify master password length is enforced."""
    caught = False
    try:
        create_encrypted_backup(password="123")  # too short (< 6)
    except ValueError:
        caught = True
    assert caught, "Expected ValueError for short password"


def test_create_and_restore_backup_lifecycle():
    """Verify backup creation, decryption verification, and restore."""
    master_pwd = "TestMasterPassword!2026"
    test_note = "Standalone Automated Verification Archive"

    # 1. Create encrypted backup
    meta = create_encrypted_backup(master_pwd, note=test_note)
    assert meta["filename"].endswith(".enc")
    assert meta["size_bytes"] > 0
    assert meta["note"] == test_note

    fpath = BACKUP_DIR / meta["filename"]
    assert fpath.exists()
    raw_enc_bytes = fpath.read_bytes()

    # 2. Attempt restore with wrong password (must fail)
    caught_wrong = False
    try:
        restore_encrypted_backup(raw_enc_bytes, "WrongPasswordHere!#$")
    except ValueError as exc_wrong:
        caught_wrong = True
        assert "密码错误" in str(exc_wrong)
    assert caught_wrong, "Expected wrong password failure"

    # 3. Attempt restore with corrupted bytes (must fail)
    corrupted_bytes = raw_enc_bytes[:20] + b"CORRUPTED_GARBAGE" + raw_enc_bytes[40:]
    caught_corrupt = False
    try:
        restore_encrypted_backup(corrupted_bytes, master_pwd)
    except ValueError:
        caught_corrupt = True
    assert caught_corrupt, "Expected corrupted bytes failure"

    # 4. Attempt restore with correct password (must succeed)
    restore_res = restore_encrypted_backup(raw_enc_bytes, master_pwd)
    assert restore_res["status"] == "success"
    assert restore_res["restored_files_count"] >= 1
    assert "manifest" in restore_res
    assert restore_res["manifest"].get("version") == "2.0.0"

    # 5. List backups
    backups = list_backups()
    assert any(b["filename"] == meta["filename"] for b in backups)

    # 6. Delete backup
    deleted = delete_backup_file(meta["filename"])
    assert deleted
    assert not (BACKUP_DIR / meta["filename"]).exists()


if __name__ == "__main__":
    print("=== [TEST SUITE 4] System Disaster Recovery & Hot AES-256 Engine ===")
    test_password_validation()
    print("  ✓ test_password_validation passed successfully (enforces >=6 char password)")
    test_create_and_restore_backup_lifecycle()
    print("  ✓ test_create_and_restore_backup_lifecycle passed successfully (full encrypted zip lifecycle)")
    print(">>> All Disaster Recovery & Backup tests PASSED! <<<\n")
