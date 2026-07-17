import requests
import sys
import json
from datetime import datetime

class MoodRecAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timed out after {timeout} seconds")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        if success:
            print(f"   LLM Available: {response.get('llm_available', 'Unknown')}")
            print(f"   APIs Configured: {response.get('apis_configured', {})}")
        return success

    def test_mood_analysis(self, memory_text):
        """Test mood analysis endpoint"""
        success, response = self.run_test(
            "Mood Analysis",
            "POST",
            "api/analyze-mood",
            200,
            data={
                "memory_text": memory_text,
                "user_id": "test_user"
            },
            timeout=45  # Longer timeout for AI processing
        )
        if success:
            print(f"   Detected Mood: {response.get('mood', 'Unknown')}")
            print(f"   Confidence: {response.get('confidence', 0):.2f}")
            print(f"   Emotions: {response.get('emotions', [])}")
            print(f"   Analysis: {response.get('analysis', '')[:100]}...")
        return success, response

    def test_recommendations(self, mood, content_types=None, languages=None):
        """Test recommendations endpoint"""
        if content_types is None:
            content_types = ["movies", "books", "dramas", "songs"]
        if languages is None:
            languages = ["en"]
            
        success, response = self.run_test(
            f"Recommendations for {mood}",
            "POST",
            "api/recommendations",
            200,
            data={
                "mood": mood,
                "content_types": content_types,
                "languages": languages,
                "user_id": "test_user"
            }
        )
        if success:
            recommendations = response.get('recommendations', [])
            print(f"   Total Recommendations: {len(recommendations)}")
            for i, rec in enumerate(recommendations[:3]):  # Show first 3
                print(f"   {i+1}. {rec.get('title', 'Unknown')} ({rec.get('content_type', 'Unknown')})")
        return success, response

    def test_mood_analysis_edge_cases(self):
        """Test mood analysis with edge cases"""
        test_cases = [
            ("", "Empty text"),
            ("a", "Single character"),
            ("This is a very long text " * 50, "Very long text"),
        ]
        
        edge_case_results = []
        for text, description in test_cases:
            print(f"\n🔍 Testing Edge Case: {description}")
            try:
                success, response = self.run_test(
                    f"Mood Analysis - {description}",
                    "POST",
                    "api/analyze-mood",
                    200 if text else 422,  # Empty text might return validation error
                    data={
                        "memory_text": text,
                        "user_id": "test_user"
                    },
                    timeout=30
                )
                edge_case_results.append((description, success))
            except Exception as e:
                print(f"   Edge case failed: {e}")
                edge_case_results.append((description, False))
        
        return edge_case_results

    def test_recommendations_edge_cases(self):
        """Test recommendations with different parameters"""
        test_cases = [
            ({"mood": "happy", "content_types": ["movies"], "languages": ["en"]}, "Movies only"),
            ({"mood": "sad", "content_types": ["books"], "languages": ["en"]}, "Books only"),
            ({"mood": "excited", "content_types": ["dramas"], "languages": ["en"]}, "Dramas only"),
            ({"mood": "romantic", "content_types": ["movies", "books"], "languages": ["en", "es"]}, "Multiple types and languages"),
            ({"mood": "nonexistent_mood", "content_types": ["movies"], "languages": ["en"]}, "Invalid mood"),
        ]
        
        edge_case_results = []
        for params, description in test_cases:
            print(f"\n🔍 Testing Edge Case: {description}")
            try:
                success, response = self.run_test(
                    f"Recommendations - {description}",
                    "POST",
                    "api/recommendations",
                    200,
                    data=params,
                    timeout=30
                )
                edge_case_results.append((description, success))
            except Exception as e:
                print(f"   Edge case failed: {e}")
                edge_case_results.append((description, False))
        
        return edge_case_results

def main():
    print("🚀 Starting MoodRec API Testing...")
    print("=" * 60)
    
    # Setup
    tester = MoodRecAPITester()
    
    # Test 1: Health Check
    print("\n📋 PHASE 1: Health Check")
    health_success = tester.test_health_check()
    
    if not health_success:
        print("❌ Health check failed - backend may not be running properly")
        print(f"\n📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
        return 1
    
    # Test 2: Mood Analysis with the specific test case
    print("\n📋 PHASE 2: Mood Analysis")
    test_memory = "I spent the afternoon reading a book by the fireplace while it rained outside. The quiet moments felt so peaceful and I felt grateful for simple pleasures."
    
    mood_success, mood_response = tester.test_mood_analysis(test_memory)
    detected_mood = mood_response.get('mood', 'neutral') if mood_success else 'neutral'
    
    # Test 3: Recommendations based on detected mood
    print("\n📋 PHASE 3: Recommendations")
    if mood_success:
        rec_success, rec_response = tester.test_recommendations(detected_mood)
    else:
        # Fallback to test with a known mood
        rec_success, rec_response = tester.test_recommendations('peaceful')
    
    # Test 4: Direct mood recommendations
    print("\n📋 PHASE 4: Direct Mood Testing")
    direct_moods = ['happy', 'relaxed', 'nostalgic']
    for mood in direct_moods:
        tester.test_recommendations(mood, ["movies"], ["en"])
    
    # Test 5: Edge Cases
    print("\n📋 PHASE 5: Edge Case Testing")
    mood_edge_results = tester.test_mood_analysis_edge_cases()
    rec_edge_results = tester.test_recommendations_edge_cases()
    
    # Print final results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    print(f"Total Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
    
    if tester.tests_passed >= tester.tests_run * 0.8:  # 80% success rate
        print("✅ Backend API testing PASSED - Most functionality working")
        return 0
    else:
        print("❌ Backend API testing FAILED - Significant issues found")
        return 1

if __name__ == "__main__":
    sys.exit(main())