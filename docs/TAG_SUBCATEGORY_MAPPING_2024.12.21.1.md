# Tag Subcategory Mapping for BlackBook

**Version**: 2024.12.21.1
**Purpose**: Define the mapping between Google Contact labels and BlackBook tag subcategories

---

## Overview

When Google Contacts are synced to BlackBook, labels (tags) are imported. This document defines:
1. The 10 official subcategories for People Tags
2. Default colors for each subcategory
3. Mapping of known Google labels to subcategories

---

## Subcategory Definitions

| # | Subcategory Name | Default Color | Hex Code | Description |
|---|------------------|---------------|----------|-------------|
| 1 | Location | Blue | `#3b82f6` | Geographic grouping |
| 2 | Classmates | Cyan | `#06b6d4` | School/university classmates |
| 3 | Education | Violet | `#8b5cf6` | Educational institutions attended |
| 4 | Holidays | Orange | `#f97316` | Holiday card and greeting lists |
| 5 | Personal | Pink | `#ec4899` | Personal contacts and family |
| 6 | Social | Green | `#22c55e` | Social groups and clubs |
| 7 | Professional | Purple | `#a855f7` | Professional roles and resources |
| 8 | Former Colleagues | Teal | `#14b8a6` | Past workplace connections |
| 9 | Investor Type | Indigo | `#6366f1` | Investment professionals by type |
| 10 | Relationship Origin | Rose | `#f43f5e` | How you met/know the person |

---

## Google Label → Subcategory Mapping

### Location
```python
"NYC": "Location",
"SF": "Location",
"Boston": "Location",
"Chicago": "Location",
"London": "Location",
"PL": "Location",
"Georgia": "Location",
"Moscow": "Location",
"DC": "Location",
"Bialystok": "Location",
```

### Classmates
```python
"Georgetown": "Classmates",
```

### Education
```python
"Goodenough": "Education",
"Hentz": "Education",
"LFC": "Education",
"LSE": "Education",
"Maine East": "Education",
```

### Holidays
```python
"Xmas - Holidays": "Holidays",
"Xmas ENG": "Holidays",
"Xmas PL": "Holidays",
"Happy Easter": "Holidays",
"Hanukah": "Holidays",
```

### Personal
```python
"Admin": "Personal",
"Matt": "Personal",
"Personal": "Personal",
"Art": "Personal",
"Karski": "Personal",
```

### Social
```python
"Nudists": "Social",
"X-Guys": "Social",
```

### Professional
```python
"Entrepreneur | Founder": "Professional",
"C-Suite": "Professional",
"Partner": "Professional",
"Managing Director": "Professional",
"VP/Director": "Professional",
"Advisor": "Professional",
"Lawyer": "Professional",
"Banker": "Professional",
"Accountant/CPA": "Professional",
"Recruiter/Headhunter": "Professional",
"Journalist/Media": "Professional",
"Academic/Professor": "Professional",
"Government/Regulator": "Professional",
"Medical Contacts": "Professional",
"Actuary": "Professional",
"Creative": "Professional",
"Referrals | Introductions": "Professional",
"Tech": "Professional",
"StartOut": "Professional",
"Operations": "Professional",
# Legacy tags that map to Professional
"Resource: Lawyer": "Professional",
"Resource: Actuary": "Professional",
"Resource: Tech": "Professional",
"Resource: Operations": "Professional",
"Headhunters": "Professional",
"Headhunter/Recruiter": "Professional",
"Banker | Consultant": "Professional",
```

### Former Colleagues
```python
"Credit Suisse": "Former Colleagues",
"GAFG": "Former Colleagues",
"Lehman": "Former Colleagues",
"Salute": "Former Colleagues",
"State Department": "Former Colleagues",
```

### Investor Type
```python
"VC - Early Stage": "Investor Type",
"VC - Growth": "Investor Type",
"PE - Buyout": "Investor Type",
"PE - Growth Equity": "Investor Type",
"Angel Investor": "Investor Type",
"Family Office": "Investor Type",
"Hedge Fund - Long/Short": "Investor Type",
"Hedge Fund - Market Neutral; Pure Alpha": "Investor Type",
"Hedge Fund - Risk Arb": "Investor Type",
"Hedge Fund - Distressed / Special Situations": "Investor Type",
"Hedge Fund - Activist": "Investor Type",
"Hedge Fund - Macro (Rates, FX, Com)": "Investor Type",
"Hedge Fund - Relative Value / Arb": "Investor Type",
"Hedge Fund - Credit": "Investor Type",
"Hedge Fund - Quant | HFT": "Investor Type",
"Private Credit": "Investor Type",
"LP": "Investor Type",
"Corporate VC": "Investor Type",
"Sovereign Wealth": "Investor Type",
# Legacy tags that map to Investor Type
"Venture VC": "Investor Type",
"PE / Institutional": "Investor Type",
"Angel": "Investor Type",
"Hedge Fund": "Investor Type",
```

### Relationship Origin
```python
"Family": "Relationship Origin",
"Friend": "Relationship Origin",
"Classmate": "Relationship Origin",
"Former Colleague": "Relationship Origin",
"Referral": "Relationship Origin",
"Conference/Event": "Relationship Origin",
"Cold Outreach": "Relationship Origin",
"Board Connection": "Relationship Origin",
"Deal Connection": "Relationship Origin",
"Social Apps": "Relationship Origin",
```

---

## Complete Python Mapping Dictionary

