"""
Duplicate Contacts Cleanup Script for BlackBook
Run after deploying the fixed sync code to clean up existing duplicates.

Usage:
    docker exec -it blackbook-app python /app/cleanup_duplicates.py
"""

import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://blackbook:blackbook@db:5432/perunsblackbook")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

def find_duplicate_emails():
    """Find emails that appear on multiple persons."""
    result = db.execute(text("""
        SELECT email, array_agg(person_id) as person_ids, COUNT(*) as cnt
        FROM person_emails
        GROUP BY email
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """))
    return result.fetchall()

def get_person_data_score(person_id):
    """Score a person by how much data they have (higher = more data)."""
    result = db.execute(text("""
        SELECT 
            p.id,
            (CASE WHEN p.first_name IS NOT NULL AND p.first_name != '' THEN 1 ELSE 0 END +
             CASE WHEN p.last_name IS NOT NULL AND p.last_name != '' THEN 1 ELSE 0 END +
             CASE WHEN p.phone IS NOT NULL AND p.phone != '' THEN 1 ELSE 0 END +
             CASE WHEN p.linkedin IS NOT NULL AND p.linkedin != '' THEN 1 ELSE 0 END +
             CASE WHEN p.twitter IS NOT NULL AND p.twitter != '' THEN 1 ELSE 0 END +
             CASE WHEN p.title IS NOT NULL AND p.title != '' THEN 1 ELSE 0 END +
             CASE WHEN p.notes IS NOT NULL AND p.notes != '' THEN 1 ELSE 0 END +
             CASE WHEN p.google_resource_name IS NOT NULL THEN 2 ELSE 0 END +
             CASE WHEN p.profile_picture IS NOT NULL THEN 1 ELSE 0 END) as score,
            p.google_resource_name,
            p.first_name,
            p.last_name
        FROM persons p
        WHERE p.id = :person_id
    """), {"person_id": str(person_id)})
    return result.fetchone()

def merge_persons(keep_id, delete_ids):
    """Merge duplicate persons - move relationships to keeper, delete others."""
    for delete_id in delete_ids:
        # Move emails (skip if already exists on keeper)
        db.execute(text("""
            UPDATE person_emails 
            SET person_id = :keep_id 
            WHERE person_id = :delete_id 
            AND email NOT IN (SELECT email FROM person_emails WHERE person_id = :keep_id)
        """), {"keep_id": str(keep_id), "delete_id": str(delete_id)})
        
        # Delete duplicate emails that couldn't be moved
        db.execute(text("""
            DELETE FROM person_emails WHERE person_id = :delete_id
        """), {"delete_id": str(delete_id)})
        
        # Move tags (skip if already exists on keeper)
        db.execute(text("""
            UPDATE person_tags 
            SET person_id = :keep_id 
            WHERE person_id = :delete_id 
            AND tag_id NOT IN (SELECT tag_id FROM person_tags WHERE person_id = :keep_id)
        """), {"keep_id": str(keep_id), "delete_id": str(delete_id)})
        
        # Delete duplicate tags that couldn't be moved
        db.execute(text("""
            DELETE FROM person_tags WHERE person_id = :delete_id
        """), {"delete_id": str(delete_id)})
        
        # Move interactions
        db.execute(text("""
            UPDATE interactions SET person_id = :keep_id WHERE person_id = :delete_id
        """), {"keep_id": str(keep_id), "delete_id": str(delete_id)})
        
        # Move organization links
        db.execute(text("""
            UPDATE person_organizations 
            SET person_id = :keep_id 
            WHERE person_id = :delete_id
            AND organization_id NOT IN (SELECT organization_id FROM person_organizations WHERE person_id = :keep_id)
        """), {"keep_id": str(keep_id), "delete_id": str(delete_id)})
        
        db.execute(text("""
            DELETE FROM person_organizations WHERE person_id = :delete_id
        """), {"delete_id": str(delete_id)})
        
        # Delete the duplicate person
        db.execute(text("""
            DELETE FROM persons WHERE id = :delete_id
        """), {"delete_id": str(delete_id)})
    
    db.commit()

def main():
    print("=" * 60)
    print("BlackBook Duplicate Contacts Cleanup")
    print("=" * 60)
    
    # Find duplicates
    duplicates = find_duplicate_emails()
    print(f"\nFound {len(duplicates)} emails with duplicates")
    
    if not duplicates:
        print("No duplicates to clean up!")
        return
    
    total_merged = 0
    total_deleted = 0
    
    for email, person_ids, cnt in duplicates:
        print(f"\n{email}: {cnt} duplicates")
        
        # Score each person
        scores = []
        for pid in person_ids:
            data = get_person_data_score(pid)
            if data:
                scores.append((pid, data.score, data.google_resource_name, data.first_name, data.last_name))
                print(f"  - {pid}: score={data.score}, google_id={'Yes' if data.google_resource_name else 'No'}, name={data.first_name} {data.last_name}")
        
        # Keep the one with highest score (prefer ones with google_resource_name)
        scores.sort(key=lambda x: (x[2] is not None, x[1]), reverse=True)
        
        if len(scores) > 1:
            keep_id = scores[0][0]
            delete_ids = [s[0] for s in scores[1:]]
            
            print(f"  -> Keeping: {keep_id}")
            print(f"  -> Deleting: {delete_ids}")
            
            merge_persons(keep_id, delete_ids)
            total_merged += 1
            total_deleted += len(delete_ids)
    
    print("\n" + "=" * 60)
    print(f"Cleanup complete!")
    print(f"  Merged: {total_merged} groups")
    print(f"  Deleted: {total_deleted} duplicate persons")
    print("=" * 60)
    
    # Final count
    result = db.execute(text("SELECT COUNT(*) FROM persons"))
    print(f"\nTotal persons remaining: {result.scalar()}")

if __name__ == "__main__":
    main()
