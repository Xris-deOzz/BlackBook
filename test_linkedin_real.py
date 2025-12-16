"""Test LinkedIn import with the actual CSV file."""
from app.services.linkedin_import import LinkedInImportService
from app.database import SessionLocal
from app.models import Person

# Read the actual LinkedIn CSV
csv_path = r"C:\Users\ossow\Downloads\Basic_LinkedInDataExport_12-08-2025.zip\Connections.csv"
with open(csv_path, 'r', encoding='utf-8') as f:
    csv_content = f.read()

print(f"CSV content first 500 chars:\n{csv_content[:500]}\n")

db = SessionLocal()
service = LinkedInImportService(db)

# Build the name cache
service._build_name_cache()

cache_size = len(service._name_to_person_cache)
print(f'Name cache has {cache_size} entries')

# Check for Rudi Ball
key_check = "rudi ball" in service._name_to_person_cache
print(f'"rudi ball" in cache: {key_check}')

# Parse the CSV
contacts = service._parse_csv(csv_content)
print(f'\nParsed {len(contacts)} contacts')

# Show first 5 contacts
print("\nFirst 5 contacts:")
for i, contact in enumerate(contacts[:5]):
    print(f"  {i+1}. {contact.full_name} | {contact.linkedin_url}")

# Try to find Rudi Ball in the parsed contacts
rudi_contacts = [c for c in contacts if c.full_name and 'rudi' in c.full_name.lower()]
print(f"\nContacts with 'rudi' in name: {len(rudi_contacts)}")
for c in rudi_contacts:
    print(f"  - {c.full_name} | {c.linkedin_url}")

# Try matching a few contacts
print("\n\nTrying to match first 5 contacts:")
for contact in contacts[:5]:
    if contact.full_name:
        person = service._match_contact_to_person(contact)
        if person:
            print(f"  MATCHED: {contact.full_name} -> {person.full_name} (current linkedin: {person.linkedin})")
        else:
            print(f"  NO MATCH: {contact.full_name}")

db.close()
