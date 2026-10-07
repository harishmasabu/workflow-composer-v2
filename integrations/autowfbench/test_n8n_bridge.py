import unittest
from n8n_solution import validate_result, WORKFLOW_ID

class BridgeTests(unittest.TestCase):
    def test_acknowledgment_is_not_completion(self):
        with self.assertRaises(Exception):
            validate_result({"message":"Workflow was started"},"run-a")

    def test_requires_run_and_workflow_provenance(self):
        result={"protocol_version":"1.0","run_id":"run-a","status":"completed",
                "final_answer":"Observed result","artifacts":[{"name":"incident-summary.md","media_type":"text/markdown","content":"Summary"}],
                "trace":[{"timestamp":"now","kind":"n8n_execution","data":{"workflow_id":WORKFLOW_ID,"execution_id":"123","run_id":"run-a"}}]}
        self.assertIs(validate_result(result,"run-a"),result)
        with self.assertRaises(ValueError):
            validate_result(result,"run-b")
        result["trace"][0]["data"]["workflow_id"]="unrelated"
        with self.assertRaises(ValueError):
            validate_result(result,"run-a")

if __name__=="__main__":
    unittest.main()
