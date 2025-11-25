#!/usr/bin/env python3
"""
Environment Variable Validation Script

This script validates that all required environment variables
are set and contain appropriate values for production deployment.

Usage: python scripts/validate-env.py [env-file]
Example: python scripts/validate-env.py .env.production
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


class ValidationResult:
    """Stores validation results"""
    def __init__(self):
        self.errors = 0
        self.warnings = 0
        self.checks = 0
        self.messages: List[Tuple[str, str]] = []  # (level, message)
    
    def add_error(self, message: str):
        self.errors += 1
        self.checks += 1
        self.messages.append(('error', message))
    
    def add_warning(self, message: str):
        self.warnings += 1
        self.checks += 1
        self.messages.append(('warning', message))
    
    def add_success(self, message: str):
        self.checks += 1
        self.messages.append(('success', message))
    
    def print_messages(self):
        for level, message in self.messages:
            if level == 'error':
                print(f"{Colors.RED}✗ {message}{Colors.NC}")
            elif level == 'warning':
                print(f"{Colors.YELLOW}⚠ {message}{Colors.NC}")
            else:
                print(f"{Colors.GREEN}✓ {message}{Colors.NC}")


def load_env_file(env_file: str) -> dict:
    """Load environment variables from file"""
    env_vars = {}
    
    if not os.path.exists(env_file):
        print(f"{Colors.RED}ERROR: Environment file '{env_file}' not found{Colors.NC}")
        print("Please create it from .env.production.example")
        sys.exit(1)
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key] = value
    
    return env_vars


def check_required(result: ValidationResult, env: dict, var_name: str):
    """Check if a required variable is set"""
    value = env.get(var_name, '')
    
    if not value:
        result.add_error(f"REQUIRED: {var_name} is not set")
    else:
        result.add_success(f"{var_name} is set")


def check_not_default(result: ValidationResult, env: dict, var_name: str, default_pattern: str):
    """Check if a variable has been changed from default"""
    value = env.get(var_name, '')
    
    if not value:
        result.add_error(f"SECURITY: {var_name} is not set")
    elif default_pattern.lower() in value.lower():
        result.add_error(f"SECURITY: {var_name} contains default/placeholder value")
    else:
        result.add_success(f"{var_name} has been customized")


def check_min_length(result: ValidationResult, env: dict, var_name: str, min_length: int):
    """Check if a variable meets minimum length requirement"""
    value = env.get(var_name, '')
    
    if not value:
        result.add_error(f"SECURITY: {var_name} is not set")
    elif len(value) < min_length:
        result.add_error(f"SECURITY: {var_name} is too short ({len(value)} chars, minimum {min_length})")
    else:
        result.add_success(f"{var_name} has sufficient length ({len(value)} chars)")


def check_equals(result: ValidationResult, env: dict, var_name: str, expected: str):
    """Check if a variable equals expected value"""
    value = env.get(var_name, '')
    
    if value != expected:
        result.add_error(f"CONFIG: {var_name} should be '{expected}' but is '{value}'")
    else:
        result.add_success(f"{var_name} is correctly set to '{expected}'")


def check_url_https(result: ValidationResult, env: dict, var_name: str):
    """Check if a URL uses HTTPS"""
    value = env.get(var_name, '')
    
    if not value:
        result.add_error(f"REQUIRED: {var_name} is not set")
    elif not value.startswith('https://'):
        result.add_warning(f"WARNING: {var_name} should use HTTPS in production")
    else:
        result.add_success(f"{var_name} uses HTTPS")


def check_pattern(result: ValidationResult, env: dict, var_name: str, pattern: str, description: str):
    """Check if a variable matches a regex pattern"""
    value = env.get(var_name, '')
    
    if not value:
        result.add_error(f"REQUIRED: {var_name} is not set")
    elif not re.match(pattern, value):
        result.add_error(f"FORMAT: {var_name} does not match expected format ({description})")
    else:
        result.add_success(f"{var_name} format is valid")


def validate_environment(env_file: str) -> int:
    """Main validation function"""
    print("=" * 44)
    print("Environment Variable Validation")
    print("=" * 44)
    print(f"Validating: {env_file}")
    print()
    
    # Load environment variables
    env = load_env_file(env_file)
    result = ValidationResult()
    
    # Application Configuration
    print("Checking Application Configuration...")
    check_required(result, env, "APP_NAME")
    check_equals(result, env, "ENVIRONMENT", "production")
    check_equals(result, env, "DEBUG", "False")
    print()
    
    # Database Configuration
    print("Checking Database Configuration...")
    check_required(result, env, "POSTGRES_USER")
    check_not_default(result, env, "POSTGRES_PASSWORD", "CHANGE_THIS")
    check_min_length(result, env, "POSTGRES_PASSWORD", 16)
    check_required(result, env, "POSTGRES_DB")
    check_pattern(result, env, "DATABASE_URL", r"^postgresql://", "PostgreSQL connection string")
    print()
    
    # Redis Configuration
    print("Checking Redis Configuration...")
    check_pattern(result, env, "REDIS_URL", r"^redis://", "Redis connection string")
    print()
    
    # Security Configuration
    print("Checking Security Configuration...")
    check_not_default(result, env, "JWT_SECRET_KEY", "CHANGE_THIS")
    check_min_length(result, env, "JWT_SECRET_KEY", 32)
    check_required(result, env, "JWT_ALGORITHM")
    check_not_default(result, env, "ENCRYPTION_KEY", "CHANGE_THIS")
    check_min_length(result, env, "ENCRYPTION_KEY", 32)
    print()
    
    # URL Configuration
    print("Checking URL Configuration...")
    check_url_https(result, env, "FRONTEND_URL")
    check_url_https(result, env, "BACKEND_URL")
    check_url_https(result, env, "VITE_API_URL")
    check_required(result, env, "CORS_ORIGINS")
    print()
    
    # External API Configuration
    print("Checking External API Configuration...")
    check_not_default(result, env, "ANTHROPIC_API_KEY", "your_anthropic")
    check_pattern(result, env, "ANTHROPIC_API_KEY", r"^sk-ant-", "Anthropic API key format")
    check_required(result, env, "ANTHROPIC_MODEL")
    print()
    
    # Discord Configuration
    print("Checking Discord Configuration...")
    check_not_default(result, env, "DISCORD_TOKEN", "your_discord")
    check_not_default(result, env, "DISCORD_CLIENT_ID", "your_discord")
    check_not_default(result, env, "DISCORD_CLIENT_SECRET", "your_discord")
    check_url_https(result, env, "DISCORD_REDIRECT_URI")
    print()
    
    # Optional Configuration
    print("Checking Optional Configuration...")
    if env.get("DOMAIN"):
        result.add_success(f"DOMAIN is set: {env['DOMAIN']}")
    else:
        result.add_warning("WARNING: DOMAIN not set (needed for SSL certificates)")
    
    if env.get("LETSENCRYPT_EMAIL"):
        result.add_success("LETSENCRYPT_EMAIL is set")
    else:
        result.add_warning("WARNING: LETSENCRYPT_EMAIL not set (needed for SSL certificates)")
    print()
    
    # Print all messages
    result.print_messages()
    print()
    
    # Summary
    print("=" * 44)
    print("Validation Summary")
    print("=" * 44)
    print(f"Total checks: {result.checks}")
    print(f"{Colors.GREEN}Passed: {result.checks - result.errors - result.warnings}{Colors.NC}")
    print(f"{Colors.YELLOW}Warnings: {result.warnings}{Colors.NC}")
    print(f"{Colors.RED}Errors: {result.errors}{Colors.NC}")
    print()
    
    if result.errors > 0:
        print(f"{Colors.RED}VALIDATION FAILED{Colors.NC}")
        print("Please fix the errors above before deploying to production")
        return 1
    elif result.warnings > 0:
        print(f"{Colors.YELLOW}VALIDATION PASSED WITH WARNINGS{Colors.NC}")
        print("Review the warnings above - they may indicate security or configuration issues")
        return 0
    else:
        print(f"{Colors.GREEN}VALIDATION PASSED{Colors.NC}")
        print("All environment variables are properly configured")
        return 0


if __name__ == "__main__":
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env.production"
    exit_code = validate_environment(env_file)
    sys.exit(exit_code)
