import os

os.environ['env'] = 'dev'

# juste une valeur factice pour les tests
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/test_db'