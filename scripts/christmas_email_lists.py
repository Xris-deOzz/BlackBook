"""
Christmas Email List Generator.

Generates two lists of people for Christmas emails:
1. Polish-speaking (people in Poland or with Polish names/locations)
2. English-speaking (everyone else)
"""

import sys
import io
from pathlib import Path

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models.person import Person
from app.models.person_address import PersonAddress


def get_christmas_email_lists():
    """
    Query the database and categorize people into Polish and English speaking groups.

    Polish-speaking criteria:
    - Address country contains 'Poland' or 'Polska'
    - Location field contains 'Poland', 'Polska', 'Warsaw', 'Warszawa', 'Krakow', 'Kraków', etc.
    - Last name ends with common Polish suffixes (-ski, -ska, -wicz, -czyk, etc.)

    Returns two lists: (polish_speaking, english_speaking)
    """
    db = SessionLocal()

    try:
        # Get all people with their emails and addresses
        people = db.query(Person).options(
            joinedload(Person.emails),
            joinedload(Person.addresses),
            joinedload(Person.tags)
        ).all()

        polish_speaking = []
        english_speaking = []

        # Polish cities and keywords
        polish_keywords = [
            'poland', 'polska', 'polish',
            'warsaw', 'warszawa',
            'krakow', 'kraków', 'cracow',
            'gdansk', 'gdańsk',
            'wroclaw', 'wrocław',
            'poznan', 'poznań',
            'lodz', 'łódź',
            'katowice', 'szczecin', 'lublin', 'bydgoszcz',
            'bialystok', 'białystok', 'torun', 'toruń',
        ]

        # Polish name suffixes
        polish_suffixes = ['-ski', '-ska', '-wicz', '-icz', '-czyk', '-czak', '-owski', '-owska', '-ewski', '-ewska']

        for person in people:
            is_polish = False

            # Check addresses for Poland
            for addr in person.addresses:
                if addr.country:
                    country_lower = addr.country.lower()
                    if 'poland' in country_lower or 'polska' in country_lower:
                        is_polish = True
                        break
                if addr.city:
                    city_lower = addr.city.lower()
                    if any(kw in city_lower for kw in polish_keywords):
                        is_polish = True
                        break

            # Check location field
            if not is_polish and person.location:
                location_lower = person.location.lower()
                if any(kw in location_lower for kw in polish_keywords):
                    is_polish = True

            # Check last name for Polish suffixes
            if not is_polish and person.last_name:
                last_name_lower = person.last_name.lower()
                for suffix in polish_suffixes:
                    if last_name_lower.endswith(suffix.replace('-', '')):
                        is_polish = True
                        break

            # Get primary email
            email = person.primary_email

            # Create person data dict
            person_data = {
                'name': person.full_name,
                'first_name': person.first_name or person.full_name.split()[0] if person.full_name else '',
                'email': email,
                'location': person.location,
                'tags': [t.name for t in person.tags] if person.tags else [],
            }

            if is_polish:
                polish_speaking.append(person_data)
            else:
                english_speaking.append(person_data)

        return polish_speaking, english_speaking

    finally:
        db.close()


def print_list(title: str, people: list, language: str):
    """Print a formatted list of people."""
    print(f"\n{'='*60}")
    print(f" {title} ({len(people)} people)")
    print(f"{'='*60}")

    # Filter to only people with emails
    with_email = [p for p in people if p['email']]
    without_email = [p for p in people if not p['email']]

    print(f"\nWith email ({len(with_email)}):")
    print("-" * 40)
    for i, p in enumerate(sorted(with_email, key=lambda x: x['name']), 1):
        location_str = f" ({p['location']})" if p['location'] else ""
        tags_str = f" [{', '.join(p['tags'])}]" if p['tags'] else ""
        print(f"  {i}. {p['name']}{location_str}")
        print(f"     Email: {p['email']}{tags_str}")

    if without_email:
        print(f"\nWithout email ({len(without_email)}):")
        print("-" * 40)
        for p in sorted(without_email, key=lambda x: x['name']):
            location_str = f" ({p['location']})" if p['location'] else ""
            print(f"  - {p['name']}{location_str}")


def export_csv(filename: str, people: list, language: str):
    """Export list to CSV file."""
    import csv

    with_email = [p for p in people if p['email']]

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'First Name', 'Email', 'Location', 'Tags', 'Language'])
        for p in sorted(with_email, key=lambda x: x['name']):
            writer.writerow([
                p['name'],
                p['first_name'],
                p['email'],
                p['location'] or '',
                ', '.join(p['tags']) if p['tags'] else '',
                language
            ])

    print(f"Exported {len(with_email)} contacts to {filename}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Generate Christmas email lists')
    parser.add_argument('--export', action='store_true', help='Export to CSV files')
    args = parser.parse_args()

    print("Christmas Email List Generator")
    print("=" * 60)

    polish, english = get_christmas_email_lists()

    print_list("POLISH-SPEAKING CONTACTS", polish, "Polish")
    print_list("ENGLISH-SPEAKING CONTACTS", english, "English")

    # Summary
    print(f"\n{'='*60}")
    print(" SUMMARY")
    print(f"{'='*60}")
    polish_with_email = len([p for p in polish if p['email']])
    english_with_email = len([p for p in english if p['email']])
    print(f"  Polish-speaking: {polish_with_email} with email, {len(polish) - polish_with_email} without")
    print(f"  English-speaking: {english_with_email} with email, {len(english) - english_with_email} without")
    print(f"  Total: {polish_with_email + english_with_email} contacts with email")

    # Export if requested
    if args.export:
        print(f"\n{'='*60}")
        export_csv('christmas_polish.csv', polish, 'Polish')
        export_csv('christmas_english.csv', english, 'English')
        print("\nCSV files created in current directory!")
