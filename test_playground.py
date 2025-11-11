"""Test script for the playground API."""

import json
import sys
from playground import app

def test_compile_api():
    """Test the compile API endpoint."""
    with app.test_client() as client:
        # Test basic compilation
        response = client.post('/api/compile', 
            json={'asql': 'from users', 'dialect': 'postgres'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'sql' in data
        assert 'SELECT * FROM users' in data['sql']
        print("✓ Basic compilation works")
        
        # Test with WHERE clause
        response = client.post('/api/compile',
            json={'asql': 'from users where status == "active"', 'dialect': 'postgres'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'sql' in data
        assert 'WHERE' in data['sql']
        print("✓ WHERE clause compilation works")
        
        # Test GROUP BY
        response = client.post('/api/compile',
            json={'asql': 'from users group by country ( # as total )', 'dialect': 'postgres'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'sql' in data
        assert 'GROUP BY' in data['sql']
        print("✓ GROUP BY compilation works")
        
        # Test error handling
        response = client.post('/api/compile',
            json={'asql': 'invalid query', 'dialect': 'postgres'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'error' in data
        print("✓ Error handling works")
        
        # Test empty query
        response = client.post('/api/compile',
            json={'asql': '', 'dialect': 'postgres'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'error' in data
        print("✓ Empty query handling works")
        
        print("\n✅ All API tests passed!")

if __name__ == '__main__':
    try:
        test_compile_api()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
