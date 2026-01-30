"""
Input Validators
Email, password, and general input validation utilities.
"""

import re
from typing import Tuple, Optional


class EmailValidator:
    """Validate email addresses"""

    # RFC 5322 compliant email regex (simplified)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )

    # Common disposable email domains to block
    DISPOSABLE_DOMAINS = {
        'tempmail.com', 'throwaway.email', '10minutemail.com',
        'guerrillamail.com', 'mailinator.com', 'maildrop.cc',
        'yopmail.com', 'temp-mail.org', 'getnada.com'
    }

    @classmethod
    def validate(cls, email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email address.

        Args:
            email: Email address to validate

        Returns:
            (is_valid, error_message)
        """
        if not email:
            return False, "Email is required"

        if len(email) > 320:  # RFC 5321 max length
            return False, "Email is too long (max 320 characters)"

        if not cls.EMAIL_REGEX.match(email):
            return False, "Invalid email format"

        # Check for disposable email
        domain = email.split('@')[-1].lower()
        if domain in cls.DISPOSABLE_DOMAINS:
            return False, "Disposable email addresses are not allowed"

        return True, None

    @classmethod
    def normalize(cls, email: str) -> str:
        """
        Normalize email (lowercase, strip whitespace).

        Args:
            email: Email to normalize

        Returns:
            Normalized email
        """
        return email.strip().lower()


class PasswordValidator:
    """Validate password strength"""

    MIN_LENGTH = 8
    MAX_LENGTH = 128

    # Common passwords to block
    COMMON_PASSWORDS = {
        'password', '12345678', 'password123', 'qwerty', 'abc123',
        'monkey', '1234567890', 'letmein', 'trustno1', 'dragon',
        'baseball', 'iloveyou', 'master', 'sunshine', 'ashley',
        'bailey', 'passw0rd', 'shadow', '123123', '654321',
        'superman', 'qazwsx', 'michael', 'football', 'welcome'
    }

    @classmethod
    def validate(cls, password: str, email: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate password strength.

        Requirements:
        - Minimum 8 characters
        - Maximum 128 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        - Not a common password
        - Not too similar to email

        Args:
            password: Password to validate
            email: Optional email to check similarity

        Returns:
            (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"

        # Length check
        if len(password) < cls.MIN_LENGTH:
            return False, f"Password must be at least {cls.MIN_LENGTH} characters"

        if len(password) > cls.MAX_LENGTH:
            return False, f"Password must be less than {cls.MAX_LENGTH} characters"

        # Complexity checks
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)

        missing = []
        if not has_upper:
            missing.append("uppercase letter")
        if not has_lower:
            missing.append("lowercase letter")
        if not has_digit:
            missing.append("number")
        if not has_special:
            missing.append("special character (!@#$%^&*...)")

        if missing:
            return False, f"Password must include: {', '.join(missing)}"

        # Check against common passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            return False, "This password is too common. Please choose a stronger password."

        # Check similarity to email
        if email:
            email_local = email.split('@')[0].lower()
            if email_local in password.lower():
                return False, "Password should not contain your email address"

        return True, None

    @classmethod
    def get_strength_score(cls, password: str) -> int:
        """
        Calculate password strength score (0-100).

        Args:
            password: Password to score

        Returns:
            Strength score
        """
        score = 0

        # Length bonus
        if len(password) >= 8:
            score += 20
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 10

        # Character variety
        if any(c.isupper() for c in password):
            score += 15
        if any(c.islower() for c in password):
            score += 15
        if any(c.isdigit() for c in password):
            score += 15
        if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            score += 15

        # Penalize common passwords
        if password.lower() in cls.COMMON_PASSWORDS:
            score -= 50

        return max(0, min(100, score))


class InputValidator:
    """General input validation"""

    @staticmethod
    def validate_name(name: str, field_name: str = "Name") -> Tuple[bool, Optional[str]]:
        """
        Validate name field.

        Args:
            name: Name to validate
            field_name: Field name for error messages

        Returns:
            (is_valid, error_message)
        """
        if not name:
            return False, f"{field_name} is required"

        if len(name) < 2:
            return False, f"{field_name} must be at least 2 characters"

        if len(name) > 255:
            return False, f"{field_name} must be less than 255 characters"

        # Basic validation - allow letters, spaces, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", name):
            return False, f"{field_name} contains invalid characters"

        return True, None

    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number.

        Args:
            phone: Phone number to validate

        Returns:
            (is_valid, error_message)
        """
        if not phone:
            return True, None  # Phone is optional

        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)

        # Check if it's a valid phone number (digits and optional +)
        if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
            return False, "Invalid phone number format. Use format: +1-555-0123"

        return True, None

    @staticmethod
    def sanitize_text(text: str, max_length: int = 10000) -> str:
        """
        Sanitize text input (remove dangerous characters, trim).

        Args:
            text: Text to sanitize
            max_length: Maximum length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Strip whitespace
        text = text.strip()

        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length]

        # Remove null bytes and other control characters
        text = text.replace('\x00', '')

        return text


def validate_signup_data(email: str, password: str, full_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate signup form data.

    Args:
        email: Email address
        password: Password
        full_name: Full name

    Returns:
        (is_valid, error_message)
    """
    # Validate email
    is_valid, error = EmailValidator.validate(email)
    if not is_valid:
        return False, error

    # Validate password
    is_valid, error = PasswordValidator.validate(password, email)
    if not is_valid:
        return False, error

    # Validate name
    is_valid, error = InputValidator.validate_name(full_name, "Full name")
    if not is_valid:
        return False, error

    return True, None


def validate_login_data(email: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate login form data.

    Args:
        email: Email address
        password: Password

    Returns:
        (is_valid, error_message)
    """
    # Basic validation for login (don't reveal if email exists)
    if not email:
        return False, "Email is required"

    if not password:
        return False, "Password is required"

    # Don't validate email format on login - could leak info
    # Just normalize it
    email = EmailValidator.normalize(email)

    return True, None
