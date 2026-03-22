"""Authentication module for demo application."""

from typing import Optional
import hashlib
import secrets


class AuthService:
    """Simple authentication service with password hashing."""
    
    def __init__(self, pepper: str = "default-pepper"):
        """Initialize auth service with secret pepper."""
        self.pepper = pepper
        self.users = {}
    
    def hash_password(self, password: str) -> str:
        """Hash password with pepper using SHA-256."""
        salted = password + self.pepper
        return hashlib.sha256(salted.encode()).hexdigest()
    
    def register(self, username: str, password: str) -> bool:
        """Register a new user.
        
        Args:
            username: Username to register.
            password: Plain text password.
            
        Returns:
            True if registration succeeded, False if username exists.
        """
        if username in self.users:
            return False
        
        self.users[username] = {
            "password_hash": self.hash_password(password),
            "salt": secrets.token_hex(16),
        }
        return True
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user.
        
        Args:
            username: Username to authenticate.
            password: Plain text password.
            
        Returns:
            True if authentication succeeded.
        """
        if username not in self.users:
            return False
        
        expected_hash = self.users[username]["password_hash"]
        actual_hash = self.hash_password(password)
        
        return secrets.compare_digest(actual_hash, expected_hash)
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password.
        
        Args:
            username: Username whose password to change.
            old_password: Current password for verification.
            new_password: New password to set.
            
        Returns:
            True if password change succeeded.
        """
        if not self.authenticate(username, old_password):
            return False
        
        self.users[username]["password_hash"] = self.hash_password(new_password)
        return True


def create_session(user_id: int) -> str:
    """Create a session token for a user.
    
    Args:
        user_id: User ID to create session for.
        
    Returns:
        Session token.
    """
    return secrets.token_urlsafe(32)
