#!/usr/bin/env python3
"""
Migration script to move avatars and logos from JSON files to database
"""
import sys
import json
from pathlib import Path

# Add parent directory to path to import web modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.database import init_db, get_db, get_all_avatars, get_all_logos, save_avatar_to_db, save_logo_to_db
from flask import Flask

def migrate_avatars():
    """Migrate avatars from avatar_library.json to database"""
    print("[MIGRATION] Migrating avatars...")
    
    # Check JSON file locations
    json_paths = [
        Path('avatar_library.json'),
        Path('web/avatar_library.json'),
    ]
    
    avatar_json = None
    for path in json_paths:
        if path.exists():
            avatar_json = path
            break
    
    if not avatar_json:
        print("[MIGRATION] No avatar_library.json found, skipping avatars")
        return 0
    
    try:
        with open(avatar_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            avatars = data.get('avatars', [])
    except Exception as e:
        print(f"[MIGRATION] Error reading avatar_library.json: {e}")
        return 0
    
    if not avatars:
        print("[MIGRATION] No avatars found in JSON file")
        return 0
    
    # Check if database already has avatars
    existing = get_all_avatars()
    if existing:
        print(f"[MIGRATION] Database already has {len(existing)} avatars")
        response = input("Do you want to overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("[MIGRATION] Skipping avatar migration")
            return 0
    
    migrated = 0
    for avatar in avatars:
        try:
            # Ensure required fields
            if not avatar.get('id'):
                print(f"[MIGRATION] Skipping avatar without ID: {avatar}")
                continue
            
            # Extract filename from image_url if needed
            if not avatar.get('filename') and avatar.get('image_url'):
                # Extract filename from URL: http://localhost:5000/avatars/filename.png
                url = avatar.get('image_url', '')
                if '/' in url:
                    avatar['filename'] = url.split('/')[-1]
            
            # Save to database
            save_avatar_to_db(avatar)
            migrated += 1
            print(f"[MIGRATION] Migrated avatar: {avatar.get('name', avatar.get('id'))}")
        except Exception as e:
            print(f"[MIGRATION] Error migrating avatar {avatar.get('id')}: {e}")
    
    print(f"[MIGRATION] ✅ Migrated {migrated} avatars to database")
    return migrated

def migrate_logos():
    """Migrate logos from logo_library.json to database"""
    print("[MIGRATION] Migrating logos...")
    
    # Check JSON file locations
    json_paths = [
        Path('logo_library.json'),
        Path('web/logo_library.json'),
    ]
    
    logo_json = None
    for path in json_paths:
        if path.exists():
            logo_json = path
            break
    
    if not logo_json:
        print("[MIGRATION] No logo_library.json found, skipping logos")
        return 0
    
    try:
        with open(logo_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logos = data.get('logos', [])
    except Exception as e:
        print(f"[MIGRATION] Error reading logo_library.json: {e}")
        return 0
    
    if not logos:
        print("[MIGRATION] No logos found in JSON file")
        return 0
    
    # Check if database already has logos
    existing = get_all_logos()
    if existing:
        print(f"[MIGRATION] Database already has {len(existing)} logos")
        response = input("Do you want to overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("[MIGRATION] Skipping logo migration")
            return 0
    
    migrated = 0
    for logo in logos:
        try:
            # Ensure required fields
            if not logo.get('id'):
                print(f"[MIGRATION] Skipping logo without ID: {logo}")
                continue
            
            # Ensure filename exists
            if not logo.get('filename') and logo.get('url'):
                url = logo.get('url', '')
                if '/' in url:
                    logo['filename'] = url.split('/')[-1]
            
            # Save to database
            save_logo_to_db(logo)
            migrated += 1
            print(f"[MIGRATION] Migrated logo: {logo.get('name', logo.get('id'))}")
        except Exception as e:
            print(f"[MIGRATION] Error migrating logo {logo.get('id')}: {e}")
    
    print(f"[MIGRATION] ✅ Migrated {migrated} logos to database")
    return migrated

def main():
    """Run migration"""
    print("=" * 60)
    print("Avatar and Logo Migration to Database")
    print("=" * 60)
    print()
    
    # Initialize database (creates tables if needed)
    print("[MIGRATION] Initializing database...")
    init_db()
    print("[MIGRATION] ✅ Database initialized")
    print()
    
    # Migrate avatars
    avatar_count = migrate_avatars()
    print()
    
    # Migrate logos
    logo_count = migrate_logos()
    print()
    
    print("=" * 60)
    print("Migration Complete!")
    print(f"  Avatars migrated: {avatar_count}")
    print(f"  Logos migrated: {logo_count}")
    print("=" * 60)
    print()
    print("Note: JSON files are kept as backup. You can delete them")
    print("      after verifying the migration was successful.")

if __name__ == '__main__':
    main()

