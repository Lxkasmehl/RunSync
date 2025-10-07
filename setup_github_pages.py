#!/usr/bin/env python3
"""
Setup script for GitHub Pages deployment
This script helps you configure your RunSync project for GitHub Pages + GitHub Actions
"""

import os
import re
import secrets
import string

def generate_password(length=32):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def update_github_config():
    """Update GitHub configuration files with user input"""
    print("🚀 RunSync GitHub Pages Setup")
    print("=" * 50)
    
    # Get user input
    github_username = input("GitHub Username: ").strip()
    repo_name = input("Repository Name: ").strip()
    
    # Generate secure password
    admin_password = generate_password()
    print(f"\n🔑 Generated secure password: {admin_password}")
    print("💾 Save this password - you'll need it for GitHub Secrets!")
    
    # Update github-api.js
    api_js_path = "docs/github-api.js"
    if os.path.exists(api_js_path):
        with open(api_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = re.sub(r"this\.owner = '[^']*'", f"this.owner = '{github_username}'", content)
        content = re.sub(r"this\.repo = '[^']*'", f"this.repo = '{repo_name}'", content)
        
        with open(api_js_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Updated {api_js_path}")
    
    # Update index.html
    index_path = "docs/index.html"
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update password
        content = re.sub(
            r"const CORRECT_PASSWORD = '[^']*'",
            f"const CORRECT_PASSWORD = '{admin_password}'",
            content
        )
        
        # Update workflow link
        content = re.sub(
            r"https://github\.com/YOUR_USERNAME/YOUR_REPO/actions",
            f"https://github.com/{github_username}/{repo_name}/actions",
            content
        )
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Updated {index_path}")
    
    # Create .env file for local development
    env_content = f"""# RunSync Environment Variables
# Copy these to GitHub Repository Secrets

ADMIN_PASSWORD={admin_password}

# GitHub Configuration
GITHUB_USERNAME={github_username}
GITHUB_REPO={repo_name}

# Your website will be available at:
# https://{github_username}.github.io/{repo_name}/
"""
    
    with open('.env.github', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✅ Created .env.github file")
    
    # Display next steps
    print("\n" + "=" * 50)
    print("📋 Next Steps:")
    print("=" * 50)
    print(f"1. Create GitHub repository: {repo_name}")
    print(f"2. Push your code to GitHub")
    print(f"3. Go to Settings → Secrets and variables → Actions")
    print(f"4. Add secret: ADMIN_PASSWORD = {admin_password}")
    print(f"5. Go to Settings → Pages")
    print(f"6. Set Source to 'GitHub Actions'")
    print(f"7. Your website will be at: https://{github_username}.github.io/{repo_name}/")
    print("\n🔑 Remember to save your password!")
    print("=" * 50)

def create_git_commands():
    """Generate git commands for deployment"""
    print("\n📝 Git Commands:")
    print("=" * 30)
    print("git init")
    print("git add .")
    print("git commit -m 'Initial commit'")
    print("git branch -M main")
    print("git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git")
    print("git push -u origin main")

if __name__ == "__main__":
    try:
        update_github_config()
        create_git_commands()
    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please check your input and try again")
