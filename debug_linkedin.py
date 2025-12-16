from app.services.linkedin_import import LinkedInImportService
from app.database import SessionLocal
from app.models import Person

# Sample CSV with Rudi Ball
sample_csv = '''First Name,Last Name,URL,Email Address,Company,Position,Connected On
Rudi,Ball,https://www.linkedin.com/in/rudiball,,Digital Reasoning,Head of Sales,2020-01-15
'''

db = SessionLocal()
service = LinkedInImportService(db)

# Build the name cache
service._build_name_cache()

cache_size = len(service._name_to_person_cache)
print(f'Name cache has {cache_size} entries')

key_check = "rudi ball" in service._name_to_person_cache
print(f'rudi ball in cache: {key_check}')

# Parse the CSV
contacts = service._parse_csv(sample_csv)
print(f'\nParsed {len(contacts)} contacts')

for contact in contacts:
    print(f'\nTrying to match: [{contact.full_name}]')
    normalized = service._normalize_name(contact.full_name)
    print(f'  Normalized: [{normalized}]')
    in_cache = normalized in service._name_to_person_cache
    print(f'  In cache: {in_cache}')

    # Try matching
    person = service._match_contact_to_person(contact)
    if person:
        print(f'  MATCHED to: {person.full_name} (ID: {person.id})')
        print(f'  Current LinkedIn: {person.linkedin}')
        print(f'  CSV LinkedIn: {contact.linkedin_url}')
    else:
        print('  NO MATCH')

db.close()
