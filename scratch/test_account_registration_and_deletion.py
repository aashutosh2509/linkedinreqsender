import urllib.request
import urllib.error
import json
import os

ADD_URL = "http://127.0.0.1:5000/api/accounts/add"
DELETE_URL = "http://127.0.0.1:5000/api/accounts/delete"
TEST_ACC_ID = "temp_scratch_test_acc"

def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.getcode(), json.loads(res.read().decode("utf-8"))

try:
    print(f"1. Registering test profile '{TEST_ACC_ID}'...")
    add_code, add_res = post_json(ADD_URL, {
        "id": TEST_ACC_ID,
        "name": "Scratch Temp Test Account"
    })
    print(f"   Status Code: {add_code}")
    print(f"   Response: {add_res}")
    
    db_file_name = f"db_{TEST_ACC_ID}.json"
    db_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "accounts_db", db_file_name)
    print(f"2. Verifying database file exists: {db_file_path}")
    if os.path.exists(db_file_path):
        print("   Success: Database file exists!")
    else:
        print("   Failure: Database file is missing!")
        
    print(f"3. Deleting test profile '{TEST_ACC_ID}'...")
    del_code, del_res = post_json(DELETE_URL, {
        "id": TEST_ACC_ID
    })
    print(f"   Status Code: {del_code}")
    print(f"   Response: {del_res}")
    
    print("4. Re-verifying database file path has been cleaned up...")
    if not os.path.exists(db_file_path):
        print("   Success: Database file has been deleted!")
    else:
        print("   Failure: Database file still exists!")
        
except Exception as e:
    print(f"Test script failed with exception: {str(e)}")
