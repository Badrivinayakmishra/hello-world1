/**
 * Validation Utilities
 * Input validation with detailed error messages and password strength calculation.
 * Based on catalyst-research-match implementation.
 */

// Validation result type
interface ValidationResult {
  isValid: boolean;
  error?: string;
}

/**
 * Validate email format
 */
export function validateEmail(email: string): ValidationResult {
  if (!email || email.trim() === '') {
    return { isValid: false, error: 'Email is required' };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.trim())) {
    return { isValid: false, error: 'Please enter a valid email address' };
  }

  if (email.length > 320) {
    return { isValid: false, error: 'Email is too long' };
  }

  return { isValid: true };
}

/**
 * Validate password strength
 */
export function validatePassword(password: string): ValidationResult {
  if (!password) {
    return { isValid: false, error: 'Password is required' };
  }

  const errors: string[] = [];

  if (password.length < 8) {
    errors.push('at least 8 characters');
  }

  if (password.length > 128) {
    return { isValid: false, error: 'Password is too long (max 128 characters)' };
  }

  if (!/[a-z]/.test(password)) {
    errors.push('a lowercase letter');
  }

  if (!/[A-Z]/.test(password)) {
    errors.push('an uppercase letter');
  }

  if (!/[0-9]/.test(password)) {
    errors.push('a number');
  }

  if (errors.length > 0) {
    return {
      isValid: false,
      error: `Password must contain ${errors.join(', ')}`,
    };
  }

  return { isValid: true };
}

/**
 * Validate password match
 */
export function validatePasswordMatch(password: string, confirmPassword: string): ValidationResult {
  if (!confirmPassword) {
    return { isValid: false, error: 'Please confirm your password' };
  }

  if (password !== confirmPassword) {
    return { isValid: false, error: 'Passwords do not match' };
  }

  return { isValid: true };
}

/**
 * Validate name field
 */
export function validateName(name: string, fieldName = 'Name'): ValidationResult {
  if (!name || name.trim() === '') {
    return { isValid: false, error: `${fieldName} is required` };
  }

  const trimmed = name.trim();

  if (trimmed.length < 2) {
    return { isValid: false, error: `${fieldName} must be at least 2 characters` };
  }

  if (trimmed.length > 100) {
    return { isValid: false, error: `${fieldName} is too long (max 100 characters)` };
  }

  // Allow letters, spaces, hyphens, apostrophes, and periods
  const nameRegex = /^[a-zA-Z\s\-'.]+$/;
  if (!nameRegex.test(trimmed)) {
    return { isValid: false, error: `${fieldName} contains invalid characters` };
  }

  return { isValid: true };
}

/**
 * Get password strength level
 */
export function getPasswordStrength(password: string): {
  level: 'weak' | 'medium' | 'strong';
  score: number;
  color: string;
} {
  if (!password) {
    return { level: 'weak', score: 0, color: '#ef4444' };
  }

  let score = 0;

  // Length scoring
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (password.length >= 16) score += 1;

  // Character variety scoring
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;

  // Determine level
  if (score <= 3) {
    return { level: 'weak', score, color: '#ef4444' }; // Red
  } else if (score <= 5) {
    return { level: 'medium', score, color: '#f59e0b' }; // Amber
  } else {
    return { level: 'strong', score, color: '#22c55e' }; // Green
  }
}

/**
 * Validate organization name (optional field)
 */
export function validateOrganizationName(name: string): ValidationResult {
  if (!name || name.trim() === '') {
    // Organization is optional
    return { isValid: true };
  }

  const trimmed = name.trim();

  if (trimmed.length < 2) {
    return { isValid: false, error: 'Organization name must be at least 2 characters' };
  }

  if (trimmed.length > 255) {
    return { isValid: false, error: 'Organization name is too long (max 255 characters)' };
  }

  return { isValid: true };
}

/**
 * Validate all signup fields
 */
export function validateSignup(data: {
  email: string;
  password: string;
  fullName: string;
  organizationName?: string;
}): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  const emailResult = validateEmail(data.email);
  if (!emailResult.isValid && emailResult.error) {
    errors.email = emailResult.error;
  }

  const passwordResult = validatePassword(data.password);
  if (!passwordResult.isValid && passwordResult.error) {
    errors.password = passwordResult.error;
  }

  const nameResult = validateName(data.fullName, 'Full name');
  if (!nameResult.isValid && nameResult.error) {
    errors.fullName = nameResult.error;
  }

  if (data.organizationName) {
    const orgResult = validateOrganizationName(data.organizationName);
    if (!orgResult.isValid && orgResult.error) {
      errors.organizationName = orgResult.error;
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * Validate login fields
 */
export function validateLogin(data: {
  email: string;
  password: string;
}): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  const emailResult = validateEmail(data.email);
  if (!emailResult.isValid && emailResult.error) {
    errors.email = emailResult.error;
  }

  if (!data.password) {
    errors.password = 'Password is required';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

export default {
  validateEmail,
  validatePassword,
  validatePasswordMatch,
  validateName,
  validateOrganizationName,
  validateSignup,
  validateLogin,
  getPasswordStrength,
};
