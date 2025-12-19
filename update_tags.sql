-- Update remaining tags with subcategories
UPDATE tags SET subcategory = 'Role/Industry' WHERE name = 'Enterpreneur';
UPDATE tags SET subcategory = 'Role/Industry' WHERE name LIKE 'Referrals%';
UPDATE tags SET subcategory = 'Former Colleague' WHERE name = 'Formerly worked together';
UPDATE tags SET subcategory = 'Former Colleague' WHERE name = 'Salute';
UPDATE tags SET subcategory = 'Classmates' WHERE name = 'Goodenough';
UPDATE tags SET subcategory = 'Location' WHERE name = 'PL';
UPDATE tags SET subcategory = 'Relationship' WHERE name = 'Xmas ENG';
UPDATE tags SET subcategory = 'Relationship' WHERE name = 'Competition';

-- Show any remaining uncategorized People tags
SELECT name, subcategory FROM tags WHERE category IS NULL AND subcategory IS NULL ORDER BY name;