```python
# For use in contacts_service.py
GOOGLE_LABEL_TO_SUBCATEGORY = {
    # Location
    "NYC": "Location",
    "SF": "Location",
    "Boston": "Location",
    "Chicago": "Location",
    "London": "Location",
    "PL": "Location",
    "Georgia": "Location",
    "Moscow": "Location",
    "DC": "Location",
    "Bialystok": "Location",
    
    # Classmates
    "Georgetown": "Classmates",
    
    # Education
    "Goodenough": "Education",
    "Hentz": "Education",
    "LFC": "Education",
    "LSE": "Education",
    "Maine East": "Education",
    
    # Holidays
    "Xmas - Holidays": "Holidays",
    "Xmas ENG": "Holidays",
    "Xmas PL": "Holidays",
    "Happy Easter": "Holidays",
    "Hanukah": "Holidays",
    
    # Personal
    "Admin": "Personal",
    "Matt": "Personal",
    "Personal": "Personal",
    "Art": "Personal",
    "Karski": "Personal",
    
    # Social
    "Nudists": "Social",
    "X-Guys": "Social",
    
    # Professional
    "Entrepreneur | Founder": "Professional",
    "C-Suite": "Professional",
    "Partner": "Professional",
    "Managing Director": "Professional",
    "VP/Director": "Professional",
    "Advisor": "Professional",
    "Lawyer": "Professional",
    "Banker": "Professional",
    "Accountant/CPA": "Professional",
    "Recruiter/Headhunter": "Professional",
    "Journalist/Media": "Professional",
    "Academic/Professor": "Professional",
    "Government/Regulator": "Professional",
    "Medical Contacts": "Professional",
    "Actuary": "Professional",
    "Creative": "Professional",
    "Referrals | Introductions": "Professional",
    "Tech": "Professional",
    "StartOut": "Professional",
    "Operations": "Professional",
    "Resource: Lawyer": "Professional",
    "Resource: Actuary": "Professional",
    "Resource: Tech": "Professional",
    "Resource: Operations": "Professional",
    "Headhunters": "Professional",
    "Headhunter/Recruiter": "Professional",
    "Banker | Consultant": "Professional",
    
    # Former Colleagues
    "Credit Suisse": "Former Colleagues",
    "GAFG": "Former Colleagues",
    "Lehman": "Former Colleagues",
    "Salute": "Former Colleagues",
    "State Department": "Former Colleagues",
    
    # Investor Type
    "VC - Early Stage": "Investor Type",
    "VC - Growth": "Investor Type",
    "PE - Buyout": "Investor Type",
    "PE - Growth Equity": "Investor Type",
    "Angel Investor": "Investor Type",
    "Family Office": "Investor Type",
    "Hedge Fund - Long/Short": "Investor Type",
    "Hedge Fund - Market Neutral; Pure Alpha": "Investor Type",
    "Hedge Fund - Risk Arb": "Investor Type",
    "Hedge Fund - Distressed / Special Situations": "Investor Type",
    "Hedge Fund - Activist": "Investor Type",
    "Hedge Fund - Macro (Rates, FX, Com)": "Investor Type",
    "Hedge Fund - Relative Value / Arb": "Investor Type",
    "Hedge Fund - Credit": "Investor Type",
    "Hedge Fund - Quant | HFT": "Investor Type",
    "Private Credit": "Investor Type",
    "LP": "Investor Type",
    "Corporate VC": "Investor Type",
    "Sovereign Wealth": "Investor Type",
    "Venture VC": "Investor Type",
    "PE / Institutional": "Investor Type",
    "Angel": "Investor Type",
    "Hedge Fund": "Investor Type",
    
    # Relationship Origin
    "Family": "Relationship Origin",
    "Friend": "Relationship Origin",
    "Classmate": "Relationship Origin",
    "Former Colleague": "Relationship Origin",
    "Referral": "Relationship Origin",
    "Conference/Event": "Relationship Origin",
    "Cold Outreach": "Relationship Origin",
    "Board Connection": "Relationship Origin",
    "Deal Connection": "Relationship Origin",
    "Social Apps": "Relationship Origin",
}

# Subcategory default colors
SUBCATEGORY_COLORS = {
    "Location": "#3b82f6",
    "Classmates": "#06b6d4",
    "Education": "#8b5cf6",
    "Holidays": "#f97316",
    "Personal": "#ec4899",
    "Social": "#22c55e",
    "Professional": "#a855f7",
    "Former Colleagues": "#14b8a6",
    "Investor Type": "#6366f1",
    "Relationship Origin": "#f43f5e",
}

# Display order for subcategories
SUBCATEGORY_ORDER = [
    "Location",
    "Classmates", 
    "Education",
    "Holidays",
    "Personal",
    "Social",
    "Professional",
    "Former Colleagues",
    "Investor Type",
    "Relationship Origin",
]
```

---

## Implementation Notes

### For Google Sync (`contacts_service.py`)

When creating a new tag from a Google label:
1. Check if label exists in `GOOGLE_LABEL_TO_SUBCATEGORY`
2. If yes, set `tag.subcategory` to the mapped value
3. If no, leave `tag.subcategory` as NULL (user can assign later)
4. Use `SUBCATEGORY_COLORS` to set tag color based on subcategory

### For Migration (`a6w45x6y8z90_add_tag_subcategories_table.py`)

Seed the `tag_subcategories` table with:
- All 10 subcategories from `SUBCATEGORY_ORDER`
- Colors from `SUBCATEGORY_COLORS`
- `display_order` from 1-10

### For UI (Settings > Tags)

- Show subcategory color picker in the collapsible header row
- Add "Apply to All" button in header row
- Add combined "Add Tag | Subcategory" dropdown button
- Show tags without subcategory in "Uncategorized" section

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2024-12-21 | 1 | Initial mapping based on user's Excel and Google Contacts |

